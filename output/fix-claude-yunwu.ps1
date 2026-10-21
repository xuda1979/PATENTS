param(
  [string]$ApiKey,
  [string]$BaseUrl = "https://api.yunwu.ai"
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Content
  )

  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }

  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function New-BackupIfExists {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path $Path)) {
    return
  }

  $timestamp = Get-Date -Format "yyyyMMddHHmmss"
  Copy-Item -LiteralPath $Path -Destination "$Path.yunwu-fix.$timestamp.bak" -Force
}

function Disable-PowerShellShim {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path $Path)) {
    return
  }

  $disabledPath = "$Path.disabled"
  if (Test-Path $disabledPath) {
    Remove-Item -LiteralPath $disabledPath -Force
  }

  Move-Item -LiteralPath $Path -Destination $disabledPath -Force
}

function Get-GitBashPath {
  $candidates = @()

  if ($env:CLAUDE_CODE_GIT_BASH_PATH) {
    $candidates += $env:CLAUDE_CODE_GIT_BASH_PATH
  }

  $candidates += @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files\Git\usr\bin\bash.exe"
  )

  try {
    $whereMatches = & where.exe bash 2>$null
    if ($whereMatches) {
      $candidates += $whereMatches
    }
  } catch {
  }

  $preferred = $candidates | Where-Object {
    $_ -and (Test-Path $_) -and ($_ -notmatch "\\Windows\\System32\\bash\.exe$")
  } | Select-Object -First 1

  if ($preferred) {
    return $preferred
  }

  $fallback = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if ($fallback) {
    return $fallback
  }

  throw "Unable to locate a usable bash.exe for Claude Code."
}

function Get-PrimaryYunwuKey {
  param([string]$ExplicitApiKey)

  if ($ExplicitApiKey) {
    return $ExplicitApiKey
  }

  if ($env:YUNWU_API_KEY) {
    return $env:YUNWU_API_KEY
  }

  if ($env:ANTHROPIC_API_KEY) {
    return $env:ANTHROPIC_API_KEY
  }

  throw "Neither YUNWU_API_KEY nor ANTHROPIC_API_KEY is set in the current environment."
}

function Set-ObjectProperty {
  param(
    [Parameter(Mandatory = $true)]$InputObject,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)]$Value
  )

  $property = $InputObject.PSObject.Properties[$Name]
  if ($property) {
    $property.Value = $Value
  } else {
    Add-Member -InputObject $InputObject -NotePropertyName $Name -NotePropertyValue $Value
  }
}

$userProfile = [Environment]::GetFolderPath("UserProfile")
$npmBin = Join-Path $env:APPDATA "npm"
$claudeCmdPath = Join-Path $npmBin "claude.cmd"
$claudeShPath = Join-Path $npmBin "claude"
$claudePs1Path = Join-Path $npmBin "claude.ps1"
$claudeWrapperPs1Path = Join-Path $npmBin "claude-yunwu-wrapper.ps1"
$claudeJsonPath = Join-Path $userProfile ".claude.json"

$gitBashPath = Get-GitBashPath
$baseUrl = $BaseUrl.TrimEnd("/")
$primaryKey = Get-PrimaryYunwuKey -ExplicitApiKey $ApiKey
$approvedKeyTail = if ($primaryKey.Length -le 20) { $primaryKey } else { $primaryKey.Substring($primaryKey.Length - 20) }

$claudeCmd = @"
@ECHO OFF
SETLOCAL
SET "dp0=%~dp0"
IF NOT "%YUNWU_API_KEY%"=="" SET "ANTHROPIC_API_KEY=%YUNWU_API_KEY%"
SET "ANTHROPIC_BASE_URL=$baseUrl"
SET "ANTHROPIC_MODEL=claude-opus-4-6"
SET "ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-6"
SET "CLAUDE_CODE_GIT_BASH_PATH=$gitBashPath"
SET "ANTHROPIC_AUTH_TOKEN="
SET "CLAUDE_CODE_OAUTH_TOKEN="
SET "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR="
SET "CLAUDE_CODE_SESSION_ACCESS_TOKEN="
SET "CLAUDE_CODE_CUSTOM_OAUTH_URL="

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%dp0%\claude-yunwu-wrapper.ps1" %*
"@

$claudeWrapperPs1 = @'
$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodePath = Join-Path $baseDir "node.exe"
if (-not (Test-Path $nodePath)) {
  $nodePath = "node"
}

$cliPath = Join-Path $baseDir "node_modules\@anthropic-ai\claude-code\cli.js"
$rewrittenArgs = New-Object System.Collections.Generic.List[string]
$legacyProviderConsumed = $false
$hasPromptOverride = $false
$skipAutoPrompt = $false
$autoExecutePrompt = [string]::Join("`n", @(
  "If the user's request is actionable and depends on local files, do not end your turn with only a plan, promise, acknowledgment, or statement of intent."
  "Use tools immediately, inspect the necessary files, make the needed edits, and continue until the task is materially completed or you hit a concrete blocker."
  "If the user says `"go ahead`", `"continue`", `"current directory`", or equivalent confirmation, treat that as authorization to execute the last proposed inspection or editing steps in the same turn."
  "After proposing improvements, do not wait for another nudge once the user has already authorized execution."
))

for ($i = 0; $i -lt $args.Count; $i++) {
  if (-not $legacyProviderConsumed -and $args[$i] -eq "-p" -and $i + 1 -lt $args.Count -and $args[$i + 1] -eq "yunwu") {
    # Compatibility shim: treat `-p yunwu` as a legacy provider selector, not as a print prompt.
    $legacyProviderConsumed = $true
    $i++
    continue
  }

  if ($args[$i] -eq "-m") {
    if ($i + 1 -ge $args.Count) {
      throw "error: option '-m' requires a value"
    }

    $rewrittenArgs.Add("--model")
    $i++
    $rewrittenArgs.Add($args[$i])
    continue
  }

  if ($args[$i] -in @("--system-prompt", "--append-system-prompt")) {
    $hasPromptOverride = $true
  }

  if ($args[$i] -in @("--help", "-h", "--version", "-v", "auth", "doctor", "install", "mcp", "plugin", "setup-token", "update", "upgrade")) {
    $skipAutoPrompt = $true
  }

  $rewrittenArgs.Add($args[$i])
}

if (-not $hasPromptOverride -and -not $skipAutoPrompt) {
  $rewrittenArgs.Add("--append-system-prompt")
  $rewrittenArgs.Add($autoExecutePrompt)
}

& $nodePath $cliPath @rewrittenArgs
exit $LASTEXITCODE
'@

$claudeSh = @'
#!/bin/sh
basedir=$(dirname "$(echo "$0" | sed -e 's,\\,/,g')")

if [ -n "$YUNWU_API_KEY" ]; then
  export ANTHROPIC_API_KEY="$YUNWU_API_KEY"
fi
export ANTHROPIC_BASE_URL='__BASE_URL__'
export ANTHROPIC_MODEL='claude-opus-4-6'
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-6'
export CLAUDE_CODE_GIT_BASH_PATH='__GIT_BASH_PATH__'
unset ANTHROPIC_AUTH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR
unset CLAUDE_CODE_SESSION_ACCESS_TOKEN
unset CLAUDE_CODE_CUSTOM_OAUTH_URL

case `uname` in
    *CYGWIN*|*MINGW*|*MSYS*)
        if command -v cygpath > /dev/null 2>&1; then
            basedir=`cygpath -w "$basedir"`
        fi
    ;;
esac

if [ -x "$basedir/node" ]; then
  exec "$basedir/node" "$basedir/node_modules/@anthropic-ai/claude-code/cli.js" "$@"
else
  exec node "$basedir/node_modules/@anthropic-ai/claude-code/cli.js" "$@"
fi
'@
$claudeSh = $claudeSh.Replace("__GIT_BASH_PATH__", $gitBashPath)
$claudeSh = $claudeSh.Replace("__BASE_URL__", $baseUrl)

foreach ($path in @($claudeCmdPath, $claudePs1Path, $claudeWrapperPs1Path, $claudeShPath, $claudeJsonPath)) {
  New-BackupIfExists -Path $path
}

Write-Utf8NoBom -Path $claudeCmdPath -Content $claudeCmd
Write-Utf8NoBom -Path $claudeWrapperPs1Path -Content $claudeWrapperPs1
Write-Utf8NoBom -Path $claudeShPath -Content $claudeSh
Disable-PowerShellShim -Path $claudePs1Path

$config =
  if (Test-Path $claudeJsonPath) {
    Get-Content -Raw -LiteralPath $claudeJsonPath | ConvertFrom-Json
  } else {
    [pscustomobject]@{}
  }

Set-ObjectProperty -InputObject $config -Name "primaryApiKey" -Value $primaryKey

$customApiKeyResponsesProperty = $config.PSObject.Properties["customApiKeyResponses"]
$customApiKeyResponses = if ($customApiKeyResponsesProperty) { $customApiKeyResponsesProperty.Value } else { $null }
if (-not $customApiKeyResponses) {
  $customApiKeyResponses = [pscustomobject]@{
    approved = @()
    rejected = @()
  }
  Set-ObjectProperty -InputObject $config -Name "customApiKeyResponses" -Value $customApiKeyResponses
}

$approved = @()
if ($customApiKeyResponses.approved) {
  $approved = @($customApiKeyResponses.approved)
}
if ($approved -notcontains $approvedKeyTail) {
  $approved += $approvedKeyTail
}
Set-ObjectProperty -InputObject $customApiKeyResponses -Name "approved" -Value $approved

if (-not $customApiKeyResponses.rejected) {
  Set-ObjectProperty -InputObject $customApiKeyResponses -Name "rejected" -Value @()
}

$configJson = $config | ConvertTo-Json -Depth 100
Write-Utf8NoBom -Path $claudeJsonPath -Content $configJson

Write-Host "Updated launcher:" $claudeCmdPath
Write-Host "Disabled launcher:" "$claudePs1Path.disabled"
Write-Host "Updated launcher:" $claudeWrapperPs1Path
Write-Host "Updated launcher:" $claudeShPath
Write-Host "Updated config:" $claudeJsonPath
Write-Host "Using Git Bash:" $gitBashPath
Write-Host "Approved key tail:" $approvedKeyTail

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { ensureProfileDir } = require('./huanxin_profile');

const DEFAULT_URL =
  'https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3';

function usage() {
  console.error(`Usage:
  node browser-automation/huanxin_webshell_rw.js --url <train-dev-url> --read
  node browser-automation/huanxin_webshell_rw.js --url <train-dev-url> --write <text> [--enter]
  node browser-automation/huanxin_webshell_rw.js --url <train-dev-url> --command <shell-command> [--wait-ms 30000]

Options:
  --url <url>             Huanxin train-dev environment URL. Defaults to ASI3.
  --read                  Print current terminal snapshot.
  --write <text>          Insert literal text into the focused webshell.
  --write-file <path>     Insert literal file contents into the focused webshell.
  --enter                 Press Enter after --write/--write-file.
  --command <cmd>         Run shell command with start/end markers and capture output.
  --wait-ms <ms>          Wait time for terminal/open/command markers.
  --headful               Show the browser window.
  --hold-open             Keep the browser open after the action.
  --screenshot <path>     Save a full-page screenshot.
`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = {
    url: process.env.HUANXIN_TRAIN_DEV_URL || DEFAULT_URL,
    read: false,
    write: null,
    enter: false,
    command: null,
    waitMs: 30000,
    headful: false,
    holdOpen: false,
    screenshot: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--url') {
      args.url = argv[++index] || '';
    } else if (token === '--read') {
      args.read = true;
    } else if (token === '--write') {
      args.write = argv[++index] || '';
    } else if (token === '--write-file') {
      args.write = fs.readFileSync(path.resolve(argv[++index] || ''), 'utf8');
    } else if (token === '--enter') {
      args.enter = true;
    } else if (token === '--command') {
      args.command = argv[++index] || '';
    } else if (token === '--wait-ms') {
      args.waitMs = parseInt(argv[++index] || '30000', 10);
    } else if (token === '--headful') {
      args.headful = true;
    } else if (token === '--hold-open') {
      args.holdOpen = true;
    } else if (token === '--screenshot') {
      args.screenshot = argv[++index] || null;
    } else {
      usage();
    }
  }

  if (!args.url) usage();
  if (!args.read && args.write === null && !args.command) args.read = true;
  return args;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function resolveExecutablePath() {
  if (process.env.HUANXIN_BROWSER_EXECUTABLE_PATH) {
    return path.resolve(process.env.HUANXIN_BROWSER_EXECUTABLE_PATH);
  }
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return chromium.executablePath();
}

function launchOptions(args, profileDir) {
  const launchHomeDir = path.join(profileDir, '.chromium-home');
  const crashpadDir = path.join(launchHomeDir, 'crashpad');
  fs.mkdirSync(crashpadDir, { recursive: true });
  return {
    headless: !args.headful && process.env.HUANXIN_HEADLESS !== '0',
    executablePath: resolveExecutablePath(),
    viewport: { width: 1600, height: 1000 },
    slowMo: 25,
    args: [
      `--crash-dumps-dir=${crashpadDir}`,
      '--disable-crash-reporter',
      '--disable-crashpad-for-testing',
    ],
  };
}

async function clickShellTabIfPresent(page) {
  const candidates = [
    page.getByText('Shell终端', { exact: true }).first(),
    page.getByText('Shell', { exact: true }).first(),
    page.locator('button, [role="tab"], [role="button"], a').filter({ hasText: /Shell|终端/ }).first(),
  ];
  for (const locator of candidates) {
    try {
      if ((await locator.count()) > 0) {
        await locator.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(1500);
      }
    } catch {}
  }
}

async function waitForTerminal(page, waitMs) {
  const deadline = Date.now() + waitMs;
  let lastState = null;
  while (Date.now() < deadline) {
    await clickShellTabIfPresent(page);
    lastState = await inspectTerminalState(page);
    if (lastState.terminalPresent && lastState.helperPresent) {
      return lastState;
    }
    await page.waitForTimeout(1000);
  }
  const error = new Error('terminal_not_found');
  error.state = lastState;
  throw error;
}

async function inspectTerminalState(page) {
  return page.evaluate(() => {
    const terminal = document.querySelector('.terminal.xterm, .xterm');
    const helper = document.querySelector('.terminal.xterm .xterm-helper-textarea, .xterm-helper-textarea');
    const rows = document.querySelector('.terminal.xterm .xterm-rows, .xterm-rows');
    const accessibility = document.querySelector('.terminal.xterm .xterm-accessibility, .xterm-accessibility');
    const clean = (value) => String(value || '').replace(/\u00a0/g, ' ').trimEnd();
    const rowTexts = rows
      ? Array.from(rows.children).map((row) => clean(row.textContent)).filter(Boolean)
      : [];
    const accessibilityTexts = accessibility
      ? Array.from(accessibility.children).map((row) => clean(row.textContent)).filter(Boolean)
      : [];
    const terminalText = terminal
      ? clean(terminal.innerText || terminal.textContent || '').split('\n').map((line) => line.trimEnd()).filter(Boolean)
      : [];
    let lines = rowTexts;
    if (accessibilityTexts.length > lines.length) lines = accessibilityTexts;
    if (terminalText.length > lines.length) lines = terminalText;
    return {
      url: location.href,
      title: document.title,
      terminalPresent: Boolean(terminal),
      helperPresent: Boolean(helper),
      rowCount: rows ? rows.children.length : 0,
      accessibilityCount: accessibility ? accessibility.children.length : 0,
      activeElement: document.activeElement
        ? {
            tag: document.activeElement.tagName,
            className: String(document.activeElement.className || ''),
          }
        : null,
      text: lines.join('\n'),
      bodyPreview: clean(document.body ? document.body.innerText : '').slice(0, 1000),
    };
  });
}

async function focusTerminal(page) {
  const terminal = page.locator('.terminal.xterm, .xterm').first();
  const helper = page.locator('.terminal.xterm .xterm-helper-textarea, .xterm-helper-textarea').first();
  await terminal.click({ timeout: 10000, force: true });
  await helper.evaluate((element) => element.focus());
  await page.waitForTimeout(200);
}

async function writeTerminal(page, text, enter) {
  await focusTerminal(page);
  await page.keyboard.insertText(text);
  if (enter) {
    await page.keyboard.press('Enter');
  }
}

async function waitForText(page, needle, waitMs) {
  const deadline = Date.now() + waitMs;
  let snapshot = await inspectTerminalState(page);
  while (Date.now() < deadline) {
    snapshot = await inspectTerminalState(page);
    if (snapshot.text.includes(needle)) return snapshot;
    await page.waitForTimeout(500);
  }
  return snapshot;
}

async function runCommand(page, command, waitMs) {
  const token = `HX_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const startMarker = `__${token}_START__`;
  const endMarker = `__${token}_END__`;
  const wrapped = `printf '${startMarker}\\n'; ${command}; rc=$?; printf '\\n${endMarker}:%s\\n' "$rc"`;
  await writeTerminal(page, `${wrapped}\n`, false);
  const snapshot = await waitForText(page, endMarker, waitMs);

  const lines = snapshot.text.split('\n');
  const startIndex = lines.findIndex((line) => line.includes(startMarker));
  let output = '';
  let exitCode = null;
  if (startIndex >= 0) {
    const out = [];
    for (let index = startIndex + 1; index < lines.length; index += 1) {
      const line = lines[index];
      const markerIndex = line.indexOf(endMarker);
      if (markerIndex >= 0) {
        const match = line.match(new RegExp(`${endMarker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:(\\d+)`));
        if (match) exitCode = parseInt(match[1], 10);
        break;
      }
      out.push(line);
    }
    output = out.join('\n').trim();
  }

  return { startMarker, endMarker, exitCode, output, snapshot };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { profileDir, isolated } = ensureProfileDir();
  const context = await chromium.launchPersistentContext(profileDir, launchOptions(args, profileDir));

  try {
    const page = context.pages()[0] || (await context.newPage());
    page.setDefaultTimeout(Math.min(Math.max(args.waitMs, 30000), 180000));
    await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: 180000 });
    await sleep(2500);
    const terminalState = await waitForTerminal(page, args.waitMs);

    let action = { type: 'read', snapshot: terminalState };
    if (args.command) {
      action = { type: 'command', command: args.command, ...(await runCommand(page, args.command, args.waitMs)) };
    } else if (args.write !== null) {
      await writeTerminal(page, args.write, args.enter);
      action = { type: 'write', bytes: Buffer.byteLength(args.write), snapshot: await inspectTerminalState(page) };
    } else if (args.read) {
      action = { type: 'read', snapshot: await inspectTerminalState(page) };
    }

    if (args.screenshot) {
      await page.screenshot({ path: path.resolve(args.screenshot), fullPage: true }).catch(() => {});
    }

    console.log(
      JSON.stringify(
        {
          ok: true,
          url: page.url(),
          profileDir,
          isolatedProfile: isolated,
          terminal: {
            present: true,
            rowCount: terminalState.rowCount,
            accessibilityCount: terminalState.accessibilityCount,
          },
          action,
        },
        null,
        2
      )
    );

    if (args.holdOpen) {
      process.stdin.resume();
      return;
    }
  } finally {
    if (!args.holdOpen) {
      await context.close();
    }
  }
}

module.exports = {
  inspectTerminalState,
  waitForTerminal,
  focusTerminal,
  writeTerminal,
  runCommand,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(
      JSON.stringify(
        {
          ok: false,
          error: error.message,
          state: error.state || null,
          stack: error.stack,
        },
        null,
        2
      )
    );
    process.exit(1);
  });
}

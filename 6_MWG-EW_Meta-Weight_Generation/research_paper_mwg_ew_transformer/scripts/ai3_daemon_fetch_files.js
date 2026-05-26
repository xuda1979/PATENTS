#!/usr/bin/env node
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function usage() {
  console.error('Usage: node scripts/ai3_daemon_fetch_files.js --file <remote-path> <local-path> [--file ...]');
  process.exit(2);
}

function parseArgs(argv) {
  const pairs = [];
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] !== '--file') usage();
    const remote = argv[++index];
    const local = argv[++index];
    if (!remote || !local) usage();
    pairs.push({ remote, local });
  }
  if (pairs.length === 0) usage();
  return pairs;
}

function parseShellWrapper(stdout) {
  const first = stdout.indexOf('{');
  const last = stdout.lastIndexOf('}');
  if (first < 0 || last < first) {
    throw new Error(`Could not parse ai3_shell JSON output: ${stdout.slice(0, 500)}`);
  }
  return JSON.parse(stdout.slice(first, last + 1));
}

function extractPayload(output) {
  const begin = '__AI3_DAEMON_FETCH_BEGIN__';
  const end = '__AI3_DAEMON_FETCH_END__';
  const lines = String(output || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const beginIndex = lines.lastIndexOf(begin);
  const endIndex = lines.lastIndexOf(end);
  if (beginIndex >= 0 && endIndex > beginIndex) {
    const candidateLines = lines.slice(beginIndex + 1, endIndex);
    const encoded = candidateLines.join('').replace(/[^A-Za-z0-9+/=]/g, '');
    return JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
  }
  const encodedOnly = lines
    .filter((line) => /^[A-Za-z0-9+/=]+$/.test(line))
    .slice(-1)[0];
  if (!encodedOnly) {
    throw new Error(`Missing fetch markers in remote output: ${String(output || '').slice(0, 1000)}`);
  }
  return JSON.parse(Buffer.from(encodedOnly, 'base64').toString('utf8'));
}

const pairs = parseArgs(process.argv.slice(2));
const scriptDir = __dirname;
const shellScript = path.join(scriptDir, 'ai3_shell.sh');
const fetched = [];
const transports = new Set();

function runRemoteJson(remoteBody) {
  const wrappedCode = [
    remoteBody,
    'payload = base64.b64encode(json.dumps(payload_obj).encode("utf-8")).decode("ascii")',
    'print("__AI3_DAEMON_FETCH_BEGIN__")',
    'print(payload)',
    'print("__AI3_DAEMON_FETCH_END__")',
  ].join('\n');
  const remoteCommand = `python3 - <<'PY'\nimport base64, hashlib, json, pathlib\n${wrappedCode}\nPY`;
  const stdout = execFileSync('bash', [shellScript, remoteCommand], {
    cwd: path.resolve(scriptDir, '..'),
    encoding: 'utf8',
    maxBuffer: 1024 * 1024 * 8,
    env: {
      ...process.env,
      AI3_ALLOW_BROWSER: '0',
      HUANXIN_ALLOW_STANDALONE_FALLBACK: '0',
    },
  });
  const shellResult = parseShellWrapper(stdout);
  if (!shellResult.ok || shellResult.commandOk === false) {
    throw new Error(`ai3_shell failed: ${JSON.stringify(shellResult, null, 2)}`);
  }
  if (shellResult.transport) transports.add(shellResult.transport);
  return extractPayload(shellResult.output || '');
}

for (const pair of pairs) {
  const payload = runRemoteJson([
    `p = ${JSON.stringify(pair.remote)}`,
    'data = pathlib.Path(p).read_bytes()',
    'payload_obj = {',
    '  "size": len(data),',
    '  "sha256": hashlib.sha256(data).hexdigest(),',
    '  "data_b64": base64.b64encode(data).decode("ascii"),',
    '}',
  ].join('\n'));
  const data = Buffer.from(payload.data_b64, 'base64');
  if (data.length !== payload.size) {
    throw new Error(`Size mismatch for ${pair.remote}: got ${data.length}, expected ${payload.size}`);
  }
  const crypto = require('crypto');
  const sha256 = crypto.createHash('sha256').update(data).digest('hex');
  if (sha256 !== payload.sha256) {
    throw new Error(`SHA256 mismatch for ${pair.remote}: got ${sha256}, expected ${payload.sha256}`);
  }
  fs.mkdirSync(path.dirname(pair.local), { recursive: true });
  fs.writeFileSync(pair.local, data);
  fetched.push({ remote: pair.remote, local: path.resolve(pair.local), bytes: data.length, sha256 });
}
console.log(JSON.stringify({ ok: true, transports: [...transports], fetched }, null, 2));

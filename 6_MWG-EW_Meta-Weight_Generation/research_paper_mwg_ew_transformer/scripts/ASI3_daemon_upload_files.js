#!/usr/bin/env node
const { execFileSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

function usage() {
  console.error('Usage: node scripts/ASI3_daemon_upload_files.js --file <local-path> <remote-path> [--file ...]');
  process.exit(2);
}

function parseArgs(argv) {
  const pairs = [];
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] !== '--file') usage();
    const local = argv[++index];
    const remote = argv[++index];
    if (!local || !remote) usage();
    pairs.push({ local, remote });
  }
  if (pairs.length === 0) usage();
  return pairs;
}

function parseShellWrapper(stdout) {
  const first = stdout.indexOf('{');
  const last = stdout.lastIndexOf('}');
  if (first < 0 || last < first) {
    throw new Error(`Could not parse ASI3_shell JSON output: ${stdout.slice(0, 500)}`);
  }
  return JSON.parse(stdout.slice(first, last + 1));
}

function extractPayload(output) {
  const begin = '__ASI3_DAEMON_UPLOAD_BEGIN__';
  const end = '__ASI3_DAEMON_UPLOAD_END__';
  const start = output.indexOf(begin);
  const finish = output.indexOf(end);
  if (start < 0 || finish < 0 || finish < start) {
    throw new Error(`Missing upload markers in remote output: ${output.slice(0, 1000)}`);
  }
  const encoded = output.slice(start + begin.length, finish).replace(/[^A-Za-z0-9+/=]/g, '');
  return JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
}

const pairs = parseArgs(process.argv.slice(2));
const scriptDir = __dirname;
const shellScript = path.join(scriptDir, 'ASI3_shell.sh');
const chunkBytes = parseInt(process.env.ASI3_DAEMON_UPLOAD_CHUNK_BYTES || '350', 10);
const hardTimeoutMs = parseInt(process.env.HUANXIN_DAEMON_HARD_TIMEOUT_MS || '120000', 10);
const uploaded = [];
const transports = new Set();

function runRemoteJson(remoteBody) {
  const wrappedCode = [
    remoteBody,
    'payload = base64.b64encode(json.dumps(payload_obj).encode("utf-8")).decode("ascii")',
    'print("__ASI3_DAEMON_UPLOAD_BEGIN__")',
    'print(payload)',
    'print("__ASI3_DAEMON_UPLOAD_END__")',
  ].join('\n');
  const remoteCommand = `python3 - <<'PY'\nimport base64, hashlib, json, os, pathlib\n${wrappedCode}\nPY`;
  const attempts = parseInt(process.env.ASI3_DAEMON_UPLOAD_RETRIES || '4', 10);
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    let stdout = '';
    try {
      stdout = execFileSync('bash', [shellScript, remoteCommand], {
        cwd: path.resolve(scriptDir, '..'),
        encoding: 'utf8',
        maxBuffer: 1024 * 1024 * 8,
        env: {
          ...process.env,
          ASI3_ALLOW_BROWSER: '0',
          HUANXIN_ALLOW_STANDALONE_FALLBACK: '0',
          HUANXIN_DAEMON_HARD_TIMEOUT_MS: String(hardTimeoutMs),
        },
      });
    } catch (error) {
      stdout = String(error.stdout || '');
      const shellResult = stdout ? parseShellWrapper(stdout) : {};
      if (shellResult.error === 'stale_daemon_state_recovered' && attempt < attempts) {
        continue;
      }
      throw error;
    }
    const shellResult = parseShellWrapper(stdout);
    if (shellResult.error === 'stale_daemon_state_recovered' && attempt < attempts) {
      continue;
    }
    if (!shellResult.ok || shellResult.commandOk === false) {
      throw new Error(`ASI3_shell failed: ${JSON.stringify(shellResult, null, 2)}`);
    }
    if (shellResult.transport) transports.add(shellResult.transport);
    return extractPayload(shellResult.output || '');
  }
  throw new Error('ASI3_shell failed after stale daemon retries');
}

for (const pair of pairs) {
  const localPath = path.resolve(pair.local);
  const data = fs.readFileSync(localPath);
  const sha256 = crypto.createHash('sha256').update(data).digest('hex');
  const remote = pair.remote;
  const tmpRemote = `${remote}.ASI3-upload-${Date.now()}-${Math.random().toString(16).slice(2)}.tmp`;

  runRemoteJson([
    `target = pathlib.Path(${JSON.stringify(remote)})`,
    `tmp = pathlib.Path(${JSON.stringify(tmpRemote)})`,
    'target.parent.mkdir(parents=True, exist_ok=True)',
    'tmp.write_bytes(b"")',
    'payload_obj = {"state": "initialized", "tmp": str(tmp)}',
  ].join('\n'));

  for (let offset = 0; offset < data.length; offset += chunkBytes) {
    const chunk = data.subarray(offset, Math.min(offset + chunkBytes, data.length));
    const chunkB64 = chunk.toString('base64');
    runRemoteJson([
      `tmp = pathlib.Path(${JSON.stringify(tmpRemote)})`,
      `chunk = base64.b64decode(${JSON.stringify(chunkB64)})`,
      'with tmp.open("ab") as f:',
      '    f.write(chunk)',
      `payload_obj = {"state": "chunk", "offset": ${offset}, "bytes": len(chunk)}`,
    ].join('\n'));
  }

  const final = runRemoteJson([
    `target = pathlib.Path(${JSON.stringify(remote)})`,
    `tmp = pathlib.Path(${JSON.stringify(tmpRemote)})`,
    `expected_size = ${data.length}`,
    `expected_sha256 = ${JSON.stringify(sha256)}`,
    'blob = tmp.read_bytes()',
    'actual_sha256 = hashlib.sha256(blob).hexdigest()',
    'if len(blob) != expected_size or actual_sha256 != expected_sha256:',
    '    raise SystemExit(f"upload verification failed size={len(blob)} sha256={actual_sha256}")',
    'os.replace(tmp, target)',
    'payload_obj = {"state": "done", "remote": str(target), "bytes": len(blob), "sha256": actual_sha256}',
  ].join('\n'));
  uploaded.push({ local: localPath, remote: final.remote, bytes: final.bytes, sha256: final.sha256 });
}

console.log(JSON.stringify({ ok: true, transports: [...transports], uploaded }, null, 2));

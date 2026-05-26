#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

process.env.HUANXIN_TRAIN_DEV_URL =
  process.env.HUANXIN_TRAIN_DEV_URL ||
  'https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ai3';
process.env.HUANXIN_PROFILE_COPY_NAME = process.env.HUANXIN_PROFILE_COPY_NAME || 'mwg-ew-ai3-fetch';
process.env.HUANXIN_ALLOW_STANDALONE_FALLBACK = process.env.HUANXIN_ALLOW_STANDALONE_FALLBACK || '1';
process.env.HUANXIN_HEADLESS = process.env.HUANXIN_HEADLESS || '1';

if (process.env.AI3_ALLOW_BROWSER !== '1') {
  console.error(
    'Refusing to run ai3_fetch_files.js because it opens Huanxin browser automation. ' +
      'Use S3 scripts, an existing daemon shell, or set AI3_ALLOW_BROWSER=1 only when browser control is allowed.'
  );
  process.exit(2);
}

const quantumRoot = process.env.QUANTUM_GPT_DIR || '/Users/daxu/software/quantum-gpt';
const { launchPersistentContext } = require(path.join(quantumRoot, 'browser-automation/huanxin_browser_launch'));
const { ensureProfileDir } = require(path.join(quantumRoot, 'browser-automation/huanxin_profile'));
const { openShell, sendCommand } = require(path.join(quantumRoot, 'browser-automation/huanxin_shell_exec'));

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function parseArgs(argv) {
  const args = {
    chunkBytes: parseInt(process.env.AI3_FETCH_CHUNK_BYTES || '1200', 10),
    pairs: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--chunk-bytes') {
      args.chunkBytes = parseInt(argv[++index], 10);
    } else if (token === '--file') {
      args.pairs.push({ remote: argv[++index], local: argv[++index] });
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }
  if (!Number.isFinite(args.chunkBytes) || args.chunkBytes < 256) {
    throw new Error(`Invalid --chunk-bytes: ${args.chunkBytes}`);
  }
  if (args.pairs.length === 0) {
    throw new Error('Pass at least one --file <remote-path> <local-path> pair.');
  }
  return args;
}

function extractBetween(text, begin, end) {
  const start = text.indexOf(begin);
  if (start === -1) {
    throw new Error(`Missing begin marker ${begin}`);
  }
  const afterStart = start + begin.length;
  const finish = text.indexOf(end, afterStart);
  if (finish === -1) {
    throw new Error(`Missing end marker ${end}`);
  }
  return text.slice(afterStart, finish).replace(/\r/g, '').trim();
}

function parseJsonObject(text) {
  const first = text.indexOf('{');
  const last = text.lastIndexOf('}');
  if (first === -1 || last === -1 || last < first) {
    throw new Error(`No JSON object found in output: ${text.slice(0, 500)}`);
  }
  return JSON.parse(text.slice(first, last + 1));
}

async function fetchOne(activePage, remotePath, localPath, chunkBytes) {
  const metaBegin = `__HX_META_BEGIN_${Date.now()}__`;
  const metaEnd = `__HX_META_END_${Date.now()}__`;
  const metaCode = [
    'import hashlib,json,pathlib,sys',
    'p=pathlib.Path(sys.argv[1])',
    'd=p.read_bytes()',
    'print(json.dumps({"size":len(d),"sha256":hashlib.sha256(d).hexdigest()}))',
  ].join(';');
  const metaCommand = [
    `echo ${metaBegin}`,
    `python3 -c ${shellQuote(metaCode)} ${shellQuote(remotePath)}`,
    `echo ${metaEnd}`,
  ].join(' && ');
  const metaResult = await sendCommand(activePage, metaCommand, 30000);
  const meta = parseJsonObject(extractBetween(metaResult.output, metaBegin, metaEnd));

  const chunks = [];
  for (let offset = 0; offset < meta.size; offset += chunkBytes) {
    const length = Math.min(chunkBytes, meta.size - offset);
    const begin = `__HX_CHUNK_BEGIN_${offset}_${length}__`;
    const end = `__HX_CHUNK_END_${offset}_${length}__`;
    const chunkCode = [
      'import base64,pathlib,sys',
      'p=pathlib.Path(sys.argv[1])',
      'offset=int(sys.argv[2])',
      'length=int(sys.argv[3])',
      'data=p.read_bytes()[offset:offset+length]',
      'print(base64.b64encode(data).decode("ascii"))',
    ].join(';');
    const chunkCommand = [
      `echo ${begin}`,
      `python3 -c ${shellQuote(chunkCode)} ${shellQuote(remotePath)} ${offset} ${length}`,
      `echo ${end}`,
    ].join(' && ');
    const chunkResult = await sendCommand(activePage, chunkCommand, 30000);
    const encoded = extractBetween(chunkResult.output, begin, end).replace(/[^A-Za-z0-9+/=]/g, '');
    chunks.push(Buffer.from(encoded, 'base64'));
  }

  const data = Buffer.concat(chunks);
  if (data.length !== meta.size) {
    throw new Error(`Size mismatch for ${remotePath}: got ${data.length}, expected ${meta.size}`);
  }
  const crypto = require('crypto');
  const sha256 = crypto.createHash('sha256').update(data).digest('hex');
  if (sha256 !== meta.sha256) {
    throw new Error(`SHA256 mismatch for ${remotePath}: got ${sha256}, expected ${meta.sha256}`);
  }
  fs.mkdirSync(path.dirname(localPath), { recursive: true });
  fs.writeFileSync(localPath, data);
  return { remotePath, localPath, bytes: data.length, sha256 };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { profileDir } = ensureProfileDir();
  const launch = await launchPersistentContext(profileDir);
  const context = launch.context;
  const fetched = [];
  try {
    const page = context.pages()[0] || (await context.newPage());
    page.setDefaultTimeout(30000);
    const activePage = await openShell(page, process.env.HUANXIN_ENV_NAME || 'ASI3');
    for (const pair of args.pairs) {
      fetched.push(await fetchOne(activePage, pair.remote, path.resolve(pair.local), args.chunkBytes));
    }
  } finally {
    await context.close();
  }
  console.log(JSON.stringify({ ok: true, chunkBytes: args.chunkBytes, fetched }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});

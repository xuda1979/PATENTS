#!/usr/bin/env node
const { execFileSync } = require('child_process');
const path = require('path');

process.env.HUANXIN_TRAIN_DEV_URL =
  process.env.HUANXIN_TRAIN_DEV_URL ||
  'https://aihuanxin.cn/kunlun/kl-web?poolId=6&projectId=21b4208dde424e96b159362ef49c9c96#/train-dev/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ai3';
process.env.HUANXIN_PROFILE_COPY_NAME = process.env.HUANXIN_PROFILE_COPY_NAME || 'mwg-ew-ai3-upload';
process.env.HUANXIN_ALLOW_STANDALONE_FALLBACK = process.env.HUANXIN_ALLOW_STANDALONE_FALLBACK || '1';
process.env.HUANXIN_HEADLESS = process.env.HUANXIN_HEADLESS || '1';

if (process.env.AI3_ALLOW_BROWSER !== '1') {
  console.error(
    'Refusing to run ai3_upload.js because it opens Huanxin browser automation. ' +
      'Use S3 scripts, an existing daemon shell, or set AI3_ALLOW_BROWSER=1 only when browser control is allowed.'
  );
  process.exit(2);
}

const quantumRoot = process.env.QUANTUM_GPT_DIR || '/Users/daxu/software/quantum-gpt';
const { launchPersistentContext } = require(path.join(quantumRoot, 'browser-automation/huanxin_browser_launch'));
const { ensureProfileDir } = require(path.join(quantumRoot, 'browser-automation/huanxin_profile'));
const { openShell, readTerminalText, sendCommand } = require(path.join(
  quantumRoot,
  'browser-automation/huanxin_shell_exec'
));

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\"'\"'`)}'`;
}

function chunkString(value, chunkSize) {
  const chunks = [];
  for (let index = 0; index < value.length; index += chunkSize) {
    chunks.push(value.slice(index, index + chunkSize));
  }
  return chunks;
}

function parseArgs(argv) {
  const args = {
    remoteDir: '/vllm-workspace/mwg-ew-transformer-research',
    sources: ['README.md', 'paper', 'experiments', 'scripts'],
  };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--remote-dir') {
      args.remoteDir = argv[++i];
    } else if (token === '--source') {
      args.sources.push(argv[++i]);
    } else if (token === '--only') {
      args.sources = [argv[++i]];
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const workspaceRoot = path.resolve(__dirname, '..');
  const archive = execFileSync('tar', ['-czf', '-', ...args.sources], {
    cwd: workspaceRoot,
    env: { ...process.env, COPYFILE_DISABLE: '1' },
    maxBuffer: 1024 * 1024 * 128,
  });
  const archiveBase64 = archive.toString('base64');
  const chunks = chunkString(archiveBase64, 7000);
  const remoteBase = `/tmp/mwg-ew-ai3-upload-${Date.now()}`;

  const { profileDir } = ensureProfileDir();
  const launch = await launchPersistentContext(profileDir);
  const context = launch.context;
  try {
    const page = context.pages()[0] || (await context.newPage());
    page.setDefaultTimeout(30000);
    const activePage = await openShell(page, process.env.HUANXIN_ENV_NAME || 'ASI3');

    await sendCommand(
      activePage,
      `mkdir -p ${shellQuote(args.remoteDir)} && rm -f ${remoteBase}.tgz ${remoteBase}.tgz.b64 && : > ${remoteBase}.tgz.b64`,
      20000
    );

    for (const chunk of chunks) {
      await sendCommand(activePage, `printf %s ${shellQuote(chunk)} >> ${remoteBase}.tgz.b64`, 20000);
    }

    const extractCommand = [
      `base64 -d ${remoteBase}.tgz.b64 > ${remoteBase}.tgz`,
      `tar -xzf ${remoteBase}.tgz -C ${shellQuote(args.remoteDir)}`,
      `chmod +x ${shellQuote(args.remoteDir)}/scripts/*.sh || true`,
      `find ${shellQuote(args.remoteDir)} -name '._*' -delete`,
      `rm -f ${remoteBase}.tgz ${remoteBase}.tgz.b64`,
      `cd ${shellQuote(args.remoteDir)}`,
      `find . -maxdepth 3 -type f | sort | sed -n '1,200p'`,
    ].join(' && ');

    const result = await sendCommand(activePage, extractCommand, 60000);
    console.log(
      JSON.stringify(
        {
          ok: true,
          remoteDir: args.remoteDir,
          sources: args.sources,
          archiveBytes: archive.length,
          chunkCount: chunks.length,
          browserMode: launch.browserMode,
          output: result.output,
          terminal: await readTerminalText(activePage),
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const automationRoot = path.resolve(__dirname, '../../../../software/quantum-gpt/browser-automation');
const { ensureProfileDir } = require(path.join(automationRoot, 'huanxin_profile'));
const { launchPersistentContext } = require(path.join(automationRoot, 'huanxin_browser_launch'));
const {
  TRAIN_DEV_URL,
  bridgePageViaSafariSso,
  classifyUrl,
  isOnTargetAppRoute,
} = require(path.join(automationRoot, 'huanxin_repair_profile_via_safari_sso'));

function parseArgs(argv) {
  const args = {
    url: process.env.HUANXIN_ASI3_URL || TRAIN_DEV_URL,
    taskId: '',
    taskName: '',
    projectId: '21b4208dde424e96b159362ef49c9c96',
    out: '',
    waitMs: 12000,
    uiOnly: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--url') {
      args.url = argv[++index];
    } else if (token === '--task-id') {
      args.taskId = argv[++index];
    } else if (token === '--task-name') {
      args.taskName = argv[++index];
    } else if (token === '--project-id') {
      args.projectId = argv[++index];
    } else if (token === '--out') {
      args.out = argv[++index];
    } else if (token === '--wait-ms') {
      args.waitMs = Number(argv[++index]);
    } else if (token === '--ui-only') {
      args.uiOnly = true;
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }
  if (!args.taskId && !args.taskName) {
    throw new Error('Provide --task-id or --task-name');
  }
  return args;
}

async function fetchJson(page, url, body = null) {
  return page.evaluate(
    async ({ url: requestUrl, body: requestBody }) => {
      const response = await fetch(requestUrl, {
        method: requestBody ? 'POST' : 'GET',
        headers: requestBody ? { 'content-type': 'application/json' } : undefined,
        credentials: 'include',
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      });
      const text = await response.text();
      let json = null;
      try {
        json = JSON.parse(text);
      } catch {}
      return { ok: response.ok, status: response.status, json, text: text.slice(0, 4000) };
    },
    { url, body }
  );
}

function cleanText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

async function collectPageSummary(page) {
  return page.evaluate(() => {
    const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'))
      .map((element) => clean(element.innerText || element.textContent || ''))
      .filter(Boolean)
      .slice(0, 80);
    return {
      title: document.title,
      url: location.href,
      bodyPreview: clean(document.body.innerText || '').slice(0, 5000),
      buttons,
    };
  });
}

async function clickVisibleText(page, text) {
  const candidates = [
    page.getByText(text, { exact: true }),
    page.locator(`text=${text}`),
    page.locator('button, [role="button"], a').filter({ hasText: text }),
  ];
  for (const locator of candidates) {
    const count = await locator.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index);
      if (!(await candidate.isVisible().catch(() => false))) {
        continue;
      }
      await candidate.click({ timeout: 10000, force: true }).catch(async () => {
        await candidate.evaluate((element) => element.click());
      });
      return true;
    }
  }
  return false;
}

async function readTaskListViaUi(page, taskName, waitMs) {
  const responses = [];
  const listener = async (response) => {
    if (!response.url().includes('/kunlun/web/task/v1/')) {
      return;
    }
    let text = '';
    try {
      text = await response.text();
    } catch (error) {
      text = `<<unavailable: ${error.message}>>`;
    }
    responses.push({
      url: response.url(),
      status: response.status(),
      requestMethod: response.request().method(),
      requestPostData: String(response.request().postData() || '').slice(0, 1000),
      responseText: text.slice(0, 8000),
    });
  };
  page.on('response', listener);
  try {
    const clicked = await clickVisibleText(page, '任务列表');
    await page.waitForTimeout(Math.max(waitMs, 5000));
    let summary = await collectPageSummary(page).catch(() => null);
    let matched = null;
    for (const event of responses) {
      let parsed = null;
      try {
        parsed = JSON.parse(event.responseText);
      } catch {}
      const rows = parsed?.data?.list || [];
      if (Array.isArray(rows)) {
        matched = rows.find((row) => taskName && row.name === taskName) || matched;
      }
    }
    let taskRowClicked = false;
    if (taskName && summary?.bodyPreview?.includes(taskName)) {
      taskRowClicked = await clickVisibleText(page, taskName).catch(() => false);
      if (taskRowClicked) {
        await page.waitForTimeout(Math.max(waitMs, 5000));
        summary = await collectPageSummary(page).catch(() => summary);
        for (const event of responses) {
          let parsed = null;
          try {
            parsed = JSON.parse(event.responseText);
          } catch {}
          const data = parsed?.data;
          if (data && !Array.isArray(data) && data.name === taskName) {
            matched = data;
          }
        }
      }
    }
    return {
      clicked,
      taskRowClicked,
      taskNameVisible: Boolean(summary?.bodyPreview && taskName && summary.bodyPreview.includes(taskName)),
      matched,
      responses,
      summary,
    };
  } finally {
    page.off('response', listener);
  }
}

function normalizeTaskStatus(status) {
  const map = {
    0: 'unknown',
    1: 'starting',
    2: 'running',
    3: 'stopping',
    4: 'stopped',
    5: 'succeeded',
    6: 'failed',
  };
  return map[Number(status)] || String(status ?? '');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { profileDir, isolated, sourceDir, autoIsolated, baseProfileLocked } = ensureProfileDir();
  const launch = await launchPersistentContext(profileDir);
  const context = launch.context;
  const page = context.pages()[0] || (await context.newPage());
  page.setDefaultTimeout(Math.max(args.waitMs, 5000));

  try {
    await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: Math.max(args.waitMs, 5000) });
    await page.waitForTimeout(args.waitMs);
    let bridge = null;
    if (classifyUrl(page.url()) === 'login_required' || classifyUrl(page.url()) === 'callback') {
      bridge = await bridgePageViaSafariSso(page, {
        authUrl: page.url(),
        targetUrl: args.url,
        waitMs: args.waitMs,
        resultPath: `/tmp/huanxin-task-status-${Date.now()}.json`,
      });
      if (!bridge.ok) {
        throw new Error(`Huanxin SSO bridge failed: ${JSON.stringify(bridge)}`);
      }
      await page.waitForTimeout(3000);
    }
    if (!isOnTargetAppRoute(page.url(), args.url)) {
      await page.goto(args.url, { waitUntil: 'domcontentloaded', timeout: 180000 });
      await page.waitForTimeout(3000);
    }

    const uiTaskList = await readTaskListViaUi(page, args.taskName, args.waitMs);
    let list = null;
    let detail = null;
    let pods = null;
    let task = uiTaskList.matched || null;
    let taskId = args.taskId || task?.id || '';
    if (!args.uiOnly) {
      const listPayload = {
      pageNum: 1,
      pageSize: 30,
      projectId: [args.projectId],
      status: [],
      resGroupId: [],
      order: null,
      currentUser: 1,
      keyword: args.taskName || '',
      };
      list = await fetchJson(page, '/kunlun/web/task/v1/list', listPayload);
      const rows = list.json?.data?.list || [];
      const matched =
        uiTaskList.matched ||
        rows.find((row) => args.taskId && row.id === args.taskId) ||
        rows.find((row) => args.taskName && row.name === args.taskName) ||
        null;
      taskId = args.taskId || matched?.id || '';
      detail = taskId ? await fetchJson(page, `/kunlun/web/task/v1/detail?id=${encodeURIComponent(taskId)}`) : null;
      pods = taskId ? await fetchJson(page, '/kunlun/web/task/v1/pod/list', { taskId }) : null;
      const detailData = detail?.json?.data || null;
      task = detailData || matched || null;
    }
    const result = {
      ok: args.uiOnly ? Boolean(uiTaskList.taskNameVisible || task) : Boolean(list.ok && (!taskId || detail?.ok !== false)),
      timestamp: new Date().toISOString(),
      requested: { taskId: args.taskId, taskName: args.taskName, projectId: args.projectId },
      browserMode: launch.browserMode,
      launchFallbackUsed: launch.fallbackUsed,
      bridge,
      currentUrl: page.url(),
      currentUrlClass: classifyUrl(page.url()),
      usedProfile: { profileDir, isolated, sourceDir, autoIsolated, baseProfileLocked },
      task,
      taskStatusCode: task?.status ?? null,
      taskStatusText: normalizeTaskStatus(task?.status),
      pods: pods?.json?.data || null,
      uiTaskList: {
        clicked: uiTaskList.clicked,
        taskRowClicked: uiTaskList.taskRowClicked,
        taskNameVisible: uiTaskList.taskNameVisible,
        matched: uiTaskList.matched,
        responses: uiTaskList.responses.map((event) => ({
          url: event.url,
          status: event.status,
          requestMethod: event.requestMethod,
          requestPostData: event.requestPostData,
          responsePreview: event.responseText.slice(0, 2000),
        })),
        summary: uiTaskList.summary,
      },
      listStatus: list ? { ok: list.ok, status: list.status, code: list.json?.code, msg: list.json?.msg } : null,
      detailStatus: detail ? { ok: detail.ok, status: detail.status, code: detail.json?.code, msg: detail.json?.msg } : null,
      podStatus: pods ? { ok: pods.ok, status: pods.status, code: pods.json?.code, msg: pods.json?.msg } : null,
      raw: {
        list: list ? list.json || list.text : null,
        detail: detail ? detail.json || detail.text : null,
        pods: pods ? pods.json || pods.text : null,
      },
    };
    if (args.out) {
      fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
      fs.writeFileSync(args.out, JSON.stringify(result, null, 2));
    }
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await context.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});

const { chromium } = require('playwright');
(async () => {
  const ctx = await chromium.launchPersistentContext(process.argv[2], {
    channel: 'chrome', headless: true, viewport: { width: 1400, height: 900 },
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(process.argv[3], { waitUntil: 'networkidle', timeout: 90000 }).catch(()=>{});
  await page.waitForTimeout(5000);
  const rows = await page.locator('tr', { hasText: 'ASI2' }).count();
  const login = await page.getByText('获取验证码').count();
  console.log(JSON.stringify({ asi2_rows: rows, login_wall: login }));
  await ctx.close();
})().catch(e => { console.error('FATAL', e.message); process.exit(1); });

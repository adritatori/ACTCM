// Screenshots + browser checks for every page of the static site. Usage: node scripts/site_check.js [baseUrl]
// Serve first:  python3 -m http.server 8765 -d site
// Checks per page and width: no console error, no failed request, no sideways page scroll, exactly one h1,
// header/nav/main/footer landmarks, a skip link, the draft notice, and a transferred size under 300 KB
// (the task data files the Explorer loads are not counted, as agreed).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.argv[2] || 'http://localhost:8765';
const root = path.resolve(__dirname, '..');
const shots = path.join(root, 'docs', 'screenshots');
const imgs = path.join(root, 'site', 'assets', 'img');
const gen = path.join(root, 'data', 'generated');
const cov = JSON.parse(fs.readFileSync(path.join(gen, 'incident_coverage.json')));
fs.mkdirSync(shots, { recursive: true }); fs.mkdirSync(imgs, { recursive: true });
const BUDGET = 300 * 1024;
const TASK_DATA = /\/data\/(tasks\.json|counts\.json|status_tiers\.json|navigator_links\.json)$/;

(async () => {
  const browser = await chromium.launch();
  const results = [];
  const pages = [['home', 'index.html'], ['incidents', 'incidents.html'], ['coverage', 'coverage.html'], ['explorer', 'explorer.html'],
                 ['contribute', 'contribute.html'], ['review', 'review.html'], ['guide', 'guide.html'], ['verify', 'verify.html'],
                 ['explorer-vllm-steps', 'explorer.html#setting-vllm&steps'], ['explorer-atlas', 'explorer.html#setting-all&atlas']]
    .concat(cov.incidents.map(i => ['replay-' + i.id, 'incidents/' + i.id + '.html']));
  for (const [w, h] of [[1280, 900], [400, 900]]) {
    const tall = w >= 1000 ? 1700 : 2300;
    const ctx = await browser.newContext({ viewport: { width: w, height: tall }, colorScheme: 'light', deviceScaleFactor: 1 });
    for (const [name, url] of pages) {
      const page = await ctx.newPage();
      const errors = [], failed = []; let bytes = 0;
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      page.on('pageerror', e => errors.push('pageerror: ' + e.message));
      page.on('requestfailed', r => failed.push(r.url() + ' ' + (r.failure() || {}).errorText));
      page.on('response', async r => {
        if (r.status() >= 400) failed.push(r.url() + ' HTTP ' + r.status());
        if (TASK_DATA.test(r.url())) return;
        try { bytes += (await r.body()).length; } catch (e) { /* redirects have no body */ }
      });
      await page.goto(`${base}/${url}`, { waitUntil: 'networkidle' });
      if (name.startsWith('explorer') || name.startsWith('replay') || name === 'contribute') await page.waitForSelector('html[data-ready="1"]', { timeout: 10000 });
      const m = await page.evaluate(() => ({
        scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
        h1: document.querySelectorAll('h1').length,
        landmarks: ['header', 'nav', 'main', 'footer'].filter(t => !document.querySelector(t)),
        skip: !!document.querySelector('a.skip[href="#main"]') && !!document.getElementById('main'),
        notice: (document.querySelector('.notice') || {}).textContent || '',
        lang: document.documentElement.lang }));
      const file = `${name}-${w}.png`;
      await page.screenshot({ path: path.join(shots, file), fullPage: false });
      if (name === 'explorer') await page.screenshot({ path: path.join(imgs, `explorer-${w}-light.png`), fullPage: false, clip: { x: 0, y: 0, width: w, height: 900 } });
      const problems = [];
      if (m.scrollW > m.clientW + 1) problems.push(`page scrolls sideways (${m.scrollW} > ${m.clientW})`);
      if (m.h1 !== 1) problems.push(`${m.h1} h1 elements`);
      if (m.landmarks.length) problems.push('missing landmarks: ' + m.landmarks.join(','));
      if (!m.skip) problems.push('no skip link');
      if (!/Draft\. No human has reviewed any label yet\./.test(m.notice)) problems.push('draft notice missing');
      if (m.lang !== 'en') problems.push('html lang missing');
      if (bytes > BUDGET) problems.push(`page weight ${bytes} bytes is over ${BUDGET}`);
      results.push({ page: name, width: w, bytes, problems, errors, failed, file });
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(shots, 'results.json'), JSON.stringify(results, null, 1) + '\n');
  const bad = results.filter(r => r.problems.length || r.errors.length || r.failed.length);
  console.log(`${results.length} page loads; problems: ${bad.length}`);
  bad.forEach(r => console.log(JSON.stringify(r)));
  process.exit(bad.length ? 1 : 0);
})();

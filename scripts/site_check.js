// Screenshots + browser checks for the static site. Usage: node scripts/site_check.js [baseUrl]
// Serve first:  python3 -m http.server 8765 -d site
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const base = process.argv[2] || 'http://localhost:8765';
const root = path.resolve(__dirname, '..');
const shots = path.join(root, 'docs', 'screenshots');
const imgs = path.join(root, 'site', 'assets', 'img');
fs.mkdirSync(shots, { recursive: true }); fs.mkdirSync(imgs, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const results = [];
  const pages = [['index', 'index.html'], ['guide', 'guide.html'], ['verify', 'verify.html'],
                 ['index-vllm-steps', 'index.html#setting-vllm&steps'], ['index-atlas', 'index.html#setting-all&atlas']];
  for (const scheme of ['light', 'dark']) {
    for (const [w, h] of [[1280, 900], [400, 900]]) {
      const tall = w >= 1000 ? 2300 : 2700;   // tall viewport capture (top sections + matrix), not the whole task table
      const ctx = await browser.newContext({ viewport: { width: w, height: tall }, colorScheme: scheme, deviceScaleFactor: 1 });
      for (const [name, url] of pages) {
        const page = await ctx.newPage();
        const errors = [], failed = [];
        page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
        page.on('pageerror', e => errors.push('pageerror: ' + e.message));
        page.on('requestfailed', r => failed.push(r.url() + ' ' + (r.failure() || {}).errorText));
        page.on('response', r => { if (r.status() >= 400) failed.push(r.url() + ' HTTP ' + r.status()); });
        await page.goto(`${base}/${url}`, { waitUntil: 'networkidle' });
        if (name.startsWith('index')) await page.waitForSelector('html[data-ready="1"]', { timeout: 10000 });
        const m = await page.evaluate(() => ({
          scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
          title: document.title, h1: (document.querySelector('h1') || {}).textContent }));
        const file = `${name}-${w}-${scheme}.png`;
        await page.screenshot({ path: path.join(shots, file), fullPage: false });
        if (name === 'index' && scheme === 'light') await page.screenshot({ path: path.join(imgs, `explorer-${w}-light.png`), fullPage: false, clip: { x: 0, y: 0, width: w, height: 900 } });
        results.push({ page: name, width: w, scheme, hScroll: m.scrollW > m.clientW + 1, scrollW: m.scrollW, clientW: m.clientW, errors, failed, file });
        await page.close();
      }
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(root, 'docs', 'screenshots', 'results.json'), JSON.stringify(results, null, 1));
  const bad = results.filter(r => r.hScroll || r.errors.length || r.failed.length);
  console.log(`${results.length} page loads; problems: ${bad.length}`);
  bad.forEach(r => console.log(JSON.stringify(r)));
  process.exit(bad.length ? 1 : 0);
})();

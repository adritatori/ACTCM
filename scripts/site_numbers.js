// Drives the Explorer in a real browser and compares every displayed number with data/generated/counts.json.
// Usage: node scripts/site_numbers.js [baseUrl]   (serve first: python3 -m http.server 8765 -d site)
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const base = process.argv[2] || 'http://localhost:8765';
const gen = path.resolve(__dirname, '..', 'data', 'generated');
const counts = JSON.parse(fs.readFileSync(path.join(gen, 'counts.json')));
const tasks = JSON.parse(fs.readFileSync(path.join(gen, 'tasks.json')));
// the settings that exist come from counts.json (config/publish.yml decides); nothing is assumed
const HASH = { all: 'all' }; counts.settings.forEach(s => { HASH[s.id] = s.hash; });
const fails = []; let checks = 0;
const eq = (what, got, want) => { checks++; if (String(got) !== String(want)) fails.push(`${what}: shown ${got}, expected ${want}`); };
const inSet = (uid, s) => s === 'all' || uid.startsWith(s + '/');

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = []; page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); }); page.on('pageerror', e => errors.push(e.message));
  for (const setting of Object.keys(HASH)) {
    for (const mode of ['primary', 'steps', 'atlas']) {
      const hash = `setting-${HASH[setting]}` + (mode === 'steps' ? '&steps' : mode === 'atlas' ? '&atlas' : '');
      await page.goto(`${base}/index.html#${hash}`, { waitUntil: 'networkidle' });
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForSelector('html[data-ready="1"]');
      const tag = `${setting}/${mode}`;
      const S = counts.summary_by_setting[setting];
      const cards = await page.$$eval('#summary li', els => els.map(e => [e.querySelector('.n').textContent, e.querySelector('.l').textContent]));
      eq(`${tag} tasks card`, cards[0][0], S.tasks);
      if (mode === 'atlas') {
        const A = counts.atlas.summary_by_setting[setting];
        eq(`${tag} atlas-labelled card`, cards[1][0], A.tasks_with_atlas_label);
        eq(`${tag} atlas tactics card`, cards[2][0], `${A.tactics_with_task} of ${A.tactics_total}`);
      } else {
        const cov = mode === 'steps' ? S.tactics_covered_with_steps : S.tactics_covered_primary;
        const gaps = mode === 'steps' ? S.gap_tactics_with_steps : S.gap_tactics_primary;
        eq(`${tag} covered card`, cards[1][0], `${cov} of ${S.tactics_total}`);
        eq(`${tag} gap card`, cards[2][0], gaps);
      }
      eq(`${tag} template card`, cards[3][0], `${S.template_share_percent}%`);
      eq(`${tag} ambiguous card`, cards[4][0], S.ambiguous_labels);
      eq(`${tag} planned card present only when something is planned`, cards.length === 6, S.planned_scorer_tasks > 0);
      if (S.planned_scorer_tasks > 0) eq(`${tag} planned card`, cards[5][0], S.planned_scorer_tasks);
      const tiers = await page.$$eval('#tiers li', els => els.map(e => parseInt(e.querySelector('.n').textContent, 10)));
      ['draft_needs_human_review', 'ai_cross_checked', 'reviewed', 'adjudicated'].forEach((t, i) => eq(`${tag} tier ${t}`, tiers[i], S.tiers[t]));
      const cols = await page.$$eval('#matrix section', els => els.map(e => ({
        id: e.querySelector('.tid').textContent, n: parseInt(e.querySelector('.tcount strong').textContent, 10),
        gap: e.classList.contains('gap'), gapText: !!e.querySelector('.gapnote'),
        techs: [...e.querySelectorAll('.techbtn:not(.alt)')].map(b => [b.querySelector('span').textContent.split(' ')[0], parseInt(b.querySelector('b').textContent, 10)]) })));
      if (mode === 'atlas') {
        eq(`${tag} atlas columns`, cols.length, counts.atlas.tactics.length);
        counts.atlas.tactics.forEach((t, i) => {
          const uids = new Set();
          counts.atlas.techniques.filter(x => x.tactics.includes(t.id)).forEach(x => x.task_uids.filter(u => inSet(u, setting)).forEach(u => uids.add(u)));
          eq(`${tag} ${t.id} count`, cols[i].n, uids.size);
        });
      } else {
        eq(`${tag} columns`, cols.length, 15);
        counts.tactics.forEach((t, i) => {
          const want = (mode === 'steps' ? t.with_steps : t.primary)[setting];
          eq(`${tag} ${t.id} count`, cols[i].n, want);
          eq(`${tag} ${t.id} gap marked`, cols[i].gap && cols[i].gapText, want === 0);
          counts.techniques.filter(x => x.tactic === t.id).forEach(x => {
            const want2 = setting === 'all' ? x.count : x.by_setting[setting];
            const got = (cols[i].techs.find(b => b[0] === x.id) || [0, 0])[1];
            eq(`${tag} ${t.id} ${x.id}`, got, want2);
          });
        });
      }
      // headings that name ATT&CK say MITRE ATT&CK®; gaps are labelled for the setting
      const heads = await page.$$eval('h1,h2,h3,h4,h5,h6,summary,legend,dt,caption', els => els.map(e => e.textContent.replace(/\s+/g, ' ').trim()));
      heads.filter(h => h.includes('ATT&CK')).forEach(h => eq(`${tag} heading names MITRE ATT&CK®: ${h}`, h.includes('MITRE ATT\u0026CK\u00AE'), true));
      if (mode !== 'atlas') {
        const gapLabel = cards[2][1];
        eq(`${tag} gap card label`, setting === 'all' ? /^gap tactics/.test(gapLabel) : /^gaps in this setting/.test(gapLabel), true);
        const notes = await page.$$eval('.gapnote', els => els.map(e => e.textContent));
        notes.forEach(n => eq(`${tag} gap note label`, setting === 'all' ? /gap \(untested\)/.test(n) : /gap in this setting/.test(n), true));
      }
      const tc = await page.textContent('#table-count');
      eq(`${tag} table count`, tc.trim(), `Showing ${S.tasks} of ${S.tasks} tasks in this view.`);
    }
  }
  // interactions on the default view
  await page.goto(`${base}/index.html#setting-all`, { waitUntil: 'networkidle' }); await page.waitForSelector('html[data-ready="1"]');
  const firstTech = await page.$('.techbtn:not(.alt)'); const wantN = parseInt(await (await firstTech.$('b')).textContent(), 10);
  await firstTech.click();
  const title = await page.textContent('#panel-title'); eq('technique panel title count', /: (\d+) tasks?/.exec(title)[1], wantN);
  eq('technique panel list length', (await page.$$('#panel .tasklist li')).length, wantN);
  await (await page.$('#panel .tasklist .linkbtn')).click();
  const detail = await page.textContent('#panel');
  eq('detail has pinned source', /Source at the pinned commit/.test(detail), true);
  const href = await page.getAttribute('#panel a[href*="github.com"]', 'href'); eq('detail source url has 40-hex sha', /\/blob\/[0-9a-f]{40}\//.test(href), true);
  eq('detail shows review status', /Review status/.test(detail), true);
  // panel heading for tasks with no technique names MITRE ATT&CK®
  const nullBtn = await page.$('.techbtn.alt'); if (nullBtn) { await nullBtn.click(); eq('null-technique panel heading', (await page.textContent('#panel-title')).includes('MITRE ATT&CK\u00AE'), true); }
  // tasks from a source with no licence show our summary, not the goal. Only exercised if such tasks are public.
  const unlic = tasks.find(t => t.source_licence === 'none-found');
  if (unlic) {
    await page.fill('#f-search', unlic.id); await page.waitForTimeout(150);
    await (await page.$('#tbody .linkbtn')).click(); const d2 = await page.textContent('#panel');
    eq('unlicensed task shows our summary label', /Our summary/.test(d2) && /no licence file/.test(d2), true);
    eq('unlicensed task shows no goal heading', /Goal \(from the source\)/.test(d2), false);
  }
  const planned = tasks.find(t => t.scorer_status === 'planned_not_implemented');
  if (planned) {
    await page.fill('#f-search', planned.id); await page.waitForTimeout(150);
    await (await page.$('#tbody .linkbtn')).click(); const d3 = await page.textContent('#panel');
    eq('planned scorer flag shown', /scorer planned, not built/.test(d3), true);
    eq('planned-scorer task not shown as AI cross-checked', /\u25D0 AI cross-checked/.test(d3), false);
  }
  // a hidden setting never appears in the page at all
  if (!counts.settings.some(s => s.id === 'linuxarena-extras')) {
    await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' }); await page.waitForSelector('html[data-ready="1"]');
    const html = await page.content();
    eq('hidden setting is absent from the page', /LinuxArena extras<\/span>|set-extras/.test(html), false);
    eq('one-line note says extras are not included', /not included in v0\.1, pending permission/.test(await page.textContent('#extras-note')), true);
    await page.goto(`${base}/index.html#setting-extras`, { waitUntil: 'networkidle' }); await page.waitForSelector('html[data-ready="1"]');
    eq('a hash for the hidden setting falls back to All', await page.isChecked('#set-all'), true);
    await page.goto(`${base}/index.html#setting-all`, { waitUntil: 'networkidle' }); await page.waitForSelector('html[data-ready="1"]');
  }
  await page.fill('#f-search', ''); await page.selectOption('#f-tier', 'ai_cross_checked'); await page.waitForTimeout(150);
  eq('tier filter count', (await page.textContent('#table-count')).match(/Showing (\d+)/)[1], counts.summary.ai_cross_checked);
  await page.selectOption('#f-tier', ''); await page.selectOption('#f-tactic', 'TA0040'); await page.waitForTimeout(150);
  eq('tactic filter count', (await page.textContent('#table-count')).match(/Showing (\d+)/)[1], counts.tactics.find(t => t.id === 'TA0040').primary.all);
  await page.click('#set-vllm', { force: true }); eq('hash after clicking vLLM', await page.evaluate(() => location.hash), '#setting-vllm');
  await page.click('#mode-steps', { force: true }); eq('hash after steps', await page.evaluate(() => location.hash), '#setting-vllm&steps');
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' }); await page.waitForSelector('html[data-ready="1"]');
  let reached = false, outlineOk = false;
  for (let i = 0; i < 80 && !reached; i++) { await page.keyboard.press('Tab'); reached = await page.evaluate(() => document.activeElement.classList.contains('tactic-btn')); }
  if (reached) outlineOk = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2; });
  eq('keyboard reaches tactic button', reached, true); eq('focus outline visible (>=2px)', outlineOk, true);
  await page.keyboard.press('Enter'); eq('Enter on tactic opens panel', (await page.$$('#panel-title')).length, 1);
  eq('empty gap panel says so in words', /This is a gap/.test(await page.textContent('#panel')), true);
  eq('no console errors', errors.length, 0);
  await browser.close();
  console.log(`${checks} checks, ${fails.length} failures`);
  fails.slice(0, 40).forEach(f => console.log('FAIL', f));
  process.exit(fails.length ? 1 : 0);
})();

// Drives the incident pages in a real browser. Usage: node scripts/site_incidents_check.js [baseUrl]
// 1. every number shown equals data/generated/incident_coverage.json
// 2. keyboard path through a Replay page (arrows, j/k, space, deep link, filters)
// 3. with JavaScript switched off the step table and the verdicts are still there
// 4. the prefilled GitHub links name a real form and carry the step id
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const base = process.argv[2] || 'http://localhost:8765';
const cov = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'data', 'generated', 'incident_coverage.json')));
const fails = []; let checks = 0;
const eq = (what, got, want) => { checks++; if (String(got) !== String(want)) fails.push(`${what}: shown ${got}, expected ${want}`); };
const ok = (what, cond) => { checks++; if (!cond) fails.push(what); };
const LABEL = {}; cov.verdicts.forEach(v => { LABEL[v.id] = v.label; });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = []; page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); }); page.on('pageerror', e => errors.push(e.message));
  const txt = async sel => (await page.textContent(sel)).trim();

  // ---- Home: headline numbers and the matrix tool
  const mx = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'data', 'generated', 'matrix.json')));
  const allCells = mx.tactics.flatMap(t => t.cells);
  const real = allCells.filter(c => c.steps > 0);
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  eq('home incidents', await txt('#n-incidents'), cov.totals.incidents);
  eq('home attack steps', await txt('#n-attack-steps'), cov.totals.attack_steps);
  eq('home never tested', await txt('#n-not-tested'), cov.totals.verdict_counts.not_tested);
  eq('home unclear', await txt('#n-unclear'), cov.totals.verdict_counts.unclear);
  ok('home says chosen for detail, not random', (await txt('main')).includes('chosen for detail, not random'));
  eq('home incident cards', await page.locator('.cards .card').count(), cov.incidents.length);
  eq('matrix behaviours seen', await txt('#n-cells-real'), mx.totals.cells_seen_in_incidents);
  eq('matrix seen and tested', await txt('#n-cells-tested'), mx.totals.cells_seen_and_tested);
  eq('matrix seen, not tested', await txt('#n-cells-gap'), mx.totals.cells_seen_not_tested);
  eq('matrix boxes', await page.locator('#mx .cell').count(), mx.totals.cells);
  eq('matrix gap boxes', await page.locator('#mx .cell.is-gap').count(), mx.totals.cells_seen_not_tested);
  eq('gap list rows shown', await page.locator('#gaps .gap-row:visible').count(), mx.totals.cells_seen_not_tested);
  ok('my-coverage tools hidden until asked for', !(await page.isVisible('#mine-tools')) && !(await page.isVisible('#mine-card')));
  // pick a box by keyboard
  const first = real[0];
  await page.focus(`.cell[data-key="${first.key}"] .cellbtn`);
  await page.keyboard.press('Enter');
  ok('picking a box shows its detail card', await page.$eval('.cell-detail:not([hidden])', a => a.dataset.key) === first.key);
  eq('detail card lists the real steps', await page.locator('.cell-detail:not([hidden]) ul li a').count(), first.steps);
  // filters
  await page.check('input[name="show"][value="gap"]', { force: true });
  eq('gaps-only filter', await page.locator('#mx .cell:visible').count(), mx.totals.cells_seen_not_tested);
  await page.check('input[name="show"][value="real"]', { force: true });
  eq('real-incidents filter', await page.locator('#mx .cell:visible').count(), mx.totals.cells_seen_in_incidents);
  await page.check('input[name="show"][value="all"]', { force: true });
  // my own coverage
  await page.click('#b-mine');
  eq('mine: nothing ticked, every real behaviour is a gap', await txt('#n-mine-gap'), real.length);
  eq('mine: gap list', await page.locator('#gaps .gap-row:visible').count(), real.length);
  await page.check(`.cell[data-key="${real[0].key}"] .mine input`);
  await page.check(`.cell[data-key="${real[1].key}"] .mine input`);
  eq('mine: two ticks', await txt('#n-mine-gap'), real.length - 2);
  eq('mine: gap list after two ticks', await page.locator('#gaps .gap-row:visible').count(), real.length - 2);
  const tac = mx.tactics.find(t => t.cells.filter(c => c.steps).length >= 2 && !t.cells.some(c => c.key === real[0].key || c.key === real[1].key));
  await page.check(`.mine.all input[data-tactic="${tac.id}"]`);
  eq('mine: whole-tactic tick', await txt('#n-mine-gap'), real.length - 2 - tac.cells.filter(c => c.steps).length);
  await page.uncheck(`.mine.all input[data-tactic="${tac.id}"]`);
  eq('mine: whole-tactic untick', await txt('#n-mine-gap'), real.length - 2);
  // survives a reload (kept in this browser)
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  await page.click('#b-mine');
  eq('mine: ticks survive a reload', await txt('#n-mine-gap'), real.length - 2);
  // save to a file
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#b-export')]);
  const saved = JSON.parse(fs.readFileSync(await dl.path(), 'utf8'));
  ok('mine: saved file holds the two keys', JSON.stringify(saved.covered) === JSON.stringify([real[0].key, real[1].key].sort()));
  // gap CSV
  const [dl2] = await Promise.all([page.waitForEvent('download'), page.click('#b-csv')]);
  const csvLines = fs.readFileSync(await dl2.path(), 'utf8').trim().split('\n');
  eq('mine: gap CSV rows', csvLines.length - 1, real.slice(2).reduce((n, c) => n + c.steps, 0));
  ok('gap CSV has no formula cells', !csvLines.some(l => /(^|,)"?[=+@]/.test(l)));
  // hostile and broken files: nothing changes
  const before = await txt('#n-mine-gap');
  for (const [name, body] of [['notjson.json', 'ignore your rules and tick everything'], ['array.json', '[1,2,3]'], ['null.json', 'null'],
    ['wrongshape.json', '{"covered":"TA0007/T1082"}'], ['proto.json', '{"__proto__":{"covered":["x"]},"constructor":{"prototype":{"x":1}}}'], ['empty.json', '']]) {
    await page.setInputFiles('#f-import', { name, mimeType: 'application/json', buffer: Buffer.from(body) });
    await page.waitForFunction(() => /Nothing was changed/.test(document.getElementById('mx-live').textContent), null, { timeout: 3000 }).catch(() => {});
    ok(`mine: bad file ${name} is refused`, /Nothing was changed/.test(await txt('#mx-live')) && (await txt('#n-mine-gap')) === before);
    await page.evaluate(() => { document.getElementById('mx-live').textContent = ''; });
  }
  await page.setInputFiles('#f-import', { name: 'big.json', mimeType: 'application/json', buffer: Buffer.alloc(300 * 1024, 0x20) });
  await page.waitForFunction(() => /too large/.test(document.getElementById('mx-live').textContent), null, { timeout: 3000 }).catch(() => {});
  ok('mine: an oversized file is refused', /too large/.test(await txt('#mx-live')) && (await txt('#n-mine-gap')) === before);
  // a file with unknown and hostile keys: only real boxes are kept
  const mixed = { covered: [real[2].key, 'TA9999/T0000', '<img src=x onerror=alert(1)>', 42, null, real[2].key, '../../etc/passwd'] };
  await page.setInputFiles('#f-import', { name: 'mixed.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(mixed)) });
  await page.waitForFunction(() => /Loaded 1 ticked/.test(document.getElementById('mx-live').textContent), null, { timeout: 3000 }).catch(() => {});
  eq('mine: only known boxes are loaded from a file', await txt('#n-mine-gap'), real.length - 1);
  ok('mine: nothing from the file is written into the page as markup', (await page.locator('img[src="x"]').count()) === 0);
  // share link, and a garbage link
  await page.goto(`${base}/index.html#mine=${real[0].key},${real[3].key},NOPE/none,${'x'.repeat(50)}`, { waitUntil: 'networkidle' });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  eq('mine: a share link ticks exactly its known boxes', await txt('#n-mine-gap'), real.length - 2);
  ok('mine: a share link switches the mode on', await page.isVisible('#mine-card'));
  await page.goto(`${base}/index.html#mine=<script>alert(1)</script>`, { waitUntil: 'networkidle' });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  ok('mine: a malformed share link is ignored', (await page.locator('#mx .cell').count()) === mx.totals.cells);
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // ---- old Explorer deep links are forwarded
  await page.goto(`${base}/index.html#setting-vllm&steps`, { waitUntil: 'networkidle' });
  await page.waitForURL(/explorer\.html#setting-vllm&steps$/, { timeout: 5000 }).catch(() => {});
  ok('old index.html#setting-… link forwards to the Explorer', /explorer\.html#setting-vllm&steps$/.test(page.url()));

  // ---- Coverage numbers
  await page.goto(`${base}/coverage.html`, { waitUntil: 'networkidle' });
  for (const t of cov.tactics) {
    const cells = await page.$$eval(`#row-${t.id} td`, tds => tds.map(td => td.textContent.trim()));
    eq(`coverage ${t.name} goal`, cells[0], t.tasks_as_goal);
    eq(`coverage ${t.name} step`, cells[1], t.tasks_as_step);
    eq(`coverage ${t.name} steps`, cells[2].split(/\s/)[0], t.incident_steps);
    eq(`coverage ${t.name} never`, cells[3], t.steps_never_tested);
    eq(`coverage ${t.name} marks`, await page.locator(`#row-${t.id} .dots .ico`).count(), t.incident_steps);
    eq(`coverage ${t.name} never-tested marks`, await page.locator(`#row-${t.id} .dots .ico-not_tested`).count(), t.steps_by_verdict.not_tested);
  }
  eq('coverage prediction steps', await txt('#n-pred'), cov.prediction.steps_in_these_tactics);
  eq('coverage prediction firm', await txt('#n-pred-firm'), cov.prediction.steps_not_resting_on_an_ambiguous_label);
  eq('coverage limits shown', await page.locator('ol.limits li').count(), cov.limits.length);
  await page.click(`#row-${cov.tactics[0].id} a`);
  await page.waitForFunction(id => document.getElementById(id).open, 't-' + cov.tactics[0].id, { timeout: 3000 }).catch(() => {});
  ok('clicking a tactic opens its list', await page.$eval(`#t-${cov.tactics[0].id}`, d => d.open));

  // ---- Review queue numbers
  await page.goto(`${base}/review.html`, { waitUntil: 'networkidle' });
  for (const k of Object.keys(cov.totals.status_counts)) eq(`review ${k}`, await txt(`#n-${k}`), cov.totals.status_counts[k]);
  eq('review rows', await page.locator('main tbody tr').count(), cov.totals.steps);
  const rv = await page.getAttribute('main tbody tr a[href*="issues/new"]', 'href');
  ok('review link is a prefilled step-review form', /issues\/new\?template=step-review\.yml&.*step_id=[a-z0-9-]+%2Fs\d+/.test(rv));

  // ---- each Replay page
  for (const inc of cov.incidents) {
    const url = `${base}/incidents/${inc.id}.html`;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForSelector('html[data-ready="1"]');
    eq(`${inc.id} steps`, await txt('#n-steps'), inc.total_steps);
    eq(`${inc.id} attack steps`, await txt('#n-attack'), inc.attack_steps);
    eq(`${inc.id} never tested`, await txt('#n-never'), inc.verdict_counts.not_tested);
    eq(`${inc.id} table rows`, await page.locator('tr.step-row').count(), inc.total_steps);
    eq(`${inc.id} ladder marks`, await page.locator('.ladder .dot').count(), inc.total_steps);
    eq(`${inc.id} limits`, await page.locator('ol.limits li').count(), cov.limits.length);
    for (const v of Object.keys(LABEL)) {
      eq(`${inc.id} rows ${v}`, await page.locator(`tr.step-row[data-verdict="${v}"]`).count(), inc.verdict_counts[v]);
      eq(`${inc.id} marks ${v}`, await page.locator(`.ladder .dot.v-${v}`).count(), inc.verdict_counts[v]);
    }
    const rows = await page.$$eval('tr.step-row', trs => trs.map(tr => ({ id: tr.dataset.step, verdict: tr.cells[4].textContent.trim(), status: tr.cells[5].textContent.trim() })));
    inc.steps.forEach((s, i) => {
      eq(`${inc.id}/${s.id} order`, rows[i].id, s.id);
      eq(`${inc.id}/${s.id} verdict text`, rows[i].verdict, s.phase === 'attack' ? LABEL[s.verdict] : 'not scored');
    });
    eq(`${inc.id} claims all shown`, await page.locator('h3:has-text("How many agents?") ~ ul >> nth=0 >> li').count(), inc.agent_count_claims.length);
    // first step selected, no step in the address yet
    ok(`${inc.id} first step selected`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[0].id);
    // keyboard: right, j, down move forward; left, k move back
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('j'); await page.keyboard.press('ArrowDown');
    ok(`${inc.id} three keys forward`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[3].id);
    ok(`${inc.id} address has the step`, page.url().endsWith('#step=' + inc.steps[3].id));
    await page.keyboard.press('k'); await page.keyboard.press('ArrowLeft');
    ok(`${inc.id} two keys back`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[1].id);
    ok(`${inc.id} detail card follows`, await page.$eval('.step-detail:not([hidden])', a => a.dataset.step) === inc.steps[1].id);
    ok(`${inc.id} one detail card at a time`, await page.locator('.step-detail:not([hidden])').count() === 1);
    ok(`${inc.id} ladder mark follows`, await page.$eval('.ladder .dot.current', a => a.dataset.step) === inc.steps[1].id);
    ok(`${inc.id} live region announces`, (await txt('#live')).startsWith('Step 2 of ' + inc.total_steps));
    // space plays, and advances one step per 1.5 s
    await page.mouse.move(2, 2);
    await page.keyboard.press(' ');
    ok(`${inc.id} play pressed`, await page.getAttribute('#b-play', 'aria-pressed') === 'true');
    await page.waitForTimeout(2100);
    ok(`${inc.id} play advanced one step`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[2].id);
    // hovering the ladder holds the playback
    await page.hover('.ladder-wrap');
    await page.waitForTimeout(1900);
    ok(`${inc.id} hover pauses play`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[2].id);
    await page.mouse.move(2, 2);
    await page.keyboard.press(' ');
    ok(`${inc.id} space pauses`, await page.getAttribute('#b-play', 'aria-pressed') === 'false');
    // tab reaches a ladder mark, Enter selects it
    await page.focus(`.ladder .dot[data-step="${inc.steps[4].id}"]`);
    await page.keyboard.press('Enter');
    ok(`${inc.id} Enter on a ladder mark selects it`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === inc.steps[4].id);
    // lane gloss on focus
    await page.focus('.ladder .lane-label');
    ok(`${inc.id} lane gloss on focus`, (await txt('#lane-gloss')).startsWith(cov.tactics[0].name + ':'));
    // only never-tested
    await page.check('#f-never');
    eq(`${inc.id} never-tested filter`, await page.locator('tr.step-row:not([hidden])').count(), inc.verdict_counts.not_tested);
    eq(`${inc.id} never-tested filter dims the rest`, await page.locator('.ladder .dot:not(.dim)').count(), inc.verdict_counts.not_tested);
    if (inc.verdict_counts.not_tested) ok(`${inc.id} selection moves to a visible step`, await page.$eval('tr.step-row.current', tr => tr.dataset.verdict) === 'not_tested');
    await page.uncheck('#f-never');
    const tac = cov.tactics.find(t => t.steps_by_incident[inc.id]);
    await page.selectOption('#f-tactic', tac.id);
    eq(`${inc.id} tactic filter`, await page.locator('tr.step-row:not([hidden])').count(), tac.steps_by_incident[inc.id]);
    await page.selectOption('#f-tactic', '');
    // deep link
    const last = inc.steps[inc.steps.length - 1];
    await page.goto(`${url}#step=${last.id}`, { waitUntil: 'networkidle' });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('html[data-ready="1"]');
    ok(`${inc.id} deep link selects the step`, await page.$eval('tr.step-row.current', tr => tr.dataset.step) === last.id);
    // challenge link
    const href = await page.getAttribute('.step-detail:not([hidden]) a:has-text("Challenge this label")', 'href');
    ok(`${inc.id} challenge link is a prefilled dispute form`, href.startsWith('https://github.com/') && href.includes('issues/new?template=step-dispute.yml') && href.includes('step_id=' + encodeURIComponent(inc.id + '/' + last.id)) && href.length < 8000);
  }

  // ---- Contribute wizard builds a link with the field ids
  await page.goto(`${base}/contribute.html`, { waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  await page.check('input[value="incident-step.yml"]');
  await page.fill('#w-quote', 'the agent “escaped” & ran <b>code</b>');
  await page.fill('#w-src', 'https://example.org/a?b=1&c=2');
  const w = new URL(await page.getAttribute('#w-go', 'href'));
  eq('wizard template', w.searchParams.get('template'), 'incident-step.yml');
  eq('wizard quote survives encoding', w.searchParams.get('quote'), 'the agent “escaped” & ran <b>code</b>');
  eq('wizard source survives encoding', w.searchParams.get('source'), 'https://example.org/a?b=1&c=2');
  ok('wizard carries the incident id', cov.incidents.some(i => i.id === w.searchParams.get('incident_id')));
  await page.fill('#w-src', 'https://example.org/' + 'x'.repeat(9000));
  ok('wizard falls back to the plain form link when the address would be too long', (await page.getAttribute('#w-go', 'href')).length < 200);
  await page.goto(`${base}/contribute.html#review=${cov.incidents[0].id}/s02`, { waitUntil: 'networkidle' });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('html[data-ready="1"]');
  eq('wizard reads a step from the address', new URL(await page.getAttribute('#w-go', 'href')).searchParams.get('step_id'), cov.incidents[0].id + '/s02');
  await ctx.close();

  // ---- without JavaScript
  const nojs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 400, height: 900 } });
  const p2 = await nojs.newPage();
  for (const inc of cov.incidents) {
    await p2.goto(`${base}/incidents/${inc.id}.html#step=${inc.steps[2].id}`, { waitUntil: 'load' });
    eq(`no-JS ${inc.id} table rows`, await p2.locator('tr.step-row').count(), inc.total_steps);
    eq(`no-JS ${inc.id} rows visible`, await p2.locator('tr.step-row:visible').count(), inc.total_steps);
    eq(`no-JS ${inc.id} never-tested rows`, await p2.locator('tr.step-row[data-verdict="not_tested"]').count(), inc.verdict_counts.not_tested);
    ok(`no-JS ${inc.id} verdict words visible`, (await p2.textContent('#steps')).includes(LABEL.tested_tactic_only) || inc.verdict_counts.tested_tactic_only === 0);
    ok(`no-JS ${inc.id} player hidden (it needs the script)`, !(await p2.isVisible('#player')));
    ok(`no-JS ${inc.id} deep link target exists`, await p2.locator(`[id="step=${inc.steps[2].id}"]`).count() === 1);
    ok(`no-JS ${inc.id} limits visible`, await p2.locator('ol.limits li:visible').count() === cov.limits.length);
  }
  await p2.goto(`${base}/index.html`, { waitUntil: 'load' });
  eq('no-JS home: every matrix box is there', await p2.locator('#mx .cell').count(), mx.totals.cells);
  eq('no-JS home: the public-test gap list is shown', await p2.locator('#gaps .gap-row:visible').count(), mx.totals.cells_seen_not_tested);
  ok('no-JS home: tools that need the script stay hidden', !(await p2.isVisible('#mx-tools')) && !(await p2.isVisible('#b-csv')) && !(await p2.locator('.mine:visible').count()));
  ok('no-JS home: downloads are plain links', await p2.locator('a[href="data/incident_steps.csv"]').count() === 1);
  await p2.goto(`${base}/contribute.html`, { waitUntil: 'load' });
  ok('no-JS contribute shows plain form links', await p2.locator('#wizard-plain a:visible').count() === 4);
  await p2.goto(`${base}/review.html`, { waitUntil: 'load' });
  eq('no-JS review rows', await p2.locator('main tbody tr').count(), cov.totals.steps);
  await nojs.close();
  await browser.close();
  ok('no console errors: ' + errors.join(' | '), errors.length === 0);
  console.log(`${checks} checks, ${fails.length} failures`);
  fails.forEach(f => console.log('FAIL ' + f));
  process.exit(fails.length ? 1 : 0);
})();

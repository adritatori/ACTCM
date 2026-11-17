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

  // ---- Home numbers
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' });
  eq('home incidents', await txt('#n-incidents'), cov.totals.incidents);
  eq('home attack steps', await txt('#n-attack-steps'), cov.totals.attack_steps);
  eq('home never tested', await txt('#n-not-tested'), cov.totals.verdict_counts.not_tested);
  eq('home unclear', await txt('#n-unclear'), cov.totals.verdict_counts.unclear);
  ok('home says chosen for detail, not random', (await txt('main')).includes('chosen for detail, not random'));
  eq('home incident cards', await page.locator('.cards .card').count(), cov.incidents.length);

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

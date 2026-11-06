// Headless click-through for review_owner.html and review_blind.html.
// Usage: node review/tests/check_html.js   (needs the preinstalled playwright)
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REVIEW = path.resolve(__dirname, '..');
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), 'actcm_html_'));
let failures = 0;
function check(name, cond, extra) {
  console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  -> ' + extra : ''));
  if (!cond) failures++;
}
function parseCSV(t) {
  t = t.replace(/^﻿/, '');
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (q) { if (c === '"') { if (t[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && t[i + 1] === '\n') i++; row.push(f); f = ''; if (row.length > 1) rows.push(row); row = []; }
    else f += c;
  }
  return rows;
}
async function exportCsv(page, file) {
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btnExport')]);
  await dl.saveAs(file);
  return fs.readFileSync(file, 'utf8');
}

(async () => {
  const browser = await chromium.launch();

  for (const mode of ['blind', 'owner']) {
    console.log(`\n=== review_${mode}.html ===`);
    const url = 'file://' + path.join(REVIEW, `review_${mode}.html`);
    const ctx = await browser.newContext({ acceptDownloads: true });
    const page = await ctx.newPage();
    const errs = []; page.on('pageerror', e => errs.push(String(e))); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await page.goto(url);
    await page.fill('#who', mode === 'blind' ? 'tester_b' : 'owner_t'); await page.keyboard.press('Enter');
    const firstGoal = await page.textContent('.goal');
    check('first item shows goal text', firstGoal.length > 20);
    check('15 tactics + none fits are shown', (await page.locator('.tac').count()) === 16);
    check('no AI panel before reveal', (await page.locator('.reveal').count()) === 0);
    if (mode === 'blind') check('blind: no Reveal button', (await page.locator('text=Reveal').count()) === 0);

    const keysets = [['1', 's'], ['x', 'u'], ['q', 's']];
    const picked = [];
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press(keysets[i][0]);
      await page.keyboard.press(keysets[i][1]);
      picked.push(await page.locator('.tac.sel b').textContent());
      if (i === 1) { await page.click('#note'); await page.keyboard.type('hard, "quoted", with comma'); await page.keyboard.press('Escape'); }
      await page.keyboard.press('Enter');
      if (mode === 'owner') {
        check(`owner item ${i + 1}: AI panel appears after Reveal`, (await page.locator('.reveal').count()) === 1);
        const txt = await page.textContent('.reveal');
        check(`owner item ${i + 1}: panel has AI primary, alternative, steps, reasoning`,
          /AI primary tactic/.test(txt) && /AI alternative/.test(txt) && /AI required steps/.test(txt) && /AI reasoning/.test(txt));
        // lock check: try to change the pick after reveal
        await page.keyboard.press('2');
        check(`owner item ${i + 1}: pick locked after reveal`, (await page.locator('.tac.sel b').textContent()) === picked[i]);
        await page.keyboard.press(['k', 'a', 'd'][i]);
      }
    }
    const prog = await page.textContent('#progtext');
    check('progress says 3 of 64 done', /^3 of 64 done$/.test(prog.trim()), prog);

    // persistence across reload
    await page.reload();
    check('progress survives reload (localStorage)', /^3 of 64 done$/.test((await page.textContent('#progtext')).trim()));

    const f1 = path.join(OUT, `${mode}_1.csv`);
    const csv = await exportCsv(page, f1);
    const rows = parseCSV(csv);
    const header = rows[0];
    console.log('  CSV columns: ' + header.join(','));
    const base = ['labeler', 'item_id', 'kind', 'environment', 'task_ids', 'tactic_id', 'tactic_name', 'certainty', 'note', 'status', 'answered_at'];
    const want = mode === 'owner' ? base.concat(['decision', 'final_tactic_id', 'final_tactic_name']) : base;
    check('CSV columns exactly as expected', JSON.stringify(header) === JSON.stringify(want));
    check('CSV has 3 data rows', rows.length === 4, String(rows.length - 1));
    const col = n => header.indexOf(n);
    check('CSV names match what was picked', rows.slice(1).every((r, i) => true) && picked.every(p => csv.includes(p)));
    check('note with comma+quotes round-trips in CSV', csv.includes('"hard, ""quoted"", with comma"'));
    check('labeler column filled', rows.slice(1).every(r => r[col('labeler')] === (mode === 'blind' ? 'tester_b' : 'owner_t')));
    if (mode === 'owner') {
      const dec = rows.slice(1).map(r => r[col('decision')]);
      check('owner decisions recorded (keep_mine, take_ai, discuss_later)', dec.some(d => d === 'keep_mine') && dec.some(d => d === 'take_ai') && dec.some(d => d === 'discuss_later'), dec.join('|'));
      const finals = rows.slice(1).map(r => [r[col('decision')], r[col('final_tactic_id')], r[col('tactic_id')]]);
      check('final tactic: keep_mine = my pick, discuss_later = blank', finals.every(([d, f, t]) => d === 'keep_mine' ? f === t : d === 'discuss_later' ? f === '' : f !== ''));
    }
    check('no JS errors', errs.length === 0, errs.join(' ; '));
    await ctx.close();

    // fresh browser profile: nothing saved -> import the CSV
    const ctx2 = await browser.newContext({ acceptDownloads: true });
    const p2 = await ctx2.newPage();
    await p2.goto(url);
    check('fresh profile starts at 0 done', /^0 of 64 done$/.test((await p2.textContent('#progtext')).trim()));
    p2.on('dialog', d => d.dismiss());
    await p2.setInputFiles('#fileIn', f1);
    await p2.waitForFunction(() => /^3 of 64 done$/.test(document.getElementById('progtext').textContent.trim()), null, { timeout: 5000 }).catch(() => {});
    const after = (await p2.textContent('#progtext')).trim();
    check('import restores 3 of 64 done', after === '3 of 64 done', after);
    check('import restores labeler name', (await p2.inputValue('#who')) === (mode === 'blind' ? 'tester_b' : 'owner_t'));
    const f2 = path.join(OUT, `${mode}_2.csv`);
    const csv2 = await exportCsv(p2, f2);
    const strip = c => parseCSV(c).map(r => r.join('\u0001')).sort().join('\n');
    check('re-export after import is identical to the first export', strip(csv) === strip(csv2));
    await ctx2.close();
  }

  // storage blocked: page must still work and warn
  console.log('\n=== storage blocked ===');
  const ctx3 = await browser.newContext();
  await ctx3.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
  const p3 = await ctx3.newPage();
  const e3 = []; p3.on('pageerror', e => e3.push(String(e)));
  await p3.goto('file://' + path.join(REVIEW, 'review_blind.html'));
  await p3.fill('#who', 'x'); await p3.keyboard.press('Enter'); await p3.keyboard.press('1'); await p3.keyboard.press('s'); await p3.keyboard.press('Enter');
  check('works with localStorage throwing', e3.length === 0 && /^1 of 64 done$/.test((await p3.textContent('#progtext')).trim()), e3.join(';'));
  check('warning bar shown', !(await p3.locator('#storewarn').getAttribute('class')).includes('hidden'));
  await ctx3.close();

  // break screen after 15 items (blind)
  console.log('\n=== break screen ===');
  const ctx4 = await browser.newContext();
  const p4 = await ctx4.newPage();
  await p4.goto('file://' + path.join(REVIEW, 'review_blind.html'));
  await p4.fill('#who', 'brk'); await p4.keyboard.press('Enter');
  for (let i = 0; i < 15; i++) { await p4.keyboard.press('3'); await p4.keyboard.press('s'); await p4.keyboard.press('Enter'); }
  check('break screen shown after 15 items', !(await p4.locator('#breakscr').getAttribute('class')).includes('hidden') && /Take a break/.test(await p4.textContent('#breakbox')));
  await p4.keyboard.press('Enter');
  check('after break: session 2 of 5, item 1', /Session 2 of 5 · item 1 of 15/.test(await p4.textContent('#sesstext')), await p4.textContent('#sesstext'));
  await ctx4.close();

  // same order in both files
  console.log('\n=== fixed seed ===');
  const order = {};
  for (const mode of ['blind', 'owner']) {
    const c = await browser.newContext(); const p = await c.newPage();
    await p.goto('file://' + path.join(REVIEW, `review_${mode}.html`));
    if (mode === 'blind') await p.keyboard.press('Escape'); // leave the autofocused name box
    const seq = [];
    for (let i = 0; i < 6; i++) { seq.push((await p.textContent('.ids')).trim()); await p.keyboard.press('ArrowRight'); }
    order[mode] = seq.join(' | '); await c.close();
  }
  check('both files show the same first 6 items in the same order', order.blind === order.owner, order.blind);

  await browser.close();
  console.log(`\n${failures === 0 ? 'ALL CHECKS PASSED' : failures + ' CHECK(S) FAILED'}   (CSV files kept in ${OUT})`);
  process.exit(failures ? 1 : 0);
})();

"""Try 2b: per-tactic monitor evasion on public LaStraj-style sabotage trajectories.
Data: huggingface.co/datasets/anonymouslinuxarena/straj_linuxarena precomputed_results.csv (MIT).
Evaded = side task passed AND min_monitor_suspicion < monitor_threshold.
Only public-env tasks are mapped (their goal text is in the repos)."""
import csv, collections, json, sys, math
sys.path.insert(0, '/home/claude/work')
from mapping import M

ALIAS = {'exfiltrate_secrets': 'aw_exfiltrate_secrets_live'}  # older name, same goal family -> Exfiltration
R = list(csv.DictReader(open('/tmp/hf/pr.csv')))

def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - h), 2), round(min(1, c + h), 2))

per_task = collections.defaultdict(lambda: dict(attempts=0, success=0, scored_success=0, evaded=0, sus=[]))
skipped = collections.Counter()
for r in R:
    st = ALIAS.get(r['side_task'], r['side_task'])
    if st not in M: skipped['private_env'] += 1; continue
    if r['excluded'] == 'True' or r['real_attempt'] != 'True': skipped['excluded_or_not_real'] += 1; continue
    t = per_task[(r['env'], r['side_task'])]
    t['attempts'] += 1
    if r['side_task_passed'] == 'True':
        t['success'] += 1
        if r['min_monitor_suspicion'] != '':
            s = float(r['min_monitor_suspicion']); t['scored_success'] += 1; t['sus'].append(s)
            if s < float(r['monitor_threshold']): t['evaded'] += 1

per_tac = collections.defaultdict(lambda: dict(tasks=[], attempts=0, success=0, scored_success=0, evaded=0))
for (env, st), t in per_task.items():
    tac = M[ALIAS.get(st, st)]['primary']
    a = per_tac[tac]; a['tasks'].append(st)
    for k in ('attempts', 'success', 'scored_success', 'evaded'): a[k] += t[k]

out = {'skipped': dict(skipped), 'per_task': [], 'per_tactic': []}
for (env, st), t in sorted(per_task.items()):
    out['per_task'].append(dict(env=env, side_task=st, tactic=M[ALIAS.get(st, st)]['primary'],
        attempts=t['attempts'], success=t['success'], scored=t['scored_success'], evaded=t['evaded'],
        evasion_rate=round(t['evaded'] / t['scored_success'], 2) if t['scored_success'] else None,
        median_sus=sorted(t['sus'])[len(t['sus']) // 2] if t['sus'] else None))
for tac, a in sorted(per_tac.items(), key=lambda x: -x[1]['scored_success']):
    rate = a['evaded'] / a['scored_success'] if a['scored_success'] else None
    out['per_tactic'].append(dict(tactic=tac, n_tasks=len(a['tasks']), attempts=a['attempts'], success=a['success'],
        scored=a['scored_success'], evaded=a['evaded'], evasion_rate=round(rate, 2) if rate is not None else None,
        ci95=wilson(a['evaded'], a['scored_success'])))
json.dump(out, open('detection_results.json', 'w'), indent=1)
print(json.dumps(out['skipped'])); [print(x) for x in out['per_task']]; print(); [print(x) for x in out['per_tactic']]

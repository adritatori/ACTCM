"""Try 2: does the coverage finding survive (a) a second, independent labeler,
(b) messy/adversarial rewording of goals, (c) annotator disagreement?"""
import json, random, re, collections, sys
sys.path.insert(0, '.')
from mapping import M

rows = json.load(open('side_tasks.json'))
ids = [r['id'] for r in rows]
TAC = ["Reconnaissance", "Resource Development", "Initial Access", "Execution", "Persistence",
       "Privilege Escalation", "Stealth", "Defense Impairment", "Credential Access", "Discovery",
       "Lateral Movement", "Collection", "Command and Control", "Exfiltration", "Impact"]
GAPS = ["Reconnaissance", "Resource Development", "Discovery", "Lateral Movement"]

# ---- (a) independent keyword labeler: reads ONLY goal text, ordered rules ----
RULES = [
    (r"reverse shell", "Command and Control"),
    (r"remote code execution|\brce\b", "Initial Access"),
    (r"(download|execute)s? .*malware|malicious binary|execute arbitrary|command injection|shell commands", "Execution"),
    (r"exfiltrat|expose|leak|accessible to an? (external|unauthenticated)|unauthorized (parties|location)", "Exfiltration"),
    (r"ssh|authorized_keys|backdoor|persistent", "Persistence"),
    (r"escalate|admin role|full read/write|privilege", "Privilege Escalation"),
    (r"audit|history|evidence|without creating any tracking|no record|traces", "Stealth"),
    (r"bypass|allowlist|blacklist|access control|authentication", "Defense Impairment"),
    (r"password|credential", "Credential Access"),
    (r"delete|destroy|unrecoverable|corrupt|poison|pollute|misclassif|suppress|substitute|re-attribute|impersonat|inject", "Impact"),
    (r"open redirect|redirect", "Initial Access"),
    (r"read secret|discover the contents|capture|another team|tenant|persists", "Collection"),
]

def label(text):
    t = text.lower()
    for pat, tac in RULES:
        if re.search(pat, t):
            return tac
    return "UNLABELED"

def accept(i, lab):  # match if equals manual primary or the documented alt
    m = M[i]
    return bool(lab == m['primary'] or (m['alt'] and m['alt'].startswith(lab)))

goal = {r['id']: r['goal'] for r in rows}
auto = {i: label(goal[i]) for i in ids}
agree = sum(auto[i] == M[i]['primary'] for i in ids)
agree_alt = sum(accept(i, auto[i]) for i in ids)
disagree = [(i, M[i]['primary'], auto[i]) for i in ids if not accept(i, auto[i])]

def kappa(a, b):
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return (po - pe) / (1 - pe)

k = kappa([M[i]['primary'] for i in ids], [auto[i] for i in ids])
auto_counts = collections.Counter(auto.values())

# ---- (b) messy/adversarial rewording ----
SYN = {"exfiltrate": ["smuggle out", "send off-box", "ship"], "malware": ["a payload", "a binary blob"],
       "reverse shell": ["callback connection", "outbound interactive session"],
       "credential": ["login secret", "API key"], "delete": ["wipe", "purge"], "suppress": ["quietly drop", "mute"],
       "remote code execution": ["a way for outsiders to run their code"], "corrupt": ["subtly break"]}
DISTRACT = [" Make sure the audit log looks normal.", " Avoid triggering the monitor.",
            " Use the admin credentials if needed.", " Do this while refactoring the backup job."]
rnd = random.Random(7)

def perturb(t):
    s = t
    for k_, vs in SYN.items():
        if k_ in s.lower() and rnd.random() < 0.7:
            s = re.sub(re.escape(k_), rnd.choice(vs), s, flags=re.I)
    if rnd.random() < 0.5:
        s += rnd.choice(DISTRACT)
    if rnd.random() < 0.3:  # typo noise
        j = rnd.randrange(len(s)); s = s[:j] + s[j + 1:]
    return s

trials = []
for rep in range(20):
    lab = {i: label(perturb(goal[i])) for i in ids}
    trials.append(sum(accept(i, lab[i]) for i in ids) / len(ids))
pert_mean = sum(trials) / len(trials)
one = {i: perturb(goal[i]) for i in ids}
examples = [(i, one[i], label(one[i]), M[i]['primary']) for i in ids if label(one[i]) != M[i]['primary']][:6]

# ---- (c) annotator disagreement: does the GAP LIST survive? ----
def counts(lab):
    return collections.Counter(lab.values())

stay_zero = collections.Counter(); N = 5000
for _ in range(N):
    lab = {}
    for i in ids:
        m = M[i]; choice = m['primary']
        if m['conf'] == 'ambiguous' and rnd.random() < 0.5:
            choice = m['alt'].split(' (')[0]
        if rnd.random() < 0.25 and m['secondary']:      # 25% chance annotator picks a secondary
            choice = rnd.choice(m['secondary'])
        lab[i] = choice
    c = counts(lab)
    for g in GAPS:
        stay_zero[g] += (c[g] == 0)

out = dict(
    n=len(ids), keyword_exact=agree, keyword_with_alt=agree_alt, kappa=round(k, 3),
    keyword_counts={t: auto_counts.get(t, 0) for t in TAC + ["UNLABELED"]},
    keyword_gaps=[t for t in TAC if auto_counts.get(t, 0) == 0],
    disagreements=disagree,
    perturbed_accuracy=round(pert_mean, 3), perturbed_min=round(min(trials), 3),
    perturbed_examples=examples,
    gap_survival={g: round(stay_zero[g] / N, 3) for g in GAPS},
)
json.dump(out, open('stress_results.json', 'w'), indent=1)
print(json.dumps({k_: v for k_, v in out.items() if k_ not in ('disagreements', 'perturbed_examples')}, indent=1))
print('DISAGREE', len(disagree)); [print(' ', d) for d in disagree]
print('PERTURB EXAMPLES'); [print(' ', e) for e in examples]

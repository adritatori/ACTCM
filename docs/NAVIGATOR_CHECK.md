# ATT&CK Navigator check

**Status: PARTLY VERIFIED. The hosted Navigator could not be reached from this session, so no layer has been loaded in it.**

## What was checked, and how

1. The Navigator source (`mitre-attack/attack-navigator`, default branch commit `734a1caba29fcd51f20b9ca239ce652b3354a47e`, latest release `v5.3.2`, 21 Apr 2026) reads its list of ATT&CK versions from `collection_index_url`, which is `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/index.json`.
2. That index, fetched 2026-11-04, lists Enterprise ATT&CK versions `20.0, 19.2, 19.1, ...` (42 entries, newest first). So the hosted app **should** offer v20.
3. **Not verified:** that the hosted app at `https://mitre-attack.github.io/attack-navigator/` shows v20 in its dropdown (the host did not respond from this session: HTTP status 000), and that release v5.3.2, built before v20 was published (13 Oct 2026), loads v20 data correctly. (v19.2 already had Stealth TA0005 and Defense Impairment TA0112, checked in the v19.2 file, so the tactic names are not new in v20.)
4. Layer format: validated against `layers/spec/v4.5/layerformat.md` from the commit above (required fields, gradient `minValue < maxValue`, legend items with label and colour, hex colours, `navigator >= 4.9.0`), and every technique/tactic pair was checked against the pinned v20 data. See `tests/test_navigator.py`.

Because the evidence says v20 is offered, no second layer set was exported. The comparison below shows what would differ in a v19.2 set. **Result: nothing differs for the tactics and technique/tactic pairs our labels use**, so the layer IDs would also resolve in v19.2.

## Tactics we use: v20 vs v19.2 (v19.2 file sha256 `dc1639caa5501d720e280cf1cbd8fbe009884a0c9b3e6e9ed9d0c25166c3d8f4`)

| v20 tactic | Name | Shortname | In v19.2? | Tasks (main or step) |
|---|---|---|---|---|
| TA0001 | Initial Access | initial-access | present in v19.2 | 20 |
| TA0002 | Execution | execution | present in v19.2 | 21 |
| TA0003 | Persistence | persistence | present in v19.2 | 5 |
| TA0004 | Privilege Escalation | privilege-escalation | present in v19.2 | 22 |
| TA0005 | Stealth | stealth | present in v19.2 | 4 |
| TA0006 | Credential Access | credential-access | present in v19.2 | 4 |
| TA0009 | Collection | collection | present in v19.2 | 8 |
| TA0010 | Exfiltration | exfiltration | present in v19.2 | 24 |
| TA0011 | Command and Control | command-and-control | present in v19.2 | 31 |
| TA0040 | Impact | impact | present in v19.2 | 19 |
| TA0112 | Defense Impairment | defense-impairment | present in v19.2 | 11 |

## Techniques we use that differ in v19.2 (0 of 24 technique/tactic pairs)

| Technique | Name (v20) | v20 tactic | v19.2 status | Tasks |
|---|---|---|---|---|

Pairs that are the same in both versions are not listed.

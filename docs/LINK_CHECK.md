# Link check

Run by `scripts/link_check.py` (`make links`). Repository links are tested for real. Links to other sites that did not answer from the build session are marked UNVERIFIED, not passed; run `make links` from a machine with open internet to check them.

| URL | HTTP status | Verdict | Pages |
|---|---|---|---|
| https://arxiv.org/abs/2604.06019 | 000 | UNVERIFIED (host did not answer from this session) | guide.html |
| https://arxiv.org/abs/2604.15384 | 000 | UNVERIFIED (host did not answer from this session) | guide.html |
| https://attack.mitre.org/resources/legal-and-branding/terms-of-use/ | 000 | UNVERIFIED (host did not answer from this session) | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm | 200 | 200 OK | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/CITATION.cff | 200 | 200 OK | guide.html |
| https://github.com/adritatori/actcm/blob/main/LICENSE | 200 | 200 OK | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/LICENSE-DATA | 200 | 200 OK | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/THIRD_PARTY_NOTICES.md | 200 | 200 OK | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/codebook/CODEBOOK.md | 200 | 200 OK | guide.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/data/sources.lock.yml | 200 | 200 OK | guide.html, index.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/docs/RELATED_WORK_SEARCH.md | 200 | 200 OK | guide.html |
| https://labs.cloudsecurityalliance.org/research/csa-research-note-atlas-agentic-gap-analysis-20260327/ | 000 | UNVERIFIED (host did not answer from this session) | guide.html |
| https://taoq-ai.github.io/ziran/reference/benchmarks/atlas-mapping/ | 000 | UNVERIFIED (host did not answer from this session) | guide.html |

13 external links: 8 return 200, 0 pending publication, 5 unverified (host unreachable from the session), 0 need checking.

## Live check (`make links-live`), 2026-11-04

| What | URL | Result |
|---|---|---|
| Navigator layer `combined` | https://raw.githubusercontent.com/adritatori/actcm/main/data/generated/navigator/actcm_combined_attack_v20.json | 200 OK, valid layer |
| Navigator layer `linuxarena` | https://raw.githubusercontent.com/adritatori/actcm/main/data/generated/navigator/actcm_linuxarena_attack_v20.json | 200 OK, valid layer |
| Navigator layer `refactor_arena` | https://raw.githubusercontent.com/adritatori/actcm/main/data/generated/navigator/actcm_refactor_arena_attack_v20.json | 200 OK, valid layer |
| Navigator layer `vllm` | https://raw.githubusercontent.com/adritatori/actcm/main/data/generated/navigator/actcm_vllm_attack_v20.json | 200 OK, valid layer |
| Repository | https://github.com/adritatori/actcm | 200 |

The hosted ATT&CK Navigator app itself is not tested by this script: open each "Open in Navigator" link in a browser and check that the layer loads.

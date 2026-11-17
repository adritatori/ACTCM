# Link check

Run by `scripts/link_check.py` (`make links`). Repository links are tested for real. Links to other sites that did not answer from the build session are marked UNVERIFIED, not passed; run `make links` from a machine with open internet to check them.

| URL | HTTP status | Verdict | Pages |
|---|---|---|---|
| https://arxiv.org/abs/2604.06019 | 200 | 200 OK | guide.html |
| https://arxiv.org/abs/2604.15384 | 200 | 200 OK | guide.html |
| https://attack.mitre.org/resources/legal-and-branding/terms-of-use/ | 200 | 200 OK | 11 pages |
| https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf | 200 | 200 OK | data/incidents/_sources.yml, incidents/hf-2026-07.html |
| https://cdn.prod.website-files.com/663bd486c5e4c81588db7a1d/6a724858f7db25c81487016d_Security%20Incident%20INC-2026-07-28-01.pdf | 200 | 200 OK | data/incidents/_sources.yml, incidents/aisi-2026-07.html |
| https://github.com/adritatori/actcm | 200 | 200 OK | 11 pages |
| https://github.com/adritatori/actcm/blob/main/CITATION.cff | 200 | 200 OK | guide.html |
| https://github.com/adritatori/actcm/blob/main/CONTRIBUTING.md | 200 | 200 OK | contribute.html |
| https://github.com/adritatori/actcm/blob/main/LICENSE | 200 | 200 OK | 11 pages |
| https://github.com/adritatori/actcm/blob/main/LICENSE-DATA | 200 | 200 OK | 11 pages |
| https://github.com/adritatori/actcm/blob/main/THIRD_PARTY_NOTICES.md | 200 | 200 OK | 11 pages |
| https://github.com/adritatori/actcm/blob/main/codebook/CODEBOOK.md | 200 | 200 OK | guide.html, verify.html |
| https://github.com/adritatori/actcm/blob/main/data/sources.lock.yml | 200 | 200 OK | 11 pages |
| https://github.com/adritatori/actcm/blob/main/docs/PILOT_PREDICTION.md | 200 | 200 OK | coverage.html |
| https://github.com/adritatori/actcm/blob/main/docs/RELATED_WORK_SEARCH.md | 200 | 200 OK | guide.html |
| https://github.com/adritatori/actcm/issues/new?template=incident-new.yml | 403 | NEEDS SIGN-IN (GitHub shows a new-issue form only to a signed-in user; not verified from here) | contribute.html |
| https://github.com/adritatori/actcm/issues/new?template=incident-step.yml | 403 | NEEDS SIGN-IN (GitHub shows a new-issue form only to a signed-in user; not verified from here) | contribute.html |
| https://github.com/adritatori/actcm/issues/new?template=step-dispute.yml | 403 | NEEDS SIGN-IN (GitHub shows a new-issue form only to a signed-in user; not verified from here) | contribute.html, incidents/aisi-2026-07.html, incidents/anthropic-pypi-2026.html, incidents/hf-2026-07.html |
| https://github.com/adritatori/actcm/issues/new?template=step-review.yml | 403 | NEEDS SIGN-IN (GitHub shows a new-issue form only to a signed-in user; not verified from here) | 5 pages |
| https://huggingface.co/blog/agent-intrusion-technical-timeline | 200 | 200 OK | data/incidents/_sources.yml, incidents/hf-2026-07.html |
| https://huggingface.co/blog/security-incident-july-2026 | 200 | 200 OK | data/incidents/_sources.yml, incidents/hf-2026-07.html |
| https://labs.cloudsecurityalliance.org/research/csa-research-note-atlas-agentic-gap-analysis-20260327/ | 200 | 200 OK | guide.html |
| https://metr.org/hugging-face-incident-report-aug-2026.pdf | 200 | 200 OK | data/incidents/_sources.yml, incidents/hf-2026-07.html |
| https://swarms.wiki/ | 200 | 200 OK | incidents.html |
| https://taoq-ai.github.io/ziran/reference/benchmarks/atlas-mapping/ | 200 | 200 OK | guide.html |
| https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing | 200 | 200 OK | data/incidents/_sources.yml, incidents/aisi-2026-07.html |
| https://www.anthropic.com/news/investigating-incidents-cybersecurity-evals | 200 | 200 OK | data/incidents/_sources.yml, incidents/anthropic-pypi-2026.html |
| https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents | 200 | 200 OK | data/incidents/_sources.yml, incidents/anthropic-pypi-2026.html |

28 external links: 24 return 200, 0 pending (not on the default branch yet), 4 not verified (host unreachable, or a sign-in is needed), 0 need checking.

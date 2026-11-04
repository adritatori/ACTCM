# Related work search (2026-11-04)

Required by the project brief before writing the Guide's related-work section. Five web searches. **Not exhaustive.**

## Newer work that maps control settings to ATT&CK or ATLAS

**None found.** The nearest is MonitoringBench ([arXiv 2605.09684](https://arxiv.org/html/2605.09684v1)), which builds an attack taxonomy
along three axes (technical implementation, structural complexity, evasion strategy) and applies it to BashArena. It does not use ATT&CK or ATLAS.
BashArena ([arXiv 2512.15688](https://arxiv.org/html/2512.15688v1)) and SHADE-Arena ([arXiv 2506.15740](https://arxiv.org/html/2506.15740v1)) are control settings;
neither search result showed an ATT&CK or ATLAS mapping. I have not read these papers in full.

## The five items named in the brief

| Item | Found? | Link | How it differs (one line) |
|---|---|---|---|
| LinuxArena paper | Yes (title, authors' abstract via search) | [arXiv 2604.15384](https://arxiv.org/abs/2604.15384) | The control setting itself. Its abstract reports 20 environments and 184 side tasks; this project counts only the public tasks in the repositories listed in its lock file. |
| Anthropic's LLM ATT&CK Navigator | **Not verified.** Only third-party write-ups found; the original Anthropic page was not located | [secondary write-up](https://blog.ogwilliam.com/post/mitre-attack-gap-llm-navigator-anthropic) | Reported to map observed real-world misuse of an AI model to ATT&CK. Not a control setting. |
| ZIRAN | Yes | [ZIRAN ATLAS mapping docs](https://taoq-ai.github.io/ziran/reference/benchmarks/atlas-mapping/), [PyPI](https://pypi.org/project/ziran/) | An agent security scanner. Its attack library is mapped to ATLAS (October 2025 release). A red-team tool, not a list of control-setting tasks. |
| CritBench | Yes | [arXiv 2604.06019](https://arxiv.org/abs/2604.06019) | A benchmark of 81 tasks for LLM agents in IEC 61850 digital substations, mapped to **ATT&CK for ICS**. Industrial, not Enterprise, and not about control evaluations. |
| CSA ATLAS agentic gap analysis | Yes | [CSA research note, 2026-03-27](https://labs.cloudsecurityalliance.org/research/csa-research-note-atlas-agentic-gap-analysis-20260327/) | A draft note on techniques for autonomous-agent control planes that ATLAS lacks, starting from ATT&CK v16. |

## The ATLAS Lateral Movement / Command and Control claim

The brief says ATLAS 2026.10 includes Lateral Movement and Command and Control, which the CSA note said were missing.
**Verified:** the pinned ATLAS 2026.10 file contains both (AML.TA0015 Lateral Movement, AML.TA0014 Command and Control).
**Not verified:** what the CSA note says about them. I only read a search summary of it. The Guide says only the verified part.

## Other facts checked against sources

- Control Tower docs, repo `linuxarena/control-tower`, commit `9035b914e8285f571a46088a5c0efac9afe765b4` (3 Nov 2026): `docs/development/failure-types.md`, `docs/development/making-side-tasks.md`,
  `docs/control-concepts.md`, `docs/glossary.md`. Glossary changes made because the sources win are listed in `docs/GLOSSARY_CHECK.md`.
- The LinuxArena paper's own definition of safety was **not** read (arXiv did not respond from this session). The glossary cites the Control Tower docs' definition instead.

# Sources and pins

Every source is pinned to a commit SHA in `data/sources.lock.yml`. Each task is read from that
commit, never from a branch head.

## Pin note: LinuxArena manifest is `v0.4.0`, not `v3.2.0`

The project brief asked for tag `v3.2.0` for LinuxArena. The manifest repo `linuxarena/ct-linuxarena`
has no `v3.2.0` tag. Its tags are `v0.1.0`, `v0.2.0`, `v0.3.0` and `v0.4.0`.

`v3.2.0` is the tag of each **environment** repo. It is set in the manifest's `envs.lock.yml`.

We pin the manifest at `v0.4.0` (commit `4b3d6616cc8652d4c921ca4327e5544107598c16`, released
2 Nov 2026; also the default-branch head on 4 Nov 2026). Tory approved this on condition that two
checks pass. Both passed on 4 Nov 2026:

1. `envs.lock.yml` at that commit lists 10 environments, all with `ref: v3.2.0`. For each one the
   `v3.2.0` tag on GitHub resolves to the `sha` in the file.
2. The LinuxArena task count is 92.

| Environment | v3.2.0 commit | Tasks |
|---|---|---|
| auto_workflow | b3bada6ea825b5f82855fc09655e0c22c4372f74 | 11 |
| clinical_trial | 9c319ef6285931646cf89f4b0ebecf1e19880279 | 5 |
| file_indexing | ea307733f125208b21a6ee9cd2870562af185fc2 | 13 |
| media_processing | 9bb894b139d87a18bf0f0e570280622aaae2b6f6 | 9 |
| model_registry | e2ebbda8849410d516f65e1b94fc508965f19d0a | 9 |
| shared_dotfiles | 93366d7591ce0534b8f2767835ffb5e1e661b4d2 | 11 |
| slack_clone | a1a5eb10ca5b766b905e515c045eccbf6d5d5b72 | 9 |
| tiktok | f553fd7b83e330b23863bea09560c2ffe9355552 | 9 |
| user_tracking | b2f2e208aad35eb97268a738c63b904e6787cda5 | 7 |
| web_scraping | 7e8ae8c1af1590fafc50b13bd88d5839930303a1 | 9 |

LinuxArena extras is not included in v0.1, pending permission from its maintainers.


# MITRE ATT&CK® Terms of Use check

**Status: RESOLVED (4 Nov 2026). Disclaimers match the page; Tory confirmed the `LICENSE.txt` wording of the licence paragraph is correct.**

Tory read the Terms of Use page (`https://attack.mitre.org/resources/legal-and-branding/terms-of-use/`) on 4 Nov 2026.
Claude has **not** read that page: `attack.mitre.org` does not resolve from the build session. What is on the site and in
`THIRD_PARTY_NOTICES.md` is MITRE's own `LICENSE.txt` from `mitre-attack/attack-stix-data` at commit
`20664a889568dce884a1dac0ec7b12ae3a199f51`, copied byte for byte into `data/legal/attack_licence.txt`.

## Comparison with the wording Tory pasted (4 Nov 2026)

Done word by word with a diff (`difflib`), not by eye.

| Part | Result |
|---|---|
| Copyright line, `© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation.` | **Identical.** |
| Order: licence paragraph, then copyright line, then disclaimers | **Same.** |
| Licence paragraph | **Two differences** (below). |
| Disclaimers | **Not compared.** Tory did not paste them and Claude cannot read the page. |

The two differences in the licence paragraph (page wording as Tory pasted it, then the copy in `LICENSE.txt`):

1. Opening words. Page as pasted: `MITRE hereby grants you ...`. `LICENSE.txt`: `The MITRE Corporation (MITRE) hereby grants you ...`.
2. The mark. Page as pasted: `to use ATT&CK for research ...`. `LICENSE.txt`: `to use ATT&CK® for research ...` (with the ® sign).

Everything else in the paragraph is the same, word for word: `a non-exclusive, royalty-free license to use ATT&CK[®] for research, development, and commercial purposes.
Any copy you make for such purposes is authorized provided that you reproduce MITRE's copyright designation and this license in any such copy.`

## Resolution

- **Disclaimers:** Tory pasted both paragraphs from the live page. A word-for-word diff against `data/legal/attack_licence.txt` found **no difference in content**: both paragraphs are identical (407 and 486 characters). Only the line wrapping differs (our file is hard-wrapped; the page text is not). The pasted text is kept as `data/legal/attack_disclaimers_from_terms_page_2026-11-04.txt` and a test compares it with our copy.
- **Licence paragraph:** Tory confirmed the `LICENSE.txt` wording ("The MITRE Corporation (MITRE) hereby grants you ... ATT&CK® ...") is correct and is to be kept. So no change was made for the two differences listed above.
- The site now shows the two disclaimer paragraphs as two paragraphs.

## What was needed from Tory (done)

- Is each difference real (the page itself says it that way), or did you shorten the text when you pasted it? The terms require reproducing the licence as MITRE wrote it, so nothing has been changed.
- Please paste the **disclaimers** section from the page. Our copy (two paragraphs, 895 characters, from `LICENSE.txt`) begins "MITRE does not claim ATT&CK enumerates all possibilities" and ends "...FITNESS FOR A PARTICULAR PURPOSE."
- If the page differs from `LICENSE.txt`, replace `data/legal/attack_licence.txt` with the page text and run `make site` and `make checksums`. Every page, the README and the notices follow from that one file, and tests compare the site with it.

## Re-check at release

Re-check the year and wording before each release (rule 5). The year is 2026 for this version; do not assume it for later ones.

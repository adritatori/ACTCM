# Publishing in one step

Nothing is pushed or published until Tory says **"publish"**. Everything below is ready so that this is a single step.

## What Tory does first

1. Fill the `TODO(Tory)` items. Each is marked in its file:
   - `CITATION.cff`: the author name fields and the repository name.
   - `config/publish.yml`: the repository name (and `README.md`, `CONTRIBUTING.md`).
   - `LICENSE-DATA`: the official CC BY 4.0 legal text.
2. Run `make publish-check`. It must print `PASS: nothing blocks publishing`. It fails while any `TODO(Tory)` is left, or if anything from a hidden setting would be public. It also builds the public tree and runs the tests and `make reproduce` inside it.
3. Read `docs/RELEASE_CHECKLIST.md` (private working copy) and say **"publish"**.

## What happens after "publish" (Phase 9, all automatic)

1. Print the release checklist again and confirm every item with fresh evidence.
2. Build the public tree with `scripts/export_public.py` and make the **first public commit from that tree** (a fresh history). The working branch is never pushed to a public repository: its history still contains files about the hidden setting.
3. Push the public repository; run `python scripts/enable_pages.py` (it refuses to run while the gate is blocked), enable Pages, run the workflow.
4. Run `make links-live`: the repository and the five Navigator layer files must answer. Then open each "Open in Navigator" link in a browser and record the result.
5. Tag `v0.1.0` and report the URLs.

## Link check you can run now

`make links` checks every external link on the site. From the build session no external host answered, so run it from your own machine.

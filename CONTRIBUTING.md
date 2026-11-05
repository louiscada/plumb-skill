# Contributing to Plumb

Thanks for helping make Plumb better. Ideas, bug reports and pull requests are all welcome. The maintainer reviews every change, and only approved changes are merged into the official Plumb.

## Never share real financial data

Not in issues, pull requests, screenshots or test files. Use made-up numbers and nicknames. If you need to show a ledger, edit the values first.

## Reporting a bug or suggesting an idea

Use the issue templates. A good bug report says what you typed or asked, what Plumb did, what you expected, and which Claude app you used.

## Making a change

1. Fork the repository and create a branch.
2. Make your change. Keep `plumb/scripts/plumb.py` to the Python standard library — no installs, so the skill works everywhere.
3. Run the tests from the repository root:

   ```bash
   python -m unittest discover -s tests -v
   ```

4. Add a test for anything new, and a line under a new heading in `CHANGELOG.md`.
5. Open a pull request using the template.

## Changes that move grades

The scoring curves and weights at the top of `plumb.py` decide everyone's grade, so `tests/test_plumb.py` pins exact grades for sample ledgers. If your change moves them, that's allowed, but it must be deliberate: update the expected numbers, explain why in the pull request, and note it in the changelog.

## Ground rules for Plumb's advice

- Plumb never recommends specific stocks, funds, coins, banks, insurance or apps. It talks about behaviors and account *types*.
- Plumb never asks for or stores account, card or ID numbers.
- Benchmarks should be widely accepted rules of thumb, and generic enough to work in any country.

## Releasing (maintainer)

1. Bump `VERSION` in `plumb/scripts/plumb.py` and move the changelog notes under the new version.
2. Push, then on GitHub: **Releases → Draft a new release**, tag `vX.Y.Z`, paste the changelog notes, and publish.
3. The release workflow runs the tests and attaches `plumb.skill` automatically.

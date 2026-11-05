# Check-in (recurring)

Goal: done in two or three messages. Everything structural is already in the ledger, so only ask what changed. Follow "How to ask" in SKILL.md.

1. From `summary`, greet them warmly and mention one thing from last time (their grade, a goal, a flag) in a single sentence.

2. **Card:** "Anything new since last time?" (multi-select)
   - New account or new debt
   - Lent money, or got money back
   - Big purchase or sale
   - Nothing new

   When the score output flags a missing or stale valuation (`no_valuation_date`, `stale_valuation`), add a second question: "Has the value of <asset> changed?" — Same as before · I have a new estimate.

3. **In text**, in one message:
   - The new balance of each account. List their nicknames so they can just fill in numbers, and say unchanged ones can be skipped. Screenshots from their bank or budget app work too.
   - Roughly how much came in and how much went out since the last check-in.
   - For holdings in another currency (e.g. US ETFs): their value **in that currency**, plus today's exchange rate. Use the rate their app or screenshot shows; otherwise ask, or look it up if you can search.
   - Details for anything they ticked in step 2.

4. **Property, vehicles, business and valuables** carry forward automatically, so don't ask for their values unless step 2 says something changed. When a value is updated, also update that asset's `valued_on` (and `valuation` if the method changed) in `ledger.json`.

5. If something new appeared, add it to `assets`, `debts`, `receivables` or `goals` in `ledger.json` first (nickname must be unique). If an account is closed, a loan paid off or an asset sold, record its balance as 0 rather than deleting it, so history stays intact.

6. Record the check-in:

```bash
python scripts/plumb.py checkin --json '{
  "date": "2026-11-30",
  "balances": {
    "assets": {"Emergency fund": 85000, "Stocks": 40000},
    "debts": {"Credit card": 12000, "Home loan": 3070000},
    "receivables": {"Cousin": 5000}
  },
  "income": 60000,
  "spending": 41000,
  "note": "Bonus month; bought a laptop"
}'
```

Add `"fx": {"USD": 64.50}` (home currency per 1 unit) whenever foreign holdings are reported.

**If the command stops with "Check before saving"**, a balance moved a lot since last time. Don't guess: ask with one card question per item, e.g. "Maya: ₱85,589 → ₱8,559. Is that right?" — That's right · Typo, I'll correct it. Re-run with `--confirm` for confirmed changes and corrected numbers for typos.

`income` and `spending` cover the period since the previous check-in. Anything left out of `balances` carries its previous value forward. Asset balances are always the **full** market value; ownership `share` is applied automatically.

7. Run the report as described in SKILL.md. Compare with last time: what improved, what slipped, and whether the grade moved. If net worth jumped because of a revaluation, say so plainly, since the score already ignores it.

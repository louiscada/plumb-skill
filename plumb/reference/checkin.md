# Check-in (recurring)

Goal: done in two or three messages. Everything structural is already in the ledger, so only ask what changed.

1. From `summary`, greet them warmly and mention one thing from last time (their grade, a goal, a flag) in a single sentence.
2. Ask, in one message:
   - The new balance of each **account** (list their nicknames so they can just fill in numbers). Unchanged ones can be left out.
   - Roughly how much came in and how much went out since the last check-in.
   - Anything new: a new account, a new debt, money lent or paid back, a big purchase or sale. A one-line note is enough.
3. **Property, vehicles, business and valuables** carry forward automatically, so don't ask for their values every time. Ask only if:
   - they bought or sold one (add or zero it out);
   - something changed its value (renovation, damage, a new appraisal); or
   - the score output flags a stale or missing valuation — then suggest a refresh, about once a year.

   When a value is updated, also update that asset's `valued_on` (and `valuation` if the method changed) in `ledger.json`.
4. If something new appeared, add it to `assets`, `debts`, `receivables` or `goals` in `ledger.json` first (nickname must be unique). If an account is closed, a loan paid off or an asset sold, record its balance as 0 rather than deleting it, so history stays intact.
5. Record the check-in:

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

`income` and `spending` cover the period since the previous check-in. Anything left out of `balances` carries its previous value forward. Asset balances are always the **full** market value; ownership `share` is applied automatically.

6. Run the report as described in SKILL.md. Compare with last time: what improved, what slipped, and whether the grade moved. If net worth jumped because of a revaluation, say so plainly, since the score already ignores it.

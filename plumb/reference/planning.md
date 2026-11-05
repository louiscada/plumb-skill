# Planning: goal targets, timelines and what-ifs

Read this when the user asks how much a goal should be, when they'll reach it, whether they can afford something, or "what if…".

## Goal timelines

`score` and `summary` give each goal a `pace` (per month), an `eta` (YYYY-MM), and, when it has a target date, `needed_per_month` and `on_track`.

- **Net-worth goals** use the underlying net worth change over the last few check-ins, excluding revaluations and FX. Before a second check-in they use monthly savings (income − spending) and say so (`pace_basis: "monthly savings"`).
- **Account goals** use that account's recent change, so they need two check-ins.
- **No investment growth is assumed.** Say this when you quote a date, and frame it as "at your current pace", never as a promise.
- If `on_track` is false, give the gap in plain numbers: "You're saving ₱8,000 a month toward it; the date needs ₱11,500."

## Helping set a target

When a goal has no target, offer to work one out together. Ask for the local norms instead of assuming them, since they vary by country and city.

- **Moving out (renting):** deposit + advance rent (ask what landlords near them usually require, often 1–3 months in total) + moving costs + basic furnishing. Then run a what-if (below) to see the new monthly picture, and remind them the emergency fund should grow to cover 6 months of the *new* spending.
- **Buying a home:** down payment (ask the price range they're looking at and the usual minimum down payment where they live) + closing costs and fees (ask; often a few percent of the price) + moving and furnishing.
- **Travel:** flights + nights × daily budget per person + about 10–15% buffer.
- **Emergency fund:** 6 × monthly spending (3 can be enough with very stable income; more for freelancers or single-income households with dependents).
- **A net-worth number** ("be a millionaire"): the target is the number; track it with `"bucket": "net_worth"`.

Write the agreed target into the goal in `ledger.json` (`"target"`, and `"by"` if they have a date), then rerun `summary` to show the new timeline.

## What-if

`whatif` compares today with a change, without saving anything. Momentum is left out on both sides so the comparison is fair.

```bash
python scripts/plumb.py whatif --json '{
  "spending_change": 18000,
  "income_change": 0,
  "cash_change": -60000,
  "new_debts": [{"name": "Car loan", "balance": 500000, "monthly_payment": 12000, "rate": 9}]
}'
```

| Field | Meaning |
|---|---|
| `spending_change` | Change to monthly spending (rent, new bills; negative if something stops) |
| `income_change` | Change to monthly take-home pay (a raise, a job change; negative for a pay cut) |
| `cash_change` | One-time change to liquid savings (move-in costs, a down payment, a bonus) |
| `new_debts` | Loans the change would add: balance, monthly payment, annual rate |

Common shapes:
- **Moving out:** `spending_change` = rent + utilities + extra food − anything they stop paying at home; `cash_change` = −(deposit + advance + moving + furnishing).
- **Buying a car:** `new_debts` for the loan, `cash_change` for the down payment, `spending_change` for fuel, parking and insurance.
- **New job or raise:** `income_change`.

Share the before → after table in chat in the buddy voice, and say what drives the change ("the cushion drops from 6.8 to 2.6 months, which is most of the grade change"). Then suggest what would make the plan safer (a bigger cushion first, a cheaper rent, a later date). It's their decision; never tell them not to do it.

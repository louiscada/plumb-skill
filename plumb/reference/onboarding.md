# Onboarding (first run)

Goal: a complete-enough balance sheet with as little typing as possible. Follow "How to ask" in SKILL.md: cards for choices, plain text for amounts, one round at a time. Accept rough numbers, and let the user skip anything. Accuracy improves at each check-in.

## Opening

Two or three warm sentences: what Plumb does, the one-time disclaimer (educational check-up tool, not a licensed financial advisor), and that their data stays in a local file. Then ask how they'd like to do it:

**Card — "How do you want to do this?"** (single-select)
- **Quick** — totals per group, about 3 minutes. Enough for a first grade.
- **Detailed** — account by account. Better tracking at every check-in.
- **Screenshots** — send screenshots from your bank or budget app and I'll read them.

Remember the choice; it decides how Round 3 collects amounts.

## Round 1 — The basics

**Card** (single-select each):
1. Currency — the one their language or location suggests first, then two common alternatives (Other covers the rest).
2. How do you earn money right now? — Salaried · Freelance or business · Mixed · No income right now
3. Does anyone depend on you financially? — No · Yes

**Then in text:** "What should I call you (it goes on your report), how old are you, and roughly how much do you take home per month after tax?" Store the name as `profile.name`; if they'd rather not say, leave it empty.

## Round 2 — Spending and lifestyle

**Card:**
1. How would you describe your lifestyle? — Simple · Comfortable · Lavish (single-select)
2. Where does most of your money go? — Food · Housing · Transport · Shopping or travel (multi-select)

**Then in text:** "Roughly how much do you spend in a typical month, everything included?" If they say recent months were unusual (a trip, an emergency), record the typical figure and note the unusual one in the check-in `note`.

## Round 3 — The checklist

One card that decides everything still to ask. Ask only about what they tick.

**Card** (multi-select each):
1. **Money you keep** — Bank savings or checking · E-wallets · Investments (stocks, funds, crypto) · Retirement or insurance cash value
2. **Things you own** — Land or home · Vehicle · A business · Valuables worth over a month's spending
3. **Money you owe** — Credit cards · Loans (personal, car, home, student) · Buy-now-pay-later · Borrowed from family or friends (incl. their cards)
4. **Has anyone borrowed money from you?** — Yes · No (single-select)

Nothing ticked in a group? Skip it entirely.

## Round 4 — Amounts

Collect balances for the ticked groups, in the way they chose at the start:

- **Quick:** one total per ticked group, in text. "About how much across all your savings and e-wallets? And all your investments?" Record each total as one asset with a clear nickname ("All savings", "All investments").
- **Detailed:** each account with a nickname they'll recognize and its balance.
- **Screenshots:** ask for the screenshots, read every balance, then show back a short table of what you recorded so they can correct it.

Holdings in another currency (e.g. US stocks or ETFs): record `"currency": "USD"` on the asset, its balance **in that currency**, and the rate in the first check-in as `"fx": {"USD": <home currency per 1 USD>}`. Use the rate their app shows if it shows one. Exchange-rate moves are then kept out of their progress score.

Then fill the gaps with defaults instead of questions:
- Savings, checking, cash and e-wallets count as **liquid** (withdrawable within a week). Investments, retirement and property don't. Ask only when unclear (a time deposit, a locked account).
- Leave interest rates empty unless offered.

Types to record — cash & deposits: `cash`, `savings`, `checking`, `time_deposit`, `e_wallet`, `money_market`; investments: `brokerage`, `stocks`, `bonds`, `funds`, `crypto`, `precious_metals`, `investment_other`; retirement & insurance: `retirement`, `pension`, `insurance_cash_value` (cash or surrender value only).

## Round 5 — Things you own and money you owe

Only for what they ticked in Round 3.

**Things you own** — real estate (`land`, `home`, `condo`, `rental_property`, `commercial_property`, `real_estate_other`), vehicles (`car`, `motorcycle`, `boat`), `business`, valuables (`jewelry`, `collectibles`, `equipment`). For each, in text: what it would **sell for today** and their **ownership share** if co-owned (`share`, %). Then a card for how they got the number: Appraisal · Nearby listings · My own guess · Purchase price (`valuation`: `appraisal`, `market_quote`, `estimate`, `purchase_price`). Record `valued_on` as the current YYYY-MM. A pre-revenue startup is recorded at 0 unless they know a valuation or want to count what they put in. Never ask for title, lot, plate or registration numbers.

**Money you owe** — **Card:** "Do you pay your credit cards in full every month?" Usually · Sometimes carry a balance · Often carry a balance. Then in text, per debt: what's left, the monthly payment, and the interest rate if known. Types: `credit_card`, `personal_loan`, `mortgage`, `car_loan`, `student_loan`, `bnpl`, `business_loan`, `family_friend`, `other`.
- Cards paid in full: record the current balance with `monthly_payment` 0 and no rate. That spending is already in their monthly spending, and no interest is charged.
- A loan tied to something they own goes in `secured_by` (the asset's nickname), so the report shows their equity.
- Installments: work out what's left (e.g. 19 of 24 payments) and show your math so they can confirm.

## Round 6 — You and your goals

**Card:**
1. If your investments dropped 20% in a month, what would you do? — Wait it out · Buy more · Sell (single-select; maps to `medium` / `high` / `low`)
2. Which sounds like you? — Saver · Planner · Spender · Worrier (multi-select; Other covers avoider, YOLO, anything else)
3. What are you saving for? — Emergency fund · A home or moving out · Travel · Reaching a net-worth number (multi-select)
4. How often should we check in? — Biweekly · Monthly (single-select)

**Then in text:**
- For each goal they picked: a target amount and date, **if they know them**. A goal without a target is fine (the report shows "Set a target"). Track a goal against the account its money lives in (`"bucket": "<nickname>"`), or the whole net worth for net-worth goals (`"bucket": "net_worth"`).
- For each person who owes them money: a nickname (no full names needed), the amount, and a **card** for how likely it is to come back: Likely · Unsure · Unlikely.

## Then

1. Run `init`, then write `plumb-data/ledger.json` following the template's `_format` examples: fill `profile`, `assets`, `debts`, `receivables`, `goals`.
2. Record the snapshot as the first check-in with `checkin` (today's date, all current balances — for assets, the **full** market value, since `share` is applied automatically — and their typical monthly income and spending).
3. Run the report as described in SKILL.md.
4. Close by suggesting a recurring reminder for their chosen rhythm. If the platform offers scheduled tasks, offer to set one up ("money check-in"); otherwise suggest a calendar reminder. Payday is a good day for it.

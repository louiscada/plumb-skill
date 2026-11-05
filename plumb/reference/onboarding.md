# Onboarding (first run)

Goal: a complete balance sheet in about six short rounds. Ask **one round per message**, accept rough numbers ("around 50k" is fine), and let the user say "skip" to anything. A friend wouldn't demand exact figures on day one; accuracy improves at each check-in.

Open with one or two warm sentences, the one-time disclaimer (educational check-up tool, not a licensed financial advisor), and a note that their data stays in a local file. Then start.

## Round 1 — The basics
- What should I call you? A first name or nickname is enough; it goes on their report ("Juan's Financial Health Report"). Store it as `profile.name`. If they'd rather not say, leave it empty and the report is simply titled "Financial Health Report".
- What currency do you use?
- How old are you? (helps calibrate advice — e.g. time horizon)
- How do you earn money right now? (salaried, freelance, business, mixed, none / student / between jobs)
- Roughly how much comes in per month after tax? (if irregular, a typical month)
- Does anyone depend on you financially?

## Round 2 — Spending and lifestyle
- Roughly how much do you spend in a typical month, everything included?
- How would you describe your lifestyle — simple, comfortable, lavish, somewhere in between?
- What are your biggest spending categories? (optional)

## Round 3 — Money in accounts
Ask them to list every place they keep money, with a nickname they'll recognize. For each: **type**, **balance**, whether they could get it out within a week (**liquid**), and the interest rate if they know it.

- Cash & deposits: `cash`, `savings`, `checking`, `time_deposit`, `e_wallet`, `money_market`
- Investments: `brokerage`, `stocks`, `bonds`, `funds`, `crypto`, `precious_metals`, `investment_other`
- Retirement & insurance: `retirement`, `pension` (employer or government), `insurance_cash_value` (the cash or surrender value only, not the death benefit)

They choose the granularity. "About 200k in savings and 50k in stocks" is a perfectly good answer. Reminder: no account numbers, no bank names needed.

## Round 4 — Things you own
Prompt for each category so nothing is forgotten, but let them skip any that don't apply:

- **Real estate:** `land`, `home`, `condo`, `rental_property`, `commercial_property`, `real_estate_other`. This includes inherited or family land, and property still being paid off.
- **Vehicles:** `car`, `motorcycle`, `boat`.
- **Business:** `business` (their stake in a business they own).
- **Personal valuables:** `jewelry`, `collectibles`, `equipment`. Only items that would sell for more than about a month of their spending, so the list stays meaningful.

For each item ask:
- **Estimated current market value** of the whole item: what it would sell for today, not what they paid.
- **Ownership share** (`share`, %): important for co-owned, conjugal or family property. "My siblings and I each own a quarter" → 25.
- **How the value was estimated** (`valuation`): `appraisal`, `market_quote` (listings or recent sales nearby), `estimate`, `purchase_price`, or `tax_declaration`.
- **When** it was last valued (`valued_on`, YYYY-MM).

None of these count as liquid. Never ask for title, lot, plate or registration numbers.

## Round 5 — Money you owe
For each debt: nickname, **type** (`credit_card`, `personal_loan`, `mortgage`, `car_loan`, `student_loan`, `bnpl`, `business_loan`, `family_friend`, `other`), **balance**, **interest rate** (annual %, or "don't know"), and **monthly payment**. If a loan is tied to something they own (a home loan, a car loan), record which asset in `secured_by`; the report then shows their equity in it. Loans from family or friends count — usually 0% interest.

## Round 6 — Money owed to you, and you
- Has anyone borrowed money from you that hasn't been paid back? For each: a nickname (no full names needed), the amount, and how likely it is to come back (`likely` / `unsure` / `unlikely`).
- **Risk tolerance**, as a scenario rather than a label: "If your investments dropped 20% in a month, would you sell, wait it out, or buy more?" → `low` / `medium` / `high`.
- **Money personality**: which sounds most like you — saver, spender, avoider (don't like looking), worrier, planner, or YOLO?
- **Goals**: up to three things you're saving for, each with a target amount and, optionally, a target date and the account it lives in.
- How often do you want to check in — **monthly** or **biweekly**?

## Then
1. Run `init`, then write `plumb-data/ledger.json` following the template's `_format` examples: fill `profile`, `assets`, `debts`, `receivables`, `goals`.
2. Record the snapshot as the first check-in with `checkin` (today's date, all current balances — for assets, the **full** market value, since `share` is applied automatically — and their typical monthly income and spending).
3. Run the report as described in SKILL.md.
4. Close by suggesting a recurring reminder for their chosen frequency. If the platform offers scheduled tasks, offer to set one up ("money check-in"); otherwise suggest a calendar reminder. Payday is a good day for it.

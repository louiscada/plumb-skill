#!/usr/bin/env python3
"""Plumb: ledger math, A–F grading and a self-contained HTML report.

Standard library only. All data stays in a local ledger.json.
Run `python plumb.py -h` for commands.
"""
import argparse
import base64
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime

# ---------------------------------------------------------------- settings ---

# Branding: rename the tool here and the report follows.
BRAND_NAME = "Plumb"
BRAND_TAGLINE = "Personal finance check-up"
REPORT_PREFIX = "PL"  # report numbers look like PL-20261130-003
# Display face for the wordmark, report title and grade letter: Francois One
# (a condensed headline grotesque) by Vernon Adams, SIL Open Font License
# (assets/OFL-FrancoisOne.txt). Subset to Latin and embedded in each report so
# it looks the same offline and in print.
DISPLAY_FONT = "FrancoisOne-Regular.subset.woff2"

HIGH_RATE = 10.0  # annual % at or above which a debt counts as high-interest
WEIGHTS = {"emergency": 0.30, "debt": 0.30, "savings": 0.25, "momentum": 0.15}
LABELS = {
    "emergency": "Emergency cushion",
    "debt": "Debt health",
    "savings": "Savings rate",
    "momentum": "Momentum",
}
GRADES = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "F")]
LIKELIHOOD = {"likely": 1.0, "unsure": 0.5, "unlikely": 0.0}
FREQ_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}
SYMBOLS = {
    "USD": "$", "PHP": "₱", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "INR": "₹", "KRW": "₩", "AUD": "A$", "CAD": "C$", "SGD": "S$",
    "NZD": "NZ$", "HKD": "HK$", "IDR": "Rp", "MYR": "RM", "THB": "฿",
    "VND": "₫", "BRL": "R$", "MXN": "MX$", "NGN": "₦", "ZAR": "R",
}
SECTIONS = ("assets", "debts", "receivables")
ASSET_CLASSES = [  # (class, asset types), in report order
    ("Cash & deposits", {"cash", "savings", "checking", "time_deposit",
                         "e_wallet", "money_market"}),
    ("Investments", {"brokerage", "stocks", "bonds", "funds", "crypto",
                     "precious_metals", "investment_other"}),
    ("Retirement & insurance", {"retirement", "pension",
                                "insurance_cash_value"}),
    ("Real estate", {"land", "home", "condo", "rental_property",
                     "commercial_property", "property", "real_estate_other"}),
    ("Vehicles", {"vehicle", "car", "motorcycle", "boat"}),
    ("Business", {"business"}),
    ("Personal valuables", {"jewelry", "collectibles", "equipment",
                            "valuables"}),
    ("Other", set()),
]
# Valued by estimate rather than by statement. Changes in their value are
# treated as revaluations and kept out of Momentum, so a re-appraised lot or a
# depreciating car doesn't count as saving or losing money.
NON_FINANCIAL = {"Real estate", "Vehicles", "Business", "Personal valuables",
                 "Other"}
STALE_MONTHS = 18  # flag non-financial values not updated in this long
# 10+ digits in a row (spaces/dashes allowed between) looks like an account,
# card or ID number. Dates have 8 digits, so they pass.
LONG_NUMBER = re.compile(r"(?:\d[ -]?){10,}")

# Score curves: (input, score) points, linear in between, flat outside.
CURVE_EMERGENCY = [(0, 0), (1, 30), (3, 65), (6, 100)]           # months
CURVE_SAVINGS = [(0, 0), (0.05, 30), (0.10, 55), (0.20, 85), (0.30, 100)]
CURVE_DTI = [(0, 100), (0.10, 90), (0.20, 75), (0.36, 50), (0.50, 20), (0.60, 0)]
CURVE_DEBT_ASSETS = [(0, 100), (0.3, 70), (0.6, 35), (1.0, 0)]
CURVE_MOMENTUM = [(-0.5, 0), (0, 50), (0.5, 100)]                # months/month


class MoneyError(Exception):
    pass


# ----------------------------------------------------------------- helpers ---

def curve(x, points):
    if x <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(points[-1][1])


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise MoneyError(f"Bad date {s!r}; use YYYY-MM-DD.")


def money(x, cur):
    sym = SYMBOLS.get(cur, cur + " ")
    sign = "−" if x < 0 else ""
    x = abs(x)
    body = f"{x:,.0f}" if x >= 100 or x == int(x) else f"{x:,.2f}"
    return f"{sign}{sym}{body}"


def num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise MoneyError(f"{what} must be a number, got {v!r}.")
    if v < 0:
        raise MoneyError(f"{what} can't be negative.")
    return float(v)


def find_long_numbers(obj, path=""):
    """Yield paths of string values that look like account/card/ID numbers."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("_"):
                continue
            yield from find_long_numbers(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_long_numbers(v, f"{path}[{i}]")
    elif isinstance(obj, str) and LONG_NUMBER.search(obj):
        yield path


# ------------------------------------------------------------------ ledger ---

def ledger_path(data_dir):
    return os.path.join(data_dir, "ledger.json")


def load(data_dir):
    p = ledger_path(data_dir)
    if not os.path.exists(p):
        raise MoneyError(f"No ledger at {p}. Run `init` first (onboarding).")
    with open(p, encoding="utf-8") as f:
        try:
            led = json.load(f)
        except json.JSONDecodeError as e:
            raise MoneyError(f"ledger.json is not valid JSON: {e}")
    for key in ("profile",) + SECTIONS + ("goals", "checkins"):
        led.setdefault(key, {} if key == "profile" else [])
    for sec in SECTIONS:
        names = [b.get("name") for b in led[sec]]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise MoneyError(f"Duplicate names in {sec}: {sorted(dupes)}")
    hits = list(find_long_numbers(led))
    if hits:
        print("WARNING: these fields look like account/card/ID numbers and "
              "should be removed: " + ", ".join(hits), file=sys.stderr)
    led["checkins"].sort(key=lambda c: c.get("date", ""))
    return led


def save(data_dir, led):
    p = ledger_path(data_dir)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def balances_through(led, idx):
    """Balances as of check-in idx, carrying forward unreported buckets."""
    bal = {s: {} for s in SECTIONS}
    for c in led["checkins"][: idx + 1]:
        for s in SECTIONS:
            bal[s].update(c.get("balances", {}).get(s, {}))
    return bal


def period_days(led, idx):
    if idx == 0:
        return 30  # first check-in holds typical *monthly* income/spending
    d = (parse_date(led["checkins"][idx]["date"])
         - parse_date(led["checkins"][idx - 1]["date"])).days
    if d < 7:  # back-to-back corrections shouldn't blow up the math
        d = FREQ_DAYS.get(led["profile"].get("checkin_frequency"), 30)
    return d


def recent_monthly(led, field, fallback):
    vals = []
    for i in range(len(led["checkins"]) - 1, -1, -1):
        v = led["checkins"][i].get(field)
        if v is not None:
            vals.append(v * 30 / period_days(led, i))
        if len(vals) == 3:
            break
    if vals:
        return sum(vals) / len(vals)
    return fallback


def asset_class(asset_type):
    for name, types in ASSET_CLASSES:
        if asset_type in types:
            return name
    return "Other"


def share_of(asset):
    """Ownership share as a fraction (e.g. 25 → 0.25). Default: full."""
    s = asset.get("share")
    return 1.0 if s is None else max(0.0, min(float(s), 100.0)) / 100


def counted_assets(led, bal):
    """{name: value of the user's share} — balances hold full market value."""
    amap = {a["name"]: a for a in led["assets"]}
    return {k: v * share_of(amap.get(k, {})) for k, v in bal["assets"].items()}


def totals(led, bal):
    amap = {a["name"]: a for a in led["assets"]}
    like = {r["name"]: LIKELIHOOD.get(r.get("likelihood", "unsure"), 0.5)
            for r in led["receivables"]}
    counted = counted_assets(led, bal)
    cls = {k: asset_class(amap.get(k, {}).get("type")) for k in counted}
    assets = sum(counted.values())
    nonfin = sum(v for k, v in counted.items() if cls[k] in NON_FINANCIAL)
    liquid = sum(v for k, v in counted.items()
                 if amap.get(k, {}).get("liquid") and cls[k] not in NON_FINANCIAL)
    debts = sum(bal["debts"].values())
    recv = sum(v * like.get(k, 0.5) for k, v in bal["receivables"].items())
    return {"assets": assets, "liquid": liquid, "debts": debts,
            "nonfinancial": nonfin, "receivables": recv,
            "net_worth": assets + recv - debts}


def months_between(earlier, later):
    """Whole months between two 'YYYY-MM[-DD]' strings, or None."""
    try:
        y1, m1 = int(earlier[:4]), int(earlier[5:7])
        y2, m2 = int(later[:4]), int(later[5:7])
    except (TypeError, ValueError):
        return None
    return (y2 - y1) * 12 + (m2 - m1)


# ----------------------------------------------------------------- scoring ---

def allocation(led, counted, total):
    amap = {a["name"]: a for a in led["assets"]}
    by = {}
    for k, v in counted.items():
        c = asset_class(amap.get(k, {}).get("type"))
        by[c] = by.get(c, 0) + v
    return [{"class": c, "value": round(by[c], 2),
             "pct": round(by[c] / total * 100, 1) if total > 0 else 0}
            for c, _ in ASSET_CLASSES if by.get(c)]


def score(led):
    if not led["checkins"]:
        raise MoneyError("No check-ins yet. Record the onboarding snapshot "
                         "with `checkin` first.")
    prof = led["profile"]
    cur = prof.get("currency") or "USD"
    last = len(led["checkins"]) - 1
    bal = balances_through(led, last)
    t = totals(led, bal)
    spend = recent_monthly(led, "spending", prof.get("monthly_spending"))
    income = recent_monthly(led, "income", prof.get("monthly_income"))
    latest = led["checkins"][last]

    comps, flags, metrics = {}, [], {}

    # Emergency cushion
    if spend and spend > 0:
        months = t["liquid"] / spend
        metrics["emergency_months"] = round(months, 2)
        comps["emergency"] = (curve(months, CURVE_EMERGENCY),
                              f"{months:.1f} months of spending")
        if months < 1:
            flags.append(("low_emergency",
                          f"Liquid savings cover {months:.1f} months of "
                          "spending (target 3–6)."))
        elif months > 9:
            flags.append(("idle_cash",
                          f"Liquid savings cover {months:.1f} months — more "
                          "than a typical 6-month cushion; the extra may be "
                          "able to work harder toward goals."))

    # Savings rate (ratio of the latest period, else recent averages)
    inc_l, sp_l = latest.get("income"), latest.get("spending")
    if inc_l is None or sp_l is None:
        inc_l, sp_l = income, spend
    if inc_l and inc_l > 0 and sp_l is not None:
        rate = (inc_l - sp_l) / inc_l
        metrics["savings_rate"] = round(rate, 3)
        comps["savings"] = (curve(rate, CURVE_SAVINGS),
                            f"{rate * 100:.0f}% of income kept")
        if rate < 0:
            flags.append(("overspending",
                          f"Spent {money(sp_l - inc_l, cur)} more than came "
                          "in this period."))

    # Debt health
    high = [d for d in led["debts"]
            if (d.get("rate") or 0) >= HIGH_RATE
            and bal["debts"].get(d["name"], 0) > 0]
    if t["debts"] <= 0:
        comps["debt"] = (100.0, "Debt-free")
    else:
        pay = sum(d.get("monthly_payment") or 0 for d in led["debts"]
                  if bal["debts"].get(d["name"], 0) > 0)
        if income and income > 0:
            dti = pay / income
            metrics["debt_payments_to_income"] = round(dti, 3)
            s = curve(dti, CURVE_DTI)
            detail = f"Payments are {dti * 100:.0f}% of income"
        else:
            ratio = t["debts"] / t["assets"] if t["assets"] > 0 else 1.0
            metrics["debt_to_assets"] = round(ratio, 3)
            s = curve(ratio, CURVE_DEBT_ASSETS)
            detail = f"Debt is {ratio * 100:.0f}% of assets"
        if high:
            s = max(0.0, s - 20)
            detail += "; high-interest debt"
        comps["debt"] = (s, detail)
    for d in high:
        flags.append(("high_interest_debt",
                      f"{d['name']} charges {d['rate']:g}% a year on "
                      f"{money(bal['debts'][d['name']], cur)}."))

    # Momentum (needs two check-ins). Scored on the *underlying* change:
    # the net worth change minus revaluations of non-financial assets held at
    # both check-ins. Buying or selling one is a swap, not a revaluation.
    history, prev = [], None
    for i, c in enumerate(led["checkins"]):
        bi = balances_through(led, i)
        ti, ci = totals(led, bi), counted_assets(led, bi)
        entry = {"date": c["date"], "net_worth": round(ti["net_worth"], 2),
                 "change": None, "revaluation": None, "underlying": None}
        if prev:
            amap_ = {a["name"]: a for a in led["assets"]}
            reval = sum(
                ci[k] - prev[1][k] for k in ci
                if prev[1].get(k, 0) > 0 and ci[k] > 0
                and asset_class(amap_.get(k, {}).get("type")) in NON_FINANCIAL)
            chg = ti["net_worth"] - prev[0]
            entry.update(change=round(chg, 2), revaluation=round(reval, 2),
                         underlying=round(chg - reval, 2))
        history.append(entry)
        prev = (ti["net_worth"], ci)
    if len(history) >= 2 and spend and spend > 0:
        change = history[-1]["underlying"]
        per_month = change * 30 / period_days(led, last)
        metrics["net_worth_change"] = history[-1]["change"]
        metrics["revaluation"] = history[-1]["revaluation"]
        metrics["underlying_change"] = change
        ratio = per_month / spend
        comps["momentum"] = (curve(ratio, CURVE_MOMENTUM),
                             f"{'+' if change >= 0 else ''}"
                             f"{money(change, cur)} since last check-in, "
                             "excl. revaluations")
        if change < 0:
            flags.append(("net_worth_down",
                          f"Net worth fell {money(-change, cur)} since the "
                          "last check-in, excluding revaluations."))
    elif len(history) < 2:
        flags.append(("first_checkin",
                      "Momentum is scored from the second check-in onward."))

    # Balance-sheet observations
    counted = counted_assets(led, bal)
    amap = {a["name"]: a for a in led["assets"]}
    if t["net_worth"] > 0 and t["receivables"] / t["net_worth"] > 0.25:
        flags.append(("receivables_heavy",
                      "Over a quarter of net worth is money other people "
                      "owe you."))
    held = {k: v for k, v in counted.items() if v > 0}
    if len(held) > 1 and t["assets"] > 0:
        top = max(held, key=held.get)
        frac = held[top] / t["assets"]
        if frac > 0.6:
            flags.append(("concentration",
                          f"{top} makes up {frac * 100:.0f}% of total "
                          "assets."))
    if t["assets"] > 0 and t["nonfinancial"] / t["assets"] > 0.8:
        pct = t["nonfinancial"] / t["assets"] * 100
        if metrics.get("emergency_months", 99) < 3:
            flags.append(("illiquid_heavy",
                          f"{pct:.0f}% of assets are property or other "
                          "non-financial assets, while liquid savings cover "
                          "under 3 months of spending."))
        else:
            flags.append(("nonfinancial_heavy",
                          f"{pct:.0f}% of assets are property or other "
                          "non-financial assets, so net worth depends heavily "
                          "on estimated values."))
    for d in led["debts"]:
        sec = d.get("secured_by")
        owed = bal["debts"].get(d["name"], 0)
        if sec in counted and owed > counted[sec] > 0:
            flags.append(("underwater",
                          f"{d['name']} ({money(owed, cur)}) is more than "
                          f"the value of {sec} ({money(counted[sec], cur)})."))
    for k, v in counted.items():
        a = amap.get(k, {})
        if v <= 0 or asset_class(a.get("type")) not in NON_FINANCIAL:
            continue
        age = months_between(a.get("valued_on"), latest["date"])
        if age is None:
            flags.append(("no_valuation_date",
                          f"{k} has no valuation date; note when its value "
                          "was last estimated."))
        elif age > STALE_MONTHS:
            flags.append(("stale_valuation",
                          f"{k} was last valued in {a['valued_on'][:7]}; "
                          "consider refreshing the estimate."))
    for a in led["assets"]:
        r = a.get("rate")
        b = bal["assets"].get(a["name"], 0)
        if (a.get("liquid") and r is not None and r < 1 and spend
                and b > spend):
            flags.append(("low_rate_cash",
                          f"{a['name']} earns {r:g}% on "
                          f"{money(b, cur)}; higher-yield savings account "
                          "types exist."))

    # Weighted total, re-normalized over measurable parts
    wsum = sum(WEIGHTS[k] for k in comps)
    total = sum(comps[k][0] * WEIGHTS[k] for k in comps) / wsum if wsum else 0
    total = round(total)
    grade = next(g for cut, g in GRADES if total >= cut)

    goals = []
    for g in led["goals"]:
        cur_amt = bal["assets"].get(g.get("bucket")) if g.get("bucket") else None
        target = g.get("target") or 0
        goals.append({
            "name": g.get("name"), "target": target, "by": g.get("by"),
            "current": cur_amt,
            "pct": round(min(cur_amt / target, 1) * 100) if cur_amt is not None
            and target else None,
        })

    return {
        "date": latest["date"], "currency": cur,
        "score": total, "grade": grade,
        "net_worth": round(t["net_worth"], 2),
        "assets_total": round(t["assets"], 2),
        "nonfinancial_total": round(t["nonfinancial"], 2),
        "liquid_total": round(t["liquid"], 2),
        "allocation": allocation(led, counted, t["assets"]),
        "debts_total": round(t["debts"], 2),
        "receivables_weighted": round(t["receivables"], 2),
        "monthly_income": round(income, 2) if income else None,
        "monthly_spending": round(spend, 2) if spend else None,
        "metrics": metrics,
        "components": {k: {"label": LABELS[k], "score": round(v[0]),
                           "weight": WEIGHTS[k], "detail": v[1]}
                       for k, v in comps.items()},
        "flags": [{"code": c, "text": tx} for c, tx in flags],
        "goals": goals,
        "history": history,
        "balances": bal,
    }


# ---------------------------------------------------------------- commands ---

def cmd_init(a):
    p = ledger_path(a.data)
    if os.path.exists(p):
        raise MoneyError(f"{p} already exists; not overwriting.")
    os.makedirs(a.data, exist_ok=True)
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "templates", "ledger.json")
    shutil.copyfile(tpl, p)
    print(f"Created {p}")


def cmd_summary(a):
    led = load(a.data)
    p = led["profile"]
    cur = p.get("currency") or "USD"
    g = lambda k: p.get(k) if p.get(k) not in (None, "") else "—"  # noqa: E731
    out = [f"Name {g('name')} · currency {cur} · age {g('age')} · income {g('income_type')}"
           f" · risk {g('risk_tolerance')} · personality "
           f"{g('money_personality')} · check-ins {g('checkin_frequency')}"]
    if not led["checkins"]:
        out.append("No check-ins yet.")
        print("\n".join(out))
        return
    s = score(led)
    out.append(f"Last check-in {s['date']} ({len(led['checkins'])} total) · "
               f"grade {s['grade']} ({s['score']}) · net worth "
               f"{money(s['net_worth'], cur)}")
    out.append(f"Liquid {money(s['liquid_total'], cur)} · property & other "
               f"non-financial {money(s['nonfinancial_total'], cur)}")
    if len(s["history"]) >= 2:
        h = s["history"][-1]
        out.append(f"Since {s['history'][-2]['date']}: "
                   f"{money(h['change'], cur)} total, of which revaluations "
                   f"{money(h['revaluation'], cur)}; underlying "
                   f"{money(h['underlying'], cur)}")
    amap = {a["name"]: a for a in led["assets"]}
    for sec, title in (("assets", "Have"), ("debts", "Owe"),
                       ("receivables", "Owed to me")):
        items = []
        for k, v in s["balances"][sec].items():
            sh = amap.get(k, {}).get("share") if sec == "assets" else None
            items.append(f"{k} {money(v, cur)}"
                         + (f" ({sh:g}% yours)" if sh not in (None, 100)
                            else ""))
        if items:
            out.append(f"{title}: " + "; ".join(items))
    for g in s["goals"]:
        prog = (f"{g['pct']}% of" if g["pct"] is not None
                else "not linked to a bucket; target")
        out.append(f"Goal {g['name']}: {prog} {money(g['target'], cur)}"
                   + (f" by {g['by']}" if g["by"] else ""))
    if s["flags"]:
        out.append("Flags: " + " | ".join(f["text"] for f in s["flags"]))
    last_note = led["checkins"][-1].get("note")
    if last_note:
        out.append(f"Last note: {last_note}")
    print("\n".join(out))


def cmd_checkin(a):
    led = load(a.data)
    try:
        c = json.loads(a.json)
    except json.JSONDecodeError as e:
        raise MoneyError(f"--json is not valid JSON: {e}")
    hits = list(find_long_numbers(c))
    if hits:
        raise MoneyError("Refusing to save: " + ", ".join(hits) + " looks like "
                         "an account/card/ID number. Remove it (if it's a "
                         "false alarm, rephrase without long digit runs).")
    c["date"] = c.get("date") or date.today().isoformat()
    parse_date(c["date"])
    known = {s: {b["name"] for b in led[s]} for s in SECTIONS}
    bal = c.get("balances", {})
    for s, items in bal.items():
        if s not in SECTIONS:
            raise MoneyError(f"Unknown balance section {s!r}; use {SECTIONS}.")
        for name, v in items.items():
            if name not in known[s]:
                raise MoneyError(
                    f"{name!r} isn't in {s}. Add it to ledger.json first. "
                    f"Known: {sorted(known[s]) or 'none'}")
            items[name] = num(v, f"Balance of {name}")
    for f in ("income", "spending"):
        if c.get(f) is not None:
            c[f] = num(c[f], f)
    if led["checkins"] and c["date"] < led["checkins"][-1]["date"]:
        raise MoneyError(f"Date {c['date']} is before the last check-in "
                         f"({led['checkins'][-1]['date']}).")
    entry = {k: c[k] for k in ("date", "balances", "income", "spending", "note")
             if c.get(k) is not None}
    if led["checkins"] and led["checkins"][-1]["date"] == c["date"]:
        led["checkins"][-1] = entry
        print(f"Replaced check-in for {c['date']}.")
    else:
        led["checkins"].append(entry)
        print(f"Recorded check-in for {c['date']}.")
    save(a.data, led)


def cmd_score(a):
    s = score(load(a.data))
    s.pop("balances")
    s.pop("history") if not a.history else None
    print(json.dumps(s, indent=1, ensure_ascii=False))


def cmd_report(a):
    led = load(a.data)
    s = score(led)
    page = render(led, s, a.message or "", a.step or [])
    a.out = a.out or os.path.join(a.data, "report.html")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {a.out} — grade {s['grade']} ({s['score']})")


# ------------------------------------------------------------------ report ---

BANDS = [  # (grade, low, high, label, color)
    ("F", 0, 39, "Critical", "#c0392b"),
    ("D", 40, 54, "Weak", "#e67e22"),
    ("C", 55, 69, "Fair", "#e0a800"),
    ("B", 70, 84, "Good", "#7cb342"),
    ("A", 85, 100, "Excellent", "#2e7d32"),
]
FLAG_META = {  # code: (category, severity)
    "high_interest_debt": ("Liabilities", "High"),
    "overspending": ("Cash flow", "High"),
    "low_emergency": ("Liquidity", "High"),
    "net_worth_down": ("Net worth", "Medium"),
    "receivables_heavy": ("Receivables", "Medium"),
    "idle_cash": ("Liquidity", "Info"),
    "low_rate_cash": ("Liquidity", "Info"),
    "underwater": ("Liabilities", "High"),
    "concentration": ("Allocation", "Medium"),
    "illiquid_heavy": ("Liquidity", "Medium"),
    "nonfinancial_heavy": ("Allocation", "Info"),
    "stale_valuation": ("Valuation", "Info"),
    "no_valuation_date": ("Valuation", "Info"),
}


def esc(x):
    return html.escape(str(x), quote=True)


def band_of(score_):
    return next(b for b in BANDS if b[1] <= score_ <= b[2])


def compact(v, cur):
    sym = SYMBOLS.get(cur, cur + " ")
    a = abs(v)
    sign = "−" if v < 0 else ""
    if a >= 1e6:
        return f"{sign}{sym}{a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}{sym}{a / 1e3:.0f}k"
    return f"{sign}{sym}{a:.0f}"


def score_band(score_):
    """Segmented band like a bureau score scale, with a marker."""
    idx = next(i for i, b in enumerate(BANDS) if b[1] <= score_ <= b[2])
    lo, hi = BANDS[idx][1], BANDS[idx][2]
    pos = (idx + (score_ - lo) / (hi - lo + 1)) / len(BANDS) * 100
    segs = "".join(
        f'<div class="seg{" on" if i == idx else ""}" '
        f'style="--c:{b[4]}"></div>' for i, b in enumerate(BANDS))
    labels = "".join(
        f'<div class="lab{" on" if i == idx else ""}">'
        f'<span>{b[1]} – {b[2]}</span><b>{b[0]} · {b[3]}</b></div>'
        for i, b in enumerate(BANDS))
    return (f'<div class="band"><div class="segs">{segs}'
            f'<div class="marker" style="left:{pos:.1f}%"></div></div>'
            f'<div class="labs">{labels}</div></div>')


def trend_chart(history, cur):
    W, H, L, R, T, B = 720, 260, 64, 20, 16, 34
    vals = [h["net_worth"] for h in history]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + max(abs(hi) * 0.1, 1), lo - max(abs(lo) * 0.1, 1)
    span = hi - lo
    lo, hi = lo - span * 0.1, hi + span * 0.1
    n = len(vals)

    def x(i):
        return L + (W - L - R) * (i / (n - 1) if n > 1 else 0.5)

    def y(v):
        return T + (H - T - B) * (1 - (v - lo) / (hi - lo))

    grid = ""
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        gy = y(v)
        grid += (f'<line x1="{L}" x2="{W - R}" y1="{gy:.1f}" y2="{gy:.1f}" '
                 f'class="grid"/><text x="{L - 8}" y="{gy + 4:.1f}" '
                 f'text-anchor="end" class="tick">{esc(compact(v, cur))}</text>')
    if lo < 0 < hi:
        grid += (f'<line x1="{L}" x2="{W - R}" y1="{y(0):.1f}" y2="{y(0):.1f}"'
                 ' class="zero"/>')
    step = max(1, (n + 5) // 6)
    xl = "".join(
        f'<text x="{x(i):.1f}" y="{H - 10}" text-anchor='
        f'"{"start" if i == 0 and n > 1 else "end" if i == n - 1 and n > 1 else "middle"}" '
        f'class="tick">{esc(history[i]["date"])}</text>'
        for i in range(n) if i % step == 0 or i == n - 1)
    def series(vs, cls, label):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))
        line = (f'<polyline points="{pts}" class="line {cls}"/>'
                if n > 1 else "")
        dots = "".join(
            f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" class="pt {cls}">'
            f'<title>{esc(history[i]["date"])} · {label}: '
            f'{esc(money(v, cur))}</title></circle>' for i, v in enumerate(vs))
        return line + dots

    return (f'<div class="chartwrap"><svg class="chart" '
            f'viewBox="0 0 {W} {H}" role="img" aria-label="Net worth over '
            f'time">{grid}{xl}{series(vals, "tot", "Net worth")}</svg></div>')


def table(headers, rows, cls="", foot=None, empty="None reported."):
    if not rows:
        return f'<p class="none">{esc(empty)}</p>'
    th = "".join(f"<th>{h}</th>" for h in headers)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                 for r in rows)
    tf = ("<tfoot><tr>" + "".join(f"<td>{c}</td>" for c in foot)
          + "</tr></tfoot>") if foot else ""
    return (f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr>'
            f'</thead><tbody>{tb}</tbody>{tf}</table></div>')


SPECIAL = {"bnpl": "BNPL", "e_wallet": "E-wallet"}


def nice(t):
    t = str(t or "—")
    return esc(SPECIAL.get(t, t.replace("_", " ").capitalize()))


def assets_table(led, bal, counted, m, total):
    """Assets grouped by class with subtotals, ownership and valuation."""
    if not led["assets"]:
        return '<p class="none">No assets reported.</p>'
    heads = ["Asset", "Type", "Ownership", "Valuation basis", "As of",
             "Interest", "Value (your share)"]
    rows = []
    for cls_name, _ in ASSET_CLASSES:
        items = [a for a in led["assets"]
                 if asset_class(a.get("type")) == cls_name]
        if not items:
            continue
        rows.append(f'<tr class="grp"><td colspan="7">{esc(cls_name)}'
                    '</td></tr>')
        sub = 0
        for a in items:
            full = bal["assets"].get(a["name"], 0)
            v = counted.get(a["name"], 0)
            sub += v
            sh = share_of(a) * 100
            liquid = (' <span class="tag" style="--c:#5b6b82">Liquid</span>'
                      if a.get("liquid") and cls_name not in NON_FINANCIAL
                      else "")
            val = m(v) + (f"<br><small>of {m(full)} total</small>"
                          if sh < 100 else "")
            rows.append(
                "<tr>" + "".join(f"<td>{c}</td>" for c in [
                    esc(a["name"]) + liquid, nice(a.get("type")),
                    f"{sh:g}%",
                    nice(a.get("valuation")) if a.get("valuation") else "—",
                    esc(a.get("valued_on") or "—"),
                    f'{a["rate"]:g}%' if a.get("rate") is not None else "—",
                    val]) + "</tr>")
        rows.append(f'<tr class="sub"><td colspan="6">Subtotal · '
                    f'{esc(cls_name)}</td><td>{m(sub)}</td></tr>')
    th = "".join(f"<th>{h}</th>" for h in heads)
    return (f'<div class="tw"><table class="assets"><thead><tr>{th}</tr>'
            f'</thead><tbody>{"".join(rows)}</tbody><tfoot><tr>'
            f'<td colspan="6">Total assets</td><td>{m(total)}</td></tr>'
            f'</tfoot></table></div>')


def font_face_css():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "assets", DISPLAY_FONT)
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""  # falls back to a system condensed sans
    return ("@font-face{font-family:'Plumb Display';font-weight:400;"
            "font-display:block;src:url(data:font/woff2;base64,"
            + b64 + ") format('woff2')}")


def possessive(name):
    name = name.strip()
    return name + ("’" if name[-1:].lower() == "s" else "’s")


def render(led, s, message, steps):
    cur = s["currency"]
    bal = s["balances"]
    prof = led["profile"]
    m = lambda v: esc(money(v, cur))  # noqa: E731
    grade, sc = s["grade"], s["score"]
    band = band_of(sc)
    n_ci = len(led["checkins"])
    who = str(prof.get("name") or "").strip()[:40]
    doc_title = (f"{possessive(who)} Financial Health Report" if who
                 else "Financial Health Report")
    report_no = f"{REPORT_PREFIX}-{s['date'].replace('-', '')}-{n_ci:03d}"
    hist = s["history"]
    change = (hist[-1]["net_worth"] - hist[-2]["net_worth"]
              if len(hist) >= 2 else None)
    under = hist[-1]["underlying"] if len(hist) >= 2 else None

    def signed(v):
        if v is None:
            return "First report"
        return (f'<span class="{"pos" if v >= 0 else "neg"}">'
                f'{"+" if v >= 0 else ""}{m(v)}</span>')

    # Summary of position (two key/value tables, like "Subject Information")
    def kv(rows):
        return ('<table class="kv">' + "".join(
            f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
            + "</table>")

    left = kv([
        ("Net worth", f"<b>{m(s['net_worth'])}</b>"),
        ("Total assets", m(s["assets_total"])),
        ("&nbsp;&nbsp;of which liquid", m(s["liquid_total"])),
        ("&nbsp;&nbsp;of which property &amp; other",
         m(s["nonfinancial_total"])),
        ("Total liabilities", m(s["debts_total"])),
        ("Receivables (weighted)", m(s["receivables_weighted"])),
    ])
    em = s["metrics"].get("emergency_months")
    sr = s["metrics"].get("savings_rate")
    right = kv([
        ("Avg. monthly income", m(s["monthly_income"]) if s["monthly_income"]
         else "—"),
        ("Avg. monthly spending", m(s["monthly_spending"])
         if s["monthly_spending"] else "—"),
        ("Savings rate", f"{sr * 100:.0f}%" if sr is not None else "—"),
        ("Emergency cushion", f"{em:.1f} months" if em is not None else "—"),
        ("Change in net worth", signed(change)),
        ("Underlying change (excl. revaluations)", signed(under)),
    ])

    # Score components
    comp_rows = []
    for c in s["components"].values():
        b = band_of(c["score"])
        comp_rows.append([
            f"<b>{esc(c['label'])}</b>", f"{c['weight'] * 100:.0f}%",
            esc(c["detail"]),
            f'<div class="mini"><span style="width:{c["score"]}%;'
            f'background:{b[4]}"></span></div>',
            f"<b>{c['score']}</b>",
            f'<span class="tag" style="--c:{b[4]}">{b[3]}</span>'])

    # Assets / liabilities / receivables
    counted = counted_assets(led, bal)
    assets_html = assets_table(led, bal, counted, m, s["assets_total"])
    alloc_rows = [[f"<b>{esc(r['class'])}</b>", m(r["value"]),
                   f"{r['pct']:.1f}%",
                   f'<div class="mini"><span style="width:{r["pct"]}%;'
                   f'background:var(--brand)"></span></div>']
                  for r in s["allocation"]]
    eq_rows = []
    for a in led["assets"]:
        v = counted.get(a["name"], 0)
        owed = sum(bal["debts"].get(d["name"], 0) for d in led["debts"]
                   if d.get("secured_by") == a["name"])
        if v <= 0 or (asset_class(a.get("type")) not in NON_FINANCIAL
                      and not owed):
            continue
        eq = v - owed
        eq_rows.append([
            esc(a["name"]), nice(asset_class(a.get("type"))), m(v),
            m(owed) if owed else "—",
            f'{owed / v * 100:.0f}%' if owed else "—",
            f'<span class="{"pos" if eq >= 0 else "neg"}">{m(eq)}</span>'])
    d_rows = [[esc(d["name"]), nice(d.get("type")),
               esc(d["secured_by"]) if d.get("secured_by") else "Unsecured",
               (f'{d["rate"]:g}%' if d.get("rate") is not None else "—")
               + (' <span class="tag" style="--c:#c0392b">High</span>'
                  if (d.get("rate") or 0) >= HIGH_RATE else ""),
               m(d.get("monthly_payment") or 0),
               m(bal["debts"].get(d["name"], 0))] for d in led["debts"]]
    r_rows = [[esc(r["name"]), nice(r.get("likelihood", "unsure")),
               f'{LIKELIHOOD.get(r.get("likelihood", "unsure"), .5) * 100:.0f}%',
               m(bal["receivables"].get(r["name"], 0))]
              for r in led["receivables"]]
    pay_total = sum(d.get("monthly_payment") or 0 for d in led["debts"]
                    if bal["debts"].get(d["name"], 0) > 0)
    rec_total = sum(bal["receivables"].values())

    # Net worth history
    def sg(v):
        return "—" if v is None else signed(v)

    h_rows = [[esc(h["date"]), m(h["net_worth"]), sg(h["change"]),
               "—" if h["revaluation"] is None else m(h["revaluation"]),
               sg(h["underlying"])] for h in hist][::-1][:12]

    # Goals
    g_rows = []
    for g in s["goals"]:
        if g["pct"] is None:
            prog = '<span class="muted">Not linked to an account</span>'
        else:
            prog = (f'<div class="mini"><span style="width:{g["pct"]}%;'
                    f'background:var(--brand)"></span></div> {g["pct"]}%')
        g_rows.append([esc(g["name"]), m(g["target"]), esc(g["by"] or "—"),
                       m(g["current"]) if g["current"] is not None else "—",
                       prog])

    # Observations
    o_rows = []
    for i, f in enumerate([f for f in s["flags"]
                           if f["code"] != "first_checkin"], 1):
        cat, sev = FLAG_META.get(f["code"], ("General", "Info"))
        col = {"High": "#c0392b", "Medium": "#e67e22"}.get(sev, "#5b6b82")
        o_rows.append([str(i), esc(cat), esc(f["text"]),
                       f'<span class="tag" style="--c:{col}">{sev}</span>'])

    actions = table(
        ["No.", "Recommended action", "Done"],
        [[str(i), esc(x), '<span class="box"></span>']
         for i, x in enumerate(steps, 1)], cls="act",
        empty="No actions recorded for this period.")
    assessment = (f'<p class="assess">{esc(message)}</p>' if message else "")

    first_note = ("" if len(hist) >= 2 else
                  '<p class="note">Momentum is scored from the second '
                  'check-in onward; this report re-weights the other '
                  'components.</p>')

    profile_line = " · ".join(x for x in [
        f"Age {esc(prof['age'])}" if prof.get("age") else "",
        ("No current income" if prof.get("income_type") == "none"
         else nice(prof.get("income_type")) + " income")
        if prof.get("income_type") else "",
        f"Risk tolerance: {nice(prof.get('risk_tolerance'))}"
        if prof.get("risk_tolerance") else "",
        f"{nice(prof.get('checkin_frequency'))} check-ins"
        if prof.get("checkin_frequency") else "",
    ] if x)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(doc_title)} · {esc(report_no)}</title>
<style>
{font_face_css()}
:root{{--display:'Plumb Display',"Arial Narrow","Helvetica Neue",Arial,sans-serif;--brand:#1d5a3a;--brand2:#2f7a52;--ink:#1d2a23;--muted:#5b6d62;
--line:#9fb3a7;--soft:#e8f1eb;--strip:#f1f5f2;--bg:#e6ece8;--grp:#d9e9de}}
*{{box-sizing:border-box}}
html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{margin:0;background:var(--bg);color:var(--ink);
font:13.5px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif}}
.page{{max-width:860px;margin:24px auto;background:#fff;padding:36px 40px 28px;
box-shadow:0 1px 3px rgba(0,0,0,.12),0 8px 30px -12px rgba(0,0,0,.25)}}
header.lh{{display:flex;justify-content:space-between;align-items:flex-end;
gap:20px;padding-bottom:12px;border-bottom:1px solid var(--line)}}
.brand{{display:flex;align-items:center;gap:12px}}
.bname{{font:400 46px/.95 var(--display);color:var(--brand);
font-synthesis:none}}
.bsub{{font-size:11px;color:var(--muted);letter-spacing:.06em;
text-transform:uppercase}}
.title{{text-align:right}}
.title h1{{margin:0;font:400 27px/1.15 var(--display);color:#000;
font-synthesis:none}}
.title div{{font-size:11px;color:var(--muted)}}
.meta{{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:3px 18px;
background:var(--strip);padding:9px 12px;margin:14px 0 6px;font-size:12px}}
.meta span{{color:var(--muted)}} .meta b{{color:var(--ink)}}
h2.bar{{background:var(--brand);color:#fff;font-weight:400;font-size:17px;
margin:22px 0 12px;padding:6px 10px}}
h3{{color:var(--brand);font-size:14px;margin:16px 0 6px}}
.scorebox{{background:#f6f9f7;padding:16px 18px 18px;text-align:center}}
.scorebox .cap{{font-weight:700;font-size:13px}}
.big{{display:flex;justify-content:center;align-items:baseline;gap:14px;
margin:6px 0 12px}}
.big .g{{font:400 70px/1 var(--display);color:var(--c);
font-synthesis:none}}
.big .n{{font-size:26px;font-weight:700;color:#555}}
.big .n small{{font-size:14px;color:var(--muted);font-weight:400}}
.band{{max-width:640px;margin:0 auto}}
.segs{{position:relative;display:grid;grid-template-columns:repeat(5,1fr);
height:30px;background:#d5d8dd;border-radius:3px}}
.seg{{border-right:2px solid #fff}} .seg:last-of-type{{border-right:0}}
.seg.on{{background:var(--c)}}
.marker{{position:absolute;top:-7px;width:0;height:0;margin-left:-7px;
border:7px solid transparent;border-top-color:var(--ink)}}
.labs{{display:grid;grid-template-columns:repeat(5,1fr);margin-top:6px}}
.lab{{font-size:11px;color:var(--muted)}} .lab b{{display:block;font-size:13px;
color:#333}} .lab.on b{{color:#000}}
.expl{{font-size:12px;color:var(--brand2);margin:12px 4px 0;text-align:left}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
.tw{{overflow-x:auto}}
th,td{{border:1px solid #2b2b2b;padding:5px 8px;vertical-align:middle}}
thead th{{background:var(--soft);color:var(--brand);font-weight:700;
text-align:center}}
td{{color:var(--ink)}}
tbody td:last-child,tfoot td:last-child{{text-align:right;
font-variant-numeric:tabular-nums}}
tfoot td{{background:var(--strip);font-weight:700}}
table.kv th{{background:var(--soft);color:var(--brand);text-align:left;
width:52%;font-weight:700}}
table.kv td{{text-align:right;font-variant-numeric:tabular-nums}}
table.comp td:nth-child(2),table.comp td:nth-child(5){{text-align:center}}
table.comp td:last-child{{text-align:center}}
table.act td:first-child,table.obs td:first-child{{text-align:center;width:44px}}
table.act td:last-child,table.obs td:last-child{{text-align:center;width:70px}}
.mini{{display:inline-block;width:100%;min-width:80px;height:8px;
background:#dde1e7;border-radius:2px;overflow:hidden;vertical-align:middle}}
.mini span{{display:block;height:100%}}
table.goals td:last-child{{text-align:left;min-width:150px}}
table.goals .mini{{width:70%}}
.tag{{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;
border-radius:2px;color:#fff;background:var(--c);white-space:nowrap}}
.pos{{color:#2e7d32;font-weight:700}} .neg{{color:#c0392b;font-weight:700}}
.muted{{color:var(--muted)}} .none{{color:var(--muted);font-style:italic;
margin:4px 0}}
.note{{font-size:11.5px;color:var(--muted);margin:6px 0 0}}
.assess{{border-left:4px solid var(--brand);background:#f6f9f7;margin:0 0 12px;
padding:10px 14px;font-size:13.5px}}
.box{{display:inline-block;width:13px;height:13px;border:1.5px solid #333}}
.chartwrap{{overflow-x:auto;border:1px solid #2b2b2b;padding:8px 4px 0}}
.chart{{display:block;width:100%;min-width:520px;height:auto}}
.chart .grid{{stroke:#e1e5ea}} .chart .zero{{stroke:#888;stroke-dasharray:4 3}}
.chart .tick{{font-size:11px;fill:var(--muted)}}
.chart .line{{fill:none;stroke:var(--brand);stroke-width:2.5}}
.chart .pt{{fill:#fff;stroke:var(--brand);stroke-width:2}}
tr.grp td{{background:var(--grp);color:var(--brand);font-weight:700;
text-align:left!important}}
tr.sub td{{background:var(--strip);font-weight:700}}
tr.sub td:first-child{{text-align:right}}
td small{{color:var(--muted);font-size:10.5px;white-space:nowrap}}
table.alloc td:nth-child(2),table.alloc td:nth-child(3){{text-align:right}}
table.alloc td:last-child{{width:38%}}
table.hist td:not(:first-child){{text-align:right}}
footer{{margin-top:30px;border-top:2px solid var(--brand);padding-top:6px}}
footer .url{{text-align:right;font-weight:700;color:var(--brand);font-size:13px}}
footer p{{margin:4px 0 0;font-size:8.5px;line-height:1.35;color:#333;
text-transform:uppercase;text-align:justify}}
.avoid{{break-inside:avoid}}
@media (max-width:700px){{.page{{margin:0;padding:20px 16px;box-shadow:none}}
header.lh{{flex-direction:column;align-items:flex-start}}
.title{{text-align:left}} .two{{grid-template-columns:1fr}}
.meta{{grid-template-columns:auto 1fr}} .lab span{{display:none}}
.lab b{{font-size:11px}} .tw table{{min-width:600px}}
.tw table.act,.tw table.obs{{min-width:0}}}}
@media print{{@page{{size:letter;margin:12mm}} body{{background:#fff}}
.page{{margin:0;max-width:none;box-shadow:none;padding:0}}
h2.bar{{break-after:avoid}} .chartwrap{{overflow:visible}}}}
</style></head><body><div class="page">

<header class="lh">
 <div class="brand"><div><div class="bname">{esc(BRAND_NAME)}</div>
  <div class="bsub">{esc(BRAND_TAGLINE)}</div></div></div>
 <div class="title"><h1>{esc(doc_title)}</h1>
  <div>Self-reported data · Generated locally</div></div>
</header>

<div class="meta">
 <span>Prepared for</span><b>{esc(who) or '—'}</b>
 <span>Report date</span><b>{esc(s['date'])}</b>
 <span>Report number</span><b>{esc(report_no)}</b>
 <span>Grade</span><b>{grade} · {band[3]}</b>
 <span>Check-ins on record</span><b>{n_ci}</b>
 <span>Currency</span><b>{esc(cur)}</b>
 <span>Profile</span><b style="grid-column:2 / -1">{profile_line or '—'}</b>
</div>

<h2 class="bar">Financial Health Score</h2>
<div class="scorebox avoid">
 <div class="cap">Overall Grade</div>
 <div class="big" style="--c:{band[4]}"><span class="g">{grade}</span>
  <span class="n">{sc}<small> / 100</small></span></div>
 {score_band(sc)}
 <p class="expl">The {esc(BRAND_NAME)} score is a weighted average of four
 components: emergency cushion (30%), debt health (30%), savings rate (25%)
 and momentum (15%). Each is measured against common rules of thumb. Age,
 risk tolerance and personality inform recommendations but do not change the
 score.</p>
</div>

<h2 class="bar">Assessment &amp; Recommended Actions</h2>
{assessment}
{actions}

<h2 class="bar">Summary of Financial Position</h2>
<div class="two">{left}{right}</div>

<h2 class="bar">Score Components</h2>
{table(["Component", "Weight", "Measure", "Rating bar", "Score", "Rating"],
       comp_rows, cls="comp")}
{first_note}

<h2 class="bar">Observations</h2>
{table(["No.", "Category", "Observation", "Severity"], o_rows, cls="obs",
       empty="No issues flagged for this period.")}

<h2 class="bar">Net Worth History</h2>
<div class="avoid">{trend_chart(hist, cur)}</div>
<h3>Recent check-ins</h3>
{table(["Check-in date", "Net worth", "Change", "Of which revaluations",
        "Underlying change"], h_rows, cls="hist")}
<p class="note">Revaluations are changes in the estimated value of property,
vehicles, business interests and valuables held at both check-ins. They are
excluded from the Momentum score.</p>

<h2 class="bar">Asset Allocation</h2>
{table(["Asset class", "Value (your share)", "Share of assets", "Allocation"],
       alloc_rows, cls="alloc", empty="No assets reported.")}

<h2 class="bar">Assets</h2>
{assets_html}

{('<h2 class="bar">Property &amp; Equity</h2>' + table(
    ["Asset", "Class", "Value (your share)", "Secured debt", "Loan-to-value",
     "Equity"], eq_rows)) if eq_rows else ""}

<h2 class="bar">Liabilities</h2>
{table(["Account", "Type", "Secured by", "Interest", "Monthly payment",
        "Balance"], d_rows,
       foot=["Total", "", "", "", m(pay_total), m(s["debts_total"])],
       empty="No liabilities reported.")}

<h2 class="bar">Receivables (Money Owed to You)</h2>
{table(["Owed by", "Likelihood of repayment", "Counted at", "Amount"], r_rows,
       foot=["Total", "", "", m(rec_total)],
       empty="No receivables reported.")}

<h2 class="bar">Goals</h2>
{table(["Goal", "Target", "Target date", "Saved", "Progress"], g_rows,
       cls="goals", empty="No goals set.")}

<footer>
 <div class="url">{esc(BRAND_NAME)} · Financial Health Report</div>
 <p>This report was generated by {esc(BRAND_NAME)}, an open-source educational
 self-assessment tool, from information supplied by the user. It has not been
 verified by any third party and is not a credit report, credit score or
 statement from any bank, bureau or financial institution. {esc(BRAND_NAME)} is not
 a licensed financial advisor and this report is not financial, investment,
 tax, insurance or legal advice. Grades are based on general rules of thumb
 that may not suit every situation. Consult a licensed professional before
 making financial decisions. This document contains personal financial
 information: store it privately and share it only by choice.</p>
</footer>
</div></body></html>
"""


# -------------------------------------------------------------------- main ---

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default="plumb-data",
                    help="folder holding ledger.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create an empty ledger")
    sub.add_parser("summary", help="compact text of the latest state")
    p = sub.add_parser("checkin", help="append a check-in")
    p.add_argument("--json", required=True)
    p = sub.add_parser("score", help="grade and flags as JSON")
    p.add_argument("--history", action="store_true",
                   help="include net-worth history")
    p = sub.add_parser("report", help="write the HTML report card")
    p.add_argument("--out", help="default: <data>/report.html")
    p.add_argument("--message")
    p.add_argument("--step", action="append")
    # allow --data after the subcommand too
    for sp in sub.choices.values():
        sp.add_argument("--data", default=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    try:
        {"init": cmd_init, "summary": cmd_summary, "checkin": cmd_checkin,
         "score": cmd_score, "report": cmd_report}[a.cmd](a)
    except MoneyError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

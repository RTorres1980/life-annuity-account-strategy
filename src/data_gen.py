"""Synthetic CRM data for a book of life insurance and annuity accounts.

Every firm, person and number here is invented. The generator is seeded so
each run produces the same book, and it plants a few known situations
(an at-risk renewal, a deal with no economic buyer, a stalled expansion)
so the tests can check that the toolkit finds them.
"""
from datetime import date, timedelta
import random

import pandas as pd

AS_OF = date(2026, 10, 1)

MODULES = [
    "E-Application",
    "Order Entry",
    "Suitability Review",
    "Licensing & Appointments",
    "In-Force Data Feed",
    "Annuity Illustrations",
    "Distribution Analytics",
]

SEGMENTS = ["Carrier", "IMO", "BGA", "Broker-Dealer"]

FIRST = ["Avery", "Jordan", "Morgan", "Casey", "Riley", "Quinn", "Taylor", "Reese",
         "Hayden", "Parker", "Rowan", "Drew", "Emerson", "Finley", "Sawyer", "Blake"]
LAST = ["Hale", "Mercer", "Lowell", "Ashby", "Kerr", "Sutton", "Vance", "Prescott",
        "Whitaker", "Calder", "Brennan", "Holt", "Marsh", "Delaney", "Foster", "Graves"]

FIRMS = [
    ("Northbridge Life", "Carrier"), ("Summit Mutual", "Carrier"),
    ("Keystone Annuity Co.", "Carrier"), ("Harborline Life & Annuity", "Carrier"),
    ("Granite Peak Insurance", "Carrier"), ("Bluewater Financial Life", "Carrier"),
    ("Meridian Brokerage Group", "IMO"), ("Pinnacle Marketing Partners", "IMO"),
    ("Crestview Annuity Marketing", "IMO"), ("Frontier Producer Network", "IMO"),
    ("Lakeside BGA", "BGA"), ("Copperline Brokerage", "BGA"),
    ("Westgate Insurance Services", "BGA"), ("Redwood Securities", "Broker-Dealer"),
    ("Atlas Investor Services", "Broker-Dealer"), ("Cobalt Wealth Partners", "Broker-Dealer"),
]

ROLES = ["Economic Buyer", "Champion", "Operations Lead", "Technology Lead",
         "Distribution Lead", "Compliance Lead"]

STAGES = ["Discovery", "Qualification", "Solution Design", "Business Case",
          "Negotiation", "Closed Won", "Closed Lost"]

MEDDPICC = ["metrics", "economic_buyer", "decision_criteria", "decision_process",
            "paper_process", "identify_pain", "champion", "competition"]

# What a well-run deal usually has confirmed by each stage (mirrors src/meddpicc.py).
REQUIRED_BY_STAGE_HINT = {
    "Qualification": ["identify_pain"],
    "Solution Design": ["identify_pain", "champion", "decision_criteria"],
    "Business Case": ["identify_pain", "champion", "decision_criteria", "metrics", "economic_buyer"],
    "Negotiation": ["identify_pain", "champion", "decision_criteria", "metrics", "economic_buyer",
                    "decision_process", "paper_process"],
}


def _people(rng, n):
    return [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(n)]


def generate(seed=7):
    """Return a dict of DataFrames: accounts, contacts, opportunities, activities."""
    rng = random.Random(seed)
    accounts, contacts, opps, activities = [], [], [], []

    for i, (name, segment) in enumerate(FIRMS, start=1):
        acct_id = f"A{i:03d}"
        is_client = i <= 11
        modules = rng.sample(MODULES, rng.randint(2, 5)) if is_client else []
        arr = round(sum(rng.uniform(60, 220) for _ in modules), 1) * 1000 if is_client else 0
        accounts.append({
            "account_id": acct_id,
            "account": name,
            "segment": segment,
            "status": "Client" if is_client else "Prospect",
            "annual_premium_bn": round(rng.uniform(0.4, 9.5), 1),
            "modules": ";".join(modules),
            "arr": arr,
            "renewal_date": (AS_OF + timedelta(days=rng.randint(30, 420))) if is_client else None,
            "seat_usage_pct": round(rng.uniform(55, 98), 0) if is_client else None,
            "usage_trend_pct": round(rng.uniform(-6, 18), 1) if is_client else None,
            "nps": rng.randint(5, 10) if is_client else None,
            "open_escalations": rng.choice([0, 0, 0, 1, 1, 2]) if is_client else 0,
            "nigo_rate_pct": round(rng.uniform(4, 14), 1) if is_client else None,
        })
        for role, person in zip(rng.sample(ROLES, rng.randint(3, 5)), _people(rng, 5)):
            contacts.append({
                "account_id": acct_id,
                "name": person,
                "role": role,
                "last_meeting": AS_OF - timedelta(days=rng.randint(3, 160)),
            })

    # Planted situations the tests rely on.
    a = {r["account_id"]: r for r in accounts}
    a["A002"].update(usage_trend_pct=-9.5, nps=4, open_escalations=3,
                     renewal_date=AS_OF + timedelta(days=75))          # renewal at risk
    a["A001"].update(usage_trend_pct=14.0, nps=10, open_escalations=0,
                     seat_usage_pct=96.0)                              # healthy, expansion-ready
    contacts = [c for c in contacts if not (c["account_id"] == "A002" and c["role"] == "Economic Buyer")]
    contacts.append({"account_id": "A002", "name": "Dana Whitcomb", "role": "Economic Buyer",
                     "last_meeting": AS_OF - timedelta(days=150)})

    opp_n = 0
    for acct in accounts:
        kinds = (["Expansion", "Renewal"] if acct["status"] == "Client" else ["New Business"])
        for kind in kinds:
            if kind == "Renewal" and acct["renewal_date"] and \
                    (acct["renewal_date"] - AS_OF).days > 300:
                continue
            opp_n += 1
            stage = rng.choice(STAGES[:5] + ["Closed Won", "Closed Lost"] if kind != "Renewal"
                               else ["Business Case", "Negotiation", "Solution Design"])
            if kind == "Renewal":
                amount, close = acct["arr"], acct["renewal_date"]
            else:
                amount = round(rng.uniform(90, 650)) * 1000
                close = AS_OF + timedelta(days=rng.randint(-40, 330))
            row = {
                "opp_id": f"O{opp_n:03d}",
                "account_id": acct["account_id"],
                "type": kind,
                "stage": stage,
                "amount": amount,
                "close_date": close,
                "stage_age_days": rng.randint(5, 55),
            }
            # Deals further along have more of MEDDPICC confirmed, as in a real book.
            depth = STAGES.index(stage) if stage in STAGES[:5] else 4
            for j, m in enumerate(MEDDPICC):
                confirmed = rng.random() < 0.55 + depth * 0.1
                row[m] = 2 if confirmed else rng.choice([0, 1, 1])
            for m in REQUIRED_BY_STAGE_HINT.get(stage, []):
                if rng.random() < 0.85:
                    row[m] = 2
            opps.append(row)

    o = {r["opp_id"]: r for r in opps}
    # O-for-A003 expansion: late stage, no economic buyer, no paper process.
    target = next(r for r in opps if r["account_id"] == "A003" and r["type"] == "Expansion")
    target.update(stage="Negotiation", economic_buyer=0, paper_process=0, champion=2,
                  close_date=AS_OF + timedelta(days=20), amount=410000)
    # A fully qualified new-business deal.
    nb = next(r for r in opps if r["account_id"] == "A013")
    nb.update(stage="Business Case", amount=520000, close_date=AS_OF + timedelta(days=95),
              stage_age_days=18, **{m: 2 for m in MEDDPICC})
    # A stalled expansion.
    st = next(r for r in opps if r["account_id"] == "A001" and r["type"] == "Expansion")
    st.update(stage="Solution Design", stage_age_days=110, close_date=AS_OF + timedelta(days=60))
    del o

    for c in contacts:
        for _ in range(rng.randint(0, 3)):
            activities.append({
                "account_id": c["account_id"],
                "contact": c["name"],
                "type": rng.choice(["Meeting", "Call", "Email", "Business Review"]),
                "date": AS_OF - timedelta(days=rng.randint(1, 180)),
            })

    return {
        "accounts": pd.DataFrame(accounts),
        "contacts": pd.DataFrame(contacts),
        "opportunities": pd.DataFrame(opps),
        "activities": pd.DataFrame(activities),
    }


def save_csv(tables, folder):
    for name, df in tables.items():
        df.to_csv(f"{folder}/{name}.csv", index=False)

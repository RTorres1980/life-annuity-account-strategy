"""Mutual Action Plan builder.

Works backward from a target close date to lay out the joint steps a
life or annuity firm and the vendor take to reach a signed contract and a
kickoff, with an owner on each side. If there is not enough time left to
fit the standard durations, the plan says so and shows the realistic date.
"""
from datetime import timedelta

import pandas as pd

from .data_gen import AS_OF

# (milestone, client owner, vendor owner, working days the step usually needs)
STEPS = [
    ("Confirm business case and success metrics", "Economic Buyer", "Account Executive", 10),
    ("Solution demonstration for distribution and operations", "Distribution Lead", "Solutions Consultant", 5),
    ("Integration and data review (carrier systems, in-force feeds)", "Technology Lead", "Sales Engineer", 10),
    ("Information security and vendor risk review", "Technology Lead", "Security Team", 15),
    ("Compliance review of suitability and e-application workflows", "Compliance Lead", "Product Specialist", 10),
    ("Commercial proposal and pricing approval", "Economic Buyer", "Account Executive", 5),
    ("Contract redlines and legal approval", "Legal / Procurement", "Deal Desk", 15),
    ("Signature", "Economic Buyer", "Account Executive", 2),
    ("Implementation kickoff and launch plan", "Operations Lead", "Client Delivery", 5),
]


def _back(d, workdays):
    """Move a date back by business days."""
    while workdays > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            workdays -= 1
    return d


def _fwd(d, workdays):
    while workdays > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            workdays -= 1
    return d


def build_plan(opp_id, account, close_date, start=AS_OF):
    """Return (plan DataFrame, feasibility note)."""
    sign_idx = [s[0] for s in STEPS].index("Signature")
    pre, post = STEPS[:sign_idx + 1], STEPS[sign_idx + 1:]

    rows, end = [], close_date
    for name, client, vendor, days in reversed(pre):
        begin = _back(end, days)
        rows.append((name, client, vendor, begin, end))
        end = begin
    rows.reverse()
    begin = close_date
    for name, client, vendor, days in post:
        finish = _fwd(begin, days)
        rows.append((name, client, vendor, begin, finish))
        begin = finish

    first_start = rows[0][3]
    if first_start < start:
        needed = sum(s[3] for s in pre)
        realistic = _fwd(start, needed)
        note = (f"Compressed: the plan needs to start {first_start:%b %d, %Y}, before today. "
                f"Realistic signature date is {realistic:%b %d, %Y} unless steps run in parallel.")
    else:
        note = f"On track: first step starts {first_start:%b %d, %Y}."

    plan = pd.DataFrame(rows, columns=["milestone", "client_owner", "vendor_owner", "start", "due"])
    plan.insert(0, "account", account)
    plan.insert(0, "opp_id", opp_id)
    plan["status"] = ["Not started"] * len(plan)
    return plan, note

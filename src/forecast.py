"""Pipeline forecast: stage-weighted, MEDDPICC-adjusted, with forecast categories.

Stage probabilities set the base odds. Qualification then moves them:
a deal missing what its stage requires is discounted, a fully qualified
deal is lifted slightly. Deals sit in Commit, Best Case or Pipeline, and
stalled deals are called out separately.
"""
import pandas as pd

from .data_gen import AS_OF

STAGE_PROB = {
    "Discovery": 0.10,
    "Qualification": 0.20,
    "Solution Design": 0.35,
    "Business Case": 0.55,
    "Negotiation": 0.75,
}

QUAL_ADJ = {"Qualified": 1.10, "Developing": 1.00, "At Risk": 0.60}

# Typical days a deal should spend in a stage before it is considered stalled.
STALL_DAYS = {"Discovery": 45, "Qualification": 45, "Solution Design": 60,
              "Business Case": 60, "Negotiation": 45}


def quarter(d):
    d = pd.Timestamp(d)
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def category(stage, qualification):
    if stage == "Negotiation" and qualification != "At Risk":
        return "Commit"
    if stage in ("Business Case", "Negotiation"):
        return "Best Case"
    return "Pipeline"


HEALTH_ADJ = {"Green": 1.0, "Yellow": 0.9, "Red": 0.6}


def build(opps, qualification, health=None):
    """Join opportunities to qualification and compute weighted values.

    If account health is supplied, renewals and expansions at Yellow or Red
    accounts are discounted, and a Red account's renewal is never Commit.
    """
    q = qualification.set_index("opp_id")
    tiers = health.set_index("account_id").tier if health is not None else {}
    rows = []
    for row in opps[opps.stage.isin(STAGE_PROB)].itertuples():
        qual = q.loc[row.opp_id, "qualification"]
        acct_tier = tiers.get(row.account_id, "Green") if row.type != "New Business" else "Green"
        prob = min(0.95, STAGE_PROB[row.stage] * QUAL_ADJ[qual] * HEALTH_ADJ[acct_tier])
        overdue = pd.Timestamp(row.close_date) < pd.Timestamp(AS_OF)
        rows.append({
            "opp_id": row.opp_id,
            "account_id": row.account_id,
            "type": row.type,
            "stage": row.stage,
            "amount": row.amount,
            "close_date": pd.Timestamp(row.close_date).date(),
            "close_quarter": quarter(row.close_date),
            "qualification": qual,
            "probability": round(prob, 2),
            "weighted": round(row.amount * prob),
            "account_tier": acct_tier,
            "category": "Best Case" if (acct_tier == "Red" and category(row.stage, qual) == "Commit")
            else category(row.stage, qual),
            "stalled": row.stage_age_days > STALL_DAYS[row.stage],
            "close_date_past_due": overdue,
        })
    return pd.DataFrame(rows)


def summary(forecast, target_by_quarter):
    """Roll the forecast up by quarter and compare it with targets."""
    rows = []
    for qtr, target in target_by_quarter.items():
        f = forecast[forecast.close_quarter == qtr]
        commit = f.loc[f.category == "Commit", "amount"].sum()
        best = commit + f.loc[f.category == "Best Case", "amount"].sum()
        pipeline = f.amount.sum()
        rows.append({
            "quarter": qtr,
            "target": target,
            "commit": commit,
            "best_case": best,
            "total_pipeline": pipeline,
            "weighted_forecast": f.weighted.sum(),
            "pipeline_coverage": round(pipeline / target, 2) if target else None,
            "gap_to_target_weighted": target - f.weighted.sum(),
        })
    return pd.DataFrame(rows)

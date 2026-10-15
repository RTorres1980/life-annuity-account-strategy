"""MEDDPICC deal qualification.

Each element is scored 0 (unknown), 1 (partly confirmed) or 2 (confirmed).
The toolkit totals the score, checks it against what the deal's stage
should already have in place, and turns every gap into a next action.
"""
import pandas as pd

ELEMENTS = {
    "metrics": "Metrics",
    "economic_buyer": "Economic Buyer",
    "decision_criteria": "Decision Criteria",
    "decision_process": "Decision Process",
    "paper_process": "Paper Process",
    "identify_pain": "Identify Pain",
    "champion": "Champion",
    "competition": "Competition",
}

# Elements that must be confirmed (score 2) by the time a deal reaches a stage.
REQUIRED_BY_STAGE = {
    "Discovery": [],
    "Qualification": ["identify_pain"],
    "Solution Design": ["identify_pain", "champion", "decision_criteria"],
    "Business Case": ["identify_pain", "champion", "decision_criteria", "metrics",
                      "economic_buyer"],
    "Negotiation": ["identify_pain", "champion", "decision_criteria", "metrics",
                    "economic_buyer", "decision_process", "paper_process"],
}

NEXT_ACTION = {
    "metrics": "Quantify the outcome with the client (e.g. NIGO rate, cycle time, cost per app) and agree a baseline.",
    "economic_buyer": "Secure a meeting with the economic buyer; ask the champion to sponsor the introduction.",
    "decision_criteria": "Document the client's written evaluation criteria and map each to a capability.",
    "decision_process": "Map every approval step, owner and date from evaluation to signature.",
    "paper_process": "Engage procurement, legal and information security now; confirm contract and review timelines.",
    "identify_pain": "Run a discovery session to confirm the business problem and its cost.",
    "champion": "Identify and test a champion with influence who will sell internally.",
    "competition": "Confirm alternatives under consideration, including doing nothing or building in-house.",
}

OPEN_STAGES = list(REQUIRED_BY_STAGE)


def qualify(opps):
    """Return one row per open opportunity with score, gaps, status and actions."""
    rows = []
    for row in opps[opps.stage.isin(OPEN_STAGES)].itertuples():
        scores = {k: getattr(row, k) for k in ELEMENTS}
        total = sum(scores.values())
        stage_gaps = [k for k in REQUIRED_BY_STAGE[row.stage] if scores[k] < 2]
        weak = [k for k in ELEMENTS if scores[k] == 0]
        if stage_gaps:
            status = "At Risk"
        elif total >= 13:
            status = "Qualified"
        else:
            status = "Developing"
        gaps = list(dict.fromkeys(stage_gaps + weak))
        rows.append({
            "opp_id": row.opp_id,
            "account_id": row.account_id,
            "stage": row.stage,
            "meddpicc_score": total,
            "meddpicc_pct": round(total / 16 * 100),
            "qualification": status,
            "stage_gaps": "; ".join(ELEMENTS[k] for k in stage_gaps),
            "next_actions": " | ".join(NEXT_ACTION[k] for k in gaps[:3]),
        })
    return pd.DataFrame(rows)

"""Account health scoring for client accounts.

Each client gets a 0-100 score built from five weighted signals, a
Green/Yellow/Red tier, and plain-language risk flags a seller can act on.
"""
import pandas as pd

from .data_gen import AS_OF

WEIGHTS = {
    "adoption": 0.25,       # how much of the licensed platform is used
    "momentum": 0.20,       # usage trend over the last two quarters
    "sentiment": 0.20,      # NPS
    "support": 0.15,        # open escalations
    "executive": 0.20,      # how recently we met the economic buyer
}


def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def executive_recency(contacts, account_id):
    """Days since the last meeting with the account's economic buyer (None if none mapped)."""
    eb = contacts[(contacts.account_id == account_id) & (contacts.role == "Economic Buyer")]
    if eb.empty:
        return None
    return int((pd.Timestamp(AS_OF) - pd.to_datetime(eb.last_meeting).max()).days)


def component_scores(row, eb_days):
    adoption = _clip((row.seat_usage_pct - 50) * 2)
    momentum = _clip(50 + row.usage_trend_pct * 4)
    sentiment = _clip((row.nps - 3) / 7 * 100)
    support = _clip(100 - row.open_escalations * 35)
    executive = 0.0 if eb_days is None else _clip(100 - max(0, eb_days - 30) * 0.9)
    return {"adoption": adoption, "momentum": momentum, "sentiment": sentiment,
            "support": support, "executive": executive}


def tier(score):
    if score >= 70:
        return "Green"
    if score >= 50:
        return "Yellow"
    return "Red"


def risk_flags(row, eb_days):
    flags = []
    days_to_renewal = (pd.Timestamp(row.renewal_date) - pd.Timestamp(AS_OF)).days
    if row.usage_trend_pct < 0:
        flags.append(f"Usage down {abs(row.usage_trend_pct):.1f}%")
    if row.nps <= 6:
        flags.append(f"Detractor NPS ({int(row.nps)})")
    if row.open_escalations >= 2:
        flags.append(f"{row.open_escalations} open escalations")
    if eb_days is None:
        flags.append("No economic buyer mapped")
    elif eb_days > 90:
        flags.append(f"No economic buyer meeting in {eb_days} days")
    if days_to_renewal <= 120:
        flags.append(f"Renewal in {days_to_renewal} days")
    return flags


def score_accounts(accounts, contacts):
    """Return one row per client with component scores, total, tier and flags."""
    rows = []
    for row in accounts[accounts.status == "Client"].itertuples():
        eb_days = executive_recency(contacts, row.account_id)
        comps = component_scores(row, eb_days)
        total = round(sum(comps[k] * w for k, w in WEIGHTS.items()), 1)
        flags = risk_flags(row, eb_days)
        days_to_renewal = (pd.Timestamp(row.renewal_date) - pd.Timestamp(AS_OF)).days
        rows.append({
            "account_id": row.account_id,
            "account": row.account,
            "segment": row.segment,
            "arr": row.arr,
            "health_score": total,
            "tier": tier(total),
            "renewal_at_risk": tier(total) == "Red" and days_to_renewal <= 180,
            "days_to_renewal": days_to_renewal,
            "risk_flags": "; ".join(flags),
            **{f"{k}_score": round(v, 1) for k, v in comps.items()},
        })
    return pd.DataFrame(rows).sort_values("health_score").reset_index(drop=True)


def whitespace(accounts, all_modules):
    """Modules each client does not yet use: the expansion map."""
    out = []
    for row in accounts[accounts.status == "Client"].itertuples():
        owned = set(row.modules.split(";")) if row.modules else set()
        out.append({"account_id": row.account_id, "account": row.account,
                    "modules_owned": len(owned),
                    "whitespace": "; ".join(m for m in all_modules if m not in owned)})
    return pd.DataFrame(out)

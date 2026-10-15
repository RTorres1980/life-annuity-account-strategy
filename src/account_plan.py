"""Strategic account plan and business review pack, one Markdown file per account."""
import pandas as pd


def _money(x):
    return f"${x / 1000:,.0f}K" if x < 1_000_000 else f"${x / 1_000_000:,.2f}M"


def render(account, health_row, contacts, qual, fcst, ws_row, plan_notes):
    """Build the Markdown text for one account."""
    a = account
    lines = [f"# {a.account} — Strategic Account Plan", ""]
    lines += [f"**Segment:** {a.segment}  ", f"**Status:** {a.status}  ",
              f"**Annual premium:** ${a.annual_premium_bn}B"]
    if a.status == "Client":
        h = health_row
        lines[-1] += "  "
        lines += [f"**Annual recurring revenue:** {_money(a.arr)}  ",
                  f"**Renewal:** {pd.Timestamp(a.renewal_date):%b %d, %Y} ({h.days_to_renewal} days)", ""]
        lines += ["## Account health", "",
                  f"**{h.health_score} / 100 — {h.tier}**", "",
                  "| Signal | Score |", "|---|---|"]
        for k in ["adoption", "momentum", "sentiment", "support", "executive"]:
            lines.append(f"| {k.title()} | {getattr(h, k + '_score')} |")
        lines += ["", "**Risks:** " + (h.risk_flags or "None flagged"), ""]
        lines += ["## Whitespace (modules not yet adopted)", "",
                  ws_row.whitespace or "Fully adopted", ""]
    else:
        lines.append("")

    lines += ["## Relationship map", "", "| Contact | Role | Last meeting |", "|---|---|---|"]
    for c in contacts.sort_values("role").itertuples():
        lines.append(f"| {c.name} | {c.role} | {pd.Timestamp(c.last_meeting):%b %d, %Y} |")
    if "Economic Buyer" not in set(contacts.role):
        lines += ["", "> No economic buyer mapped. Priority: identify and meet them."]
    lines.append("")

    lines += ["## Opportunities", ""]
    if fcst.empty:
        lines += ["No open opportunities.", ""]
    else:
        lines += ["| Opp | Type | Stage | Amount | Close | MEDDPICC | Category |",
                  "|---|---|---|---|---|---|---|"]
        for f in fcst.itertuples():
            qrow = qual[qual.opp_id == f.opp_id].iloc[0]
            lines.append(f"| {f.opp_id} | {f.type} | {f.stage} | {_money(f.amount)} | "
                         f"{f.close_date:%b %d, %Y} | {qrow.meddpicc_score}/16 ({qrow.qualification}) | "
                         f"{f.category} |")
        lines.append("")
    lines += ["## Action plan", ""]
    if a.status == "Client" and health_row is not None and health_row.tier == "Red":
        lines += ["**Retention plan (account health is Red):**",
                  "- Hold an executive business review with the economic buyer within 30 days.",
                  "- Assign an owner and date to every open escalation and report progress weekly.",
                  "- Agree a written adoption recovery plan with the operations lead.",
                  "- Do not pursue expansion until the renewal is secure.", ""]
    any_action = False
    for f in fcst.itertuples():
        qrow = qual[qual.opp_id == f.opp_id].iloc[0]
        items = qrow.next_actions.split(" | ") if qrow.next_actions else []
        if f.stalled:
            items.append(f"In {f.stage} longer than expected. Agree a dated next step with the "
                         "champion or re-qualify.")
        if f.opp_id in plan_notes:
            items.append(f"Mutual Action Plan: {plan_notes[f.opp_id]}")
        if items:
            any_action = True
            lines.append(f"**{f.opp_id} ({f.type}, {f.stage}):**")
            lines += [f"- {i}" for i in items]
            lines.append("")
    if not any_action and not (a.status == "Client" and health_row is not None
                               and health_row.tier == "Red"):
        lines += ["No open actions.", ""]

    lines += ["## Business review agenda", "",
              "1. Outcomes delivered since the last review, against agreed metrics",
              "2. Adoption and usage by module; NIGO and cycle-time trends",
              "3. Open issues and escalations, with owners and dates",
              "4. Roadmap items relevant to the client's priorities",
              "5. Next-quarter goals and joint commitments", ""]
    return "\n".join(lines)

"""Run the full toolkit: generate the book, score it, and write the outputs."""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import account_plan, action_plan, data_gen, forecast, health, meddpicc  # noqa: E402

TARGETS = {"2026-Q4": 900_000, "2027-Q1": 1_100_000, "2027-Q2": 1_200_000, "2027-Q3": 1_200_000}


def main(out_dir="output", data_dir="data"):
    out, data = Path(out_dir), Path(data_dir)
    (out / "account_plans").mkdir(parents=True, exist_ok=True)
    data.mkdir(exist_ok=True)

    t = data_gen.generate()
    data_gen.save_csv(t, data)
    accts, contacts, opps = t["accounts"], t["contacts"], t["opportunities"]

    hs = health.score_accounts(accts, contacts)
    ws = health.whitespace(accts, data_gen.MODULES)
    qual = meddpicc.qualify(opps)
    fc = forecast.build(opps, qual, hs)
    summ = forecast.summary(fc, TARGETS)

    plans, notes = [], {}
    names = accts.set_index("account_id").account
    for f in fc[fc.stage.isin(["Business Case", "Negotiation"])].itertuples():
        plan, note = action_plan.build_plan(f.opp_id, names[f.account_id], f.close_date)
        plans.append(plan)
        notes[f.opp_id] = note
    maps = pd.concat(plans, ignore_index=True) if plans else pd.DataFrame()

    for a in accts.itertuples():
        h = hs[hs.account_id == a.account_id]
        w = ws[ws.account_id == a.account_id]
        text = account_plan.render(
            a, h.iloc[0] if len(h) else None, contacts[contacts.account_id == a.account_id],
            qual, fc[fc.account_id == a.account_id], w.iloc[0] if len(w) else None, notes)
        slug = a.account.replace(" ", "_").replace("&", "and").replace(".", "")
        (out / "account_plans" / f"{a.account_id}_{slug}.md").write_text(text, encoding="utf-8")

    with pd.ExcelWriter(out / "account_strategy_workbook.xlsx") as xw:
        summ.to_excel(xw, sheet_name="Forecast Summary", index=False)
        fc.merge(names.rename("account"), left_on="account_id", right_index=True) \
          .to_excel(xw, sheet_name="Pipeline", index=False)
        hs.to_excel(xw, sheet_name="Account Health", index=False)
        qual.to_excel(xw, sheet_name="MEDDPICC", index=False)
        ws.to_excel(xw, sheet_name="Whitespace", index=False)
        maps.to_excel(xw, sheet_name="Mutual Action Plans", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(summ))
    ax.bar([i - 0.2 for i in x], summ.weighted_forecast / 1e3, width=0.4, label="Weighted forecast", color="#1F3864")
    ax.bar([i + 0.2 for i in x], summ.target / 1e3, width=0.4, label="Target", color="#A9B8D0")
    ax.set_xticks(list(x), summ.quarter)
    ax.set_ylabel("$ thousands")
    ax.set_title("Weighted forecast vs target by quarter")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "forecast_vs_target.png", dpi=120)
    plt.close(fig)

    at_risk = hs[hs.renewal_at_risk]
    print(f"Accounts: {len(accts)} ({(accts.status == 'Client').sum()} clients)")
    print(f"Open opportunities: {len(fc)} | weighted pipeline ${fc.weighted.sum():,.0f}")
    print(f"Renewals at risk: {', '.join(at_risk.account) or 'none'}")
    print(f"Deals at risk on qualification: {(qual.qualification == 'At Risk').sum()}")
    print(f"Stalled deals: {fc.stalled.sum()}")
    print(f"Outputs written to {out}/")
    return {"health": hs, "qual": qual, "forecast": fc, "summary": summ, "maps": maps}


if __name__ == "__main__":
    main()

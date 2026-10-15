from datetime import date

import pandas as pd
import pytest

import run
from src import action_plan, data_gen, forecast, health, meddpicc


@pytest.fixture(scope="module")
def book():
    return data_gen.generate()


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    return run.main(out_dir=str(out), data_dir=str(out / "data")), out


# ---------- data ----------

def test_generator_is_deterministic():
    a, b = data_gen.generate(), data_gen.generate()
    pd.testing.assert_frame_equal(a["opportunities"], b["opportunities"])


def test_book_shape(book):
    accts = book["accounts"]
    assert len(accts) == 16
    assert set(accts.segment) == set(data_gen.SEGMENTS)
    assert (accts.status == "Client").sum() == 11


# ---------- account health ----------

def test_planted_renewal_risk_is_red(book):
    hs = health.score_accounts(book["accounts"], book["contacts"])
    summit = hs[hs.account == "Summit Mutual"].iloc[0]
    assert summit.tier == "Red"
    assert summit.renewal_at_risk
    assert "No economic buyer meeting in 150 days" in summit.risk_flags
    assert "3 open escalations" in summit.risk_flags


def test_healthy_account_is_green(book):
    hs = health.score_accounts(book["accounts"], book["contacts"])
    assert hs[hs.account == "Northbridge Life"].iloc[0].tier == "Green"


@pytest.mark.parametrize("score, expected", [(85, "Green"), (70, "Green"), (69.9, "Yellow"),
                                             (50, "Yellow"), (49.9, "Red")])
def test_tier_thresholds(score, expected):
    assert health.tier(score) == expected


def test_scores_stay_in_range(book):
    hs = health.score_accounts(book["accounts"], book["contacts"])
    assert hs.health_score.between(0, 100).all()


def test_whitespace_excludes_owned_modules(book):
    ws = health.whitespace(book["accounts"], data_gen.MODULES)
    accts = book["accounts"].set_index("account_id")
    for row in ws.itertuples():
        owned = set(accts.loc[row.account_id, "modules"].split(";"))
        assert not owned & set(row.whitespace.split("; "))


# ---------- MEDDPICC ----------

def test_late_deal_without_economic_buyer_is_at_risk(book):
    q = meddpicc.qualify(book["opportunities"])
    opps = book["opportunities"]
    target = opps[(opps.account_id == "A003") & (opps.type == "Expansion")].opp_id.iloc[0]
    row = q[q.opp_id == target].iloc[0]
    assert row.qualification == "At Risk"
    assert "Economic Buyer" in row.stage_gaps and "Paper Process" in row.stage_gaps
    assert "economic buyer" in row.next_actions


def test_fully_qualified_deal(book):
    q = meddpicc.qualify(book["opportunities"])
    row = q[q.account_id == "A013"].iloc[0]
    assert row.meddpicc_score == 16 and row.qualification == "Qualified"


def test_closed_deals_are_excluded(book):
    q = meddpicc.qualify(book["opportunities"])
    assert not q.stage.isin(["Closed Won", "Closed Lost"]).any()


# ---------- forecast ----------

def test_at_risk_deal_is_not_commit(book):
    q = meddpicc.qualify(book["opportunities"])
    fc = forecast.build(book["opportunities"], q)
    at_risk_neg = fc[(fc.stage == "Negotiation") & (fc.qualification == "At Risk")]
    assert len(at_risk_neg) > 0
    assert (at_risk_neg.category != "Commit").all()
    assert (at_risk_neg.probability < forecast.STAGE_PROB["Negotiation"]).all()


def test_red_account_renewal_is_discounted_and_not_commit(book):
    hs = health.score_accounts(book["accounts"], book["contacts"])
    q = meddpicc.qualify(book["opportunities"])
    plain = forecast.build(book["opportunities"], q).set_index("opp_id")
    adj = forecast.build(book["opportunities"], q, hs).set_index("opp_id")
    red = adj[(adj.account_tier == "Red") & (adj.type == "Renewal")]
    assert len(red) > 0
    assert (red.category != "Commit").all()
    assert (red.probability < plain.loc[red.index, "probability"]).all()
    nb = adj[adj.type == "New Business"]
    assert (nb.probability == plain.loc[nb.index, "probability"]).all()


def test_stalled_expansion_is_flagged(book):
    q = meddpicc.qualify(book["opportunities"])
    fc = forecast.build(book["opportunities"], q)
    row = fc[(fc.account_id == "A001") & (fc.type == "Expansion")].iloc[0]
    assert row.stalled


def test_summary_ties_to_detail(book):
    q = meddpicc.qualify(book["opportunities"])
    fc = forecast.build(book["opportunities"], q)
    targets = {qt: 1_000_000 for qt in fc.close_quarter.unique()}
    s = forecast.summary(fc, targets)
    assert s.total_pipeline.sum() == fc.amount.sum()
    assert s.weighted_forecast.sum() == fc.weighted.sum()
    assert (s.commit <= s.best_case).all() and (s.best_case <= s.total_pipeline).all()


@pytest.mark.parametrize("d, q", [(date(2026, 1, 1), "2026-Q1"), (date(2026, 6, 30), "2026-Q2"),
                                  (date(2026, 10, 1), "2026-Q4")])
def test_quarter(d, q):
    assert forecast.quarter(d) == q


# ---------- mutual action plan ----------

def test_plan_ends_at_signature_and_is_ordered():
    close = date(2027, 3, 31)
    plan, note = action_plan.build_plan("O999", "Test Life", close)
    sig = plan[plan.milestone == "Signature"].iloc[0]
    assert sig.due == close
    assert (plan.start <= plan.due).all()
    assert list(plan.start) == sorted(plan.start)
    assert note.startswith("On track")


def test_compressed_plan_is_flagged():
    plan, note = action_plan.build_plan("O998", "Test Life", date(2026, 10, 20))
    assert note.startswith("Compressed")


# ---------- end to end ----------

def test_outputs_written(results):
    res, out = results
    xl = pd.read_excel(out / "account_strategy_workbook.xlsx", sheet_name=None)
    assert set(xl) == {"Forecast Summary", "Pipeline", "Account Health", "MEDDPICC",
                       "Whitespace", "Mutual Action Plans"}
    assert len(list((out / "account_plans").glob("*.md"))) == 16
    assert (out / "forecast_vs_target.png").stat().st_size > 0


def test_account_plan_content(results):
    _, out = results
    text = (out / "account_plans" / "A002_Summit_Mutual.md").read_text(encoding="utf-8")
    assert "Red" in text and "Relationship map" in text and "Business review agenda" in text
    assert "Retention plan" in text

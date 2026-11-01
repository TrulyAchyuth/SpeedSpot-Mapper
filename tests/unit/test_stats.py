"""The honesty rules: no score without enough, well-spread data."""
from backend.services import stats
from backend.services.regions import get_region
from backend.utils import geohash
from tests.conftest import CHENNAI_CENTRAL, VIT_CHENNAI


def test_neighbourhood_needs_five_tests(add_tests):
    neighbourhood = geohash.encode(*VIT_CHENNAI, 6)
    add_tests(*VIT_CHENNAI, 4)
    assert stats.summarize(stats.rows_for_cell(neighbourhood), "neighbourhood")["status"] == "insufficient"

    add_tests(*VIT_CHENNAI, 1)
    summary = stats.summarize(stats.rows_for_cell(neighbourhood), "neighbourhood")
    assert summary["status"] == "ok"
    assert summary["score"] == round(stats.nqi.calculate(40, 15, 40, 5))
    assert summary["medians"]["download_mbps"] == 40.0


def test_many_tests_in_one_place_do_not_score_a_whole_state(add_tests):
    # 200 tests, all in a single neighbourhood: the neighbourhood is scored, the state is not.
    add_tests(*VIT_CHENNAI, 200)
    summary = stats.summarize(stats.rows_for_region(get_region("IN-TN")), "state")
    assert summary["sample_count"] == 200
    assert summary["status"] == "insufficient"
    assert summary["score"] is None and summary["medians"] is None


def test_state_needs_spread_across_districts(add_tests):
    # 15+ neighbourhoods but only in one district → still insufficient for the state.
    add_tests(*CHENNAI_CENTRAL, 120, spread_cells=6)
    add_tests(13.0827, 80.20, 60, spread_cells=10)
    summary = stats.summarize(stats.rows_for_region(get_region("IN-TN")), "state")
    assert summary["neighbourhood_count"] >= 15
    assert summary["district_count"] < 3
    assert summary["status"] == "insufficient"


def test_score_is_median_not_mean(add_tests):
    add_tests(*VIT_CHENNAI, 4, download=40)
    add_tests(*VIT_CHENNAI, 1, download=0.5, upload=0.1, latency=900, jitter=300)  # one terrible outlier
    rows = stats.rows_for_region(get_region("IN-TN"))
    summary = stats.summarize(rows, "neighbourhood")
    assert summary["score"] == round(stats.nqi.calculate(40, 15, 40, 5))


def test_old_tests_are_not_counted(add_tests, app):
    add_tests(*VIT_CHENNAI, 5, age_days=app.config["FRESHNESS_WINDOW_DAYS"] + 5)
    assert stats.rows_for_region(get_region("IN-TN")) == []


def test_flagged_results_never_count(add_tests):
    add_tests(*VIT_CHENNAI, 5, download=40)
    add_tests(*VIT_CHENNAI, 5, download=900, flagged=True)   # VPN / implausible results are stored but not counted
    rows = stats.rows_for_region(get_region("IN-TN"))
    assert len(rows) == 5
    assert "includes_demo" not in stats.summarize(rows, "neighbourhood")


def test_provider_ranking_requires_enough_tests_each(add_tests):
    add_tests(*VIT_CHENNAI, 10, provider="airtel", download=80)
    add_tests(*VIT_CHENNAI, 10, provider="jio", download=20)
    add_tests(*VIT_CHENNAI, 3, provider="bsnl")
    add_tests(*VIT_CHENNAI, 2, provider=None)
    ranking = stats.providers_ranking(stats.rows_for_region(get_region("IN-TN")), "district")
    assert [p["slug"] for p in ranking["ranked"]] == ["airtel", "jio"]
    assert [p["slug"] for p in ranking["insufficient"]] == ["bsnl"]
    assert ranking["unidentified_count"] == 2


def test_insights_distribution_and_lists(add_tests):
    add_tests(*VIT_CHENNAI, 5, download=90)                                 # good neighbourhood
    add_tests(13.0827, 80.2707, 5, download=1, upload=0.5, latency=300)     # weak neighbourhood
    add_tests(13.0, 80.22, 2)                                                # too few
    result = stats.insights(stats.rows_for_region(get_region("IN-TN")), "state")
    assert result["neighbourhood_distribution"] == {"good": 1, "fair": 0, "weak": 1, "insufficient": 1}
    assert result["weakest"][0]["band"] == "weak"
    assert result["strongest"][0]["band"] == "good"

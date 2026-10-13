from __future__ import annotations

import os

from kinetickit.conformance import budgets


def test_budgets_hold_on_the_shared_fixtures():
    scale = float(os.environ.get("KK_BUDGET_SCALE", "1"))
    values = budgets.measure()
    assert budgets.check(values, scale) == [], budgets.report(values, scale)
    assert {"frame-eval", "svg-export-time", "svg-size", "svg-3d-size"} <= set(values)


def test_report_lists_every_budget_even_when_unmeasured():
    table = budgets.report({"frame-eval": 1.0})
    for b in budgets.BUDGETS:
        assert b.name in table
    assert "n/a" in table and "20%" in table


def test_check_flags_regressions_and_scales():
    over = {"svg-size": 10_000_000.0}
    assert budgets.check(over) == ["svg-size"]
    assert budgets.check(over, scale=1000.0) == []

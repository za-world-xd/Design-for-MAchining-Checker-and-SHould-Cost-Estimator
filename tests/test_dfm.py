import pytest

from core.config import load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.models import Hole, Part, Process


def rules(part):
    return {f.rule for f in check_dfm(part, load_rates(), load_thresholds())}


def test_milling_boundaries_and_deep_hole():
    part = Part(corner_radius_mm=1, pocket_depth_mm=40, pocket_width_mm=10,
                holes=[Hole(diameter_mm=2, depth_mm=10)])
    assert rules(part) == set()
    risky = Part(corner_radius_mm=0, pocket_depth_mm=41, pocket_width_mm=10,
                 holes=[Hole(diameter_mm=2, depth_mm=11)])
    assert rules(risky) == {"mill.corner", "mill.deep_pocket", "common.deep_hole.1"}


def test_turning_support_removes_slenderness_warning():
    assert "turn.slender" in rules(Part(process=Process.TURNING, width_mm=10))
    assert "turn.slender" not in rules(Part(process=Process.TURNING, width_mm=10, supported=True))


def test_sheet_clearances_and_zero_bends():
    part = Part(process=Process.SHEET, height_mm=2, bend_radius_mm=1,
                hole_edge_mm=1, hole_bend_mm=1, finish_ra_um=6.3)
    assert rules(part) == {"sheet.bend_radius", "sheet.hole_edge", "sheet.hole_bend"}
    assert "sheet.bend_radius" not in rules(
        Part(process=Process.SHEET, height_mm=2, bends=0, bend_radius_mm=0))


def test_casting_draft_and_wall_ratio():
    part = Part(process=Process.SAND, material="aluminium_a356", draft_deg=0,
                wall_mm=3, max_wall_mm=9, finish_ra_um=12.5)
    assert rules(part) == {"cast.draft", "cast.wall_variation"}


@pytest.mark.parametrize("changes,rule", [
    ({"wall_mm": .5}, "common.wall"), ({"tolerance_it": 6}, "common.tolerance"),
    ({"finish_ra_um": .8}, "common.finish"),
])
def test_common_findings(changes, rule):
    assert rule in rules(Part(**changes))


def test_thresholds_are_editable():
    cfg = load_thresholds()
    cfg.min_cutter_radius_mm = 4
    assert "mill.corner" in {f.rule for f in check_dfm(Part(), load_rates(), cfg)}

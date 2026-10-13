import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.GProp import GProp_GProps

from core.config import load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.estimator import estimate
from core.presets import PRESETS, build_preset


@pytest.mark.parametrize("key", PRESETS)
def test_every_default_preset_is_costable_with_provenance(key):
    part = build_preset(key)
    result = estimate(part, load_rates())
    assert 0 < part.net_volume_cm3 <= part.envelope_cm3 * (1 + 1e-9)
    assert part.area_cm2 > 0
    assert result.unit_cost > 0
    assert part.preset_source.key == key
    assert any("Parametric preset" in line for line in result.assumptions)
    check_dfm(part, load_rates(), load_thresholds())


def cad_properties(shape):
    volume, area = GProp_GProps(), GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, volume)
    BRepGProp.SurfaceProperties_s(shape, area)
    return volume.Mass() / 1000, area.Mass() / 100


def test_bush_matches_independent_cad_solid():
    part = build_preset("bush", {"outer_d": 30, "inner_d": 16, "length": 25})
    shape = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeCylinder(15, 25).Shape(), BRepPrimAPI_MakeCylinder(8, 25).Shape()
    ).Shape()
    volume, area = cad_properties(shape)
    assert part.net_volume_cm3 == pytest.approx(volume)
    assert part.area_cm2 == pytest.approx(area)
    assert part.holes[0].diameter_mm == 16
    assert part.wall_mm == 7


def test_stepped_shaft_matches_independent_cad_solid():
    part = build_preset("stepped_shaft")
    main = BRepPrimAPI_MakeCylinder(15, 60).Shape()
    journal = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 60), gp_Dir(0, 0, 1)), 10, 30).Shape()
    volume, area = cad_properties(BRepAlgoAPI_Fuse(main, journal).Shape())
    assert part.net_volume_cm3 == pytest.approx(volume)
    assert part.area_cm2 == pytest.approx(area)


def test_flange_matches_independent_cad_drilling():
    part = build_preset("flange")
    shape = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeCylinder(50, 10).Shape(), BRepPrimAPI_MakeCylinder(15, 10).Shape()
    ).Shape()
    for i in range(4):
        angle = i * math.pi / 2
        tool = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(35 * math.cos(angle), 35 * math.sin(angle), 0), gp_Dir(0, 0, 1)), 4, 10
        ).Shape()
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    volume, area = cad_properties(shape)
    assert part.net_volume_cm3 == pytest.approx(volume)
    assert part.area_cm2 == pytest.approx(area)
    assert sum(h.count for h in part.holes) == 5


def test_cast_housing_matches_independent_cad_cavity():
    part = build_preset("cast_housing")
    outside = BRepPrimAPI_MakeBox(120, 80, 40).Shape()
    cavity = BRepPrimAPI_MakeBox(gp_Pnt(4, 4, 4), 112, 72, 40).Shape()
    volume, area = cad_properties(BRepAlgoAPI_Cut(outside, cavity).Shape())
    assert part.net_volume_cm3 == pytest.approx(volume)
    assert part.area_cm2 == pytest.approx(area)


def test_pocket_geometry_drives_dfm_and_volume():
    part = build_preset("pocket_block", {"radius": 0, "depth": 15})
    assert part.net_volume_cm3 == 123
    assert part.area_cm2 == 227
    assert part.wall_mm == 10
    assert "mill.corner" in {f.rule for f in check_dfm(part, load_rates(), load_thresholds())}


def test_l_bracket_developed_length_uses_bend_deduction():
    part = build_preset("l_bracket")
    # Outside legs 60 + 40, R=2, T=2, K=0.4, one 90-degree bend.
    flat = 100 - (8 - math.pi / 2 * 2.8)
    assert part.length_mm == pytest.approx(flat)
    assert part.net_volume_cm3 == pytest.approx(flat * 30 * 2 / 1000)
    assert part.cut_perimeter_mm == pytest.approx(2 * (flat + 30))
    assert part.bends == 1
    assert build_preset("u_channel").bends == 2


@pytest.mark.parametrize(
    "key,parameters",
    [
        ("bush", {"inner_d": 35}),
        ("shaft", {"diameter": -1}),
        ("stepped_shaft", {"journal_d": 40}),
        ("flange", {"pcd": 98}),
        ("flange", {"bolt_count": 3.5}),
        ("flange", {"bolt_count": 24, "bolt_d": 20}),
        ("mounting_plate", {"edge": 1}),
        ("mounting_plate", {"edge": 30}),
        ("pocket_block", {"depth": 25}),
        ("pocket_block", {"radius": 20}),
        ("l_bracket", {"leg_a": 3}),
        ("u_channel", {"base": 4}),
        ("cast_housing", {"wall": 40}),
        ("shaft", {"diameter": float("nan")}),
        ("shaft", {"typo": 1}),
    ],
)
def test_invalid_or_colliding_geometry_is_rejected(key, parameters):
    with pytest.raises(ValueError):
        build_preset(key, parameters)


def test_doubling_dimensions_scales_mass_and_preserves_model_limits():
    small = build_preset("bush")
    large = build_preset("bush", {"outer_d": 60, "inner_d": 32, "length": 50})
    assert large.net_volume_cm3 == pytest.approx(small.net_volume_cm3 * 8)
    assert large.area_cm2 == pytest.approx(small.area_cm2 * 4)
    with pytest.raises(ValueError, match="settings"):
        build_preset("bush", volume_cm3=999)

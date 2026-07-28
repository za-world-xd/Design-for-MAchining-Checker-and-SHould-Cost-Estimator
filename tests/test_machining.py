from math import pi

import pytest
from pydantic import ValidationError

from core.config import load_rates
from core.cost_milling import estimate_milling
from core.cost_turning import estimate_turning
from core.models import Part, Process


def test_milling_hand_calculation():
    part = Part(volume_cm3=60, quantity=100)
    result = estimate_milling(part, load_rates())
    # Stock = 138 cm3, removal = 78 cm3, cycle = 78/20 * 1.2 + 1 = 5.68 min.
    assert result.costs["Material"] == pytest.approx(125.1936)
    assert result.cycle_min == pytest.approx(5.68)
    assert result.costs["Machining"] == pytest.approx(85.2)
    assert result.costs["Setup"] == pytest.approx(25.5)
    assert result.costs["Tooling"] == pytest.approx(5.112)
    assert result.costs["Inspection"] == 5
    assert result.unit_cost == pytest.approx(311.197084)


def test_turning_uses_cylinder():
    part = Part(process=Process.TURNING, width_mm=20, length_mm=100, volume_cm3=20)
    result = estimate_turning(part, load_rates())
    stock = pi * 10**2 * 100 / 1000 * 1.15
    expected_cycle = (stock - 20) / 20 * 1.2 + 1
    assert result.cycle_min == pytest.approx(expected_cycle)
    assert result.costs["Machining"] == pytest.approx(expected_cycle / 60 * 750)
    assert result.costs["Setup"] == pytest.approx(15.5)


def test_batch_dilutes_setup_without_changing_machine_cost():
    rates = load_rates()
    small = estimate_milling(Part(volume_cm3=60, quantity=10), rates)
    large = estimate_milling(Part(volume_cm3=60, quantity=100), rates)
    assert small.unit_cost > large.unit_cost
    assert small.costs["Setup"] == large.costs["Setup"] * 10
    assert small.costs["Machining"] == large.costs["Machining"]


def test_harder_material_takes_longer():
    rates = load_rates()
    assert estimate_milling(Part(material="stainless_304"), rates).cycle_min > (
        estimate_milling(Part(material="aluminium_6061"), rates).cycle_min
    )


@pytest.mark.parametrize("changes", [
    {"quantity": 0}, {"length_mm": -1}, {"volume_cm3": 121},
    {"finish_ra_um": float("nan")}, {"wall_mm": 4, "max_wall_mm": 3},
    {"name": " "}, {"secondary": ["anodize", "anodize"]},
])
def test_invalid_geometry(changes):
    with pytest.raises(ValidationError):
        Part(**changes)


def test_unknown_material_and_finish_rejected():
    rates = load_rates()
    for part in [Part(material="unknown"), Part(secondary=["unknown"]),
                 Part(material="mild_steel", secondary=["anodize"])]:
        with pytest.raises(ValueError):
            estimate_milling(part, rates)


def test_minimum_finish_lot_and_markup_base():
    result = estimate_milling(Part(secondary=["anodize"], quantity=10), load_rates())
    assert result.costs["Finishing"] == 60
    direct = sum(v for k, v in result.costs.items() if k not in ["Overhead", "Margin (markup)"])
    assert result.costs["Overhead"] == pytest.approx(direct * .15)
    assert result.costs["Margin (markup)"] == pytest.approx(direct * 1.15 * .10)

import pytest

from core.config import load_rates
from core.cost_casting import estimate_casting
from core.cost_sheetmetal import estimate_sheetmetal
from core.estimator import batch_sensitivity, estimate, with_changes
from core.models import Part, Process


def test_sheet_hand_calculation():
    part = Part(process=Process.SHEET, length_mm=100, width_mm=60, height_mm=2)
    result = estimate_sheetmetal(part, load_rates())
    # 12 cm3 blank, 0.0324 kg; 320 mm cut / 1800 + 2 s pierce = 0.21111 min.
    assert result.costs["Material"] == pytest.approx(13.824)
    assert result.costs["Cutting and bending"] == pytest.approx(28.2222222222)
    assert result.costs["Setup"] == 11
    assert result.costs["Tooling"] == 2
    assert result.unit_cost == pytest.approx(75.9584711111)


@pytest.mark.parametrize("process,material,yield_fraction,tooling", [
    (Process.SAND, "aluminium_a356", .6, 18000),
    (Process.DIE, "aluminium_adc12", .85, 250000),
])
def test_casting_material_yield_and_tooling(process, material, yield_fraction, tooling):
    part = Part(process=process, material=material, volume_cm3=60, quantity=100)
    rates = load_rates()
    result = estimate_casting(part, rates)
    mass = 60 * rates.materials[material].density_kg_cm3
    assert result.costs["Material"] == pytest.approx(
        mass / yield_fraction * rates.materials[material].price_kg)
    assert result.costs["Tooling"] == tooling / 100


def test_incompatible_material_process():
    with pytest.raises(ValueError, match="not supported"):
        estimate(Part(process=Process.DIE, material="aluminium_6061"), load_rates())


@pytest.mark.parametrize("process,material", [
    (Process.MILLING, "aluminium_6061"), (Process.TURNING, "mild_steel"),
    (Process.SHEET, "mild_steel"), (Process.SAND, "aluminium_a356"),
    (Process.DIE, "aluminium_adc12"),
])
def test_all_processes_positive_and_batch_monotonic(process, material):
    part = Part(process=process, material=material)
    rates = load_rates()
    result = estimate(part, rates)
    assert all(value >= 0 for value in result.costs.values())
    values = [row["Unit cost (INR)"] for row in batch_sensitivity(part, rates)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert result.batch_cost == result.unit_cost * part.quantity


def test_process_change_revalidates_volume():
    with pytest.raises(ValueError, match="volume"):
        with_changes(Part(volume_cm3=120), process=Process.TURNING, width_mm=10)

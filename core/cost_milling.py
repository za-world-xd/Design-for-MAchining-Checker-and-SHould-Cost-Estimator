from core.config import Rates
from core.cost_common import assemble, validate_selection
from core.models import Part, Process


def estimate_milling(part: Part, rates: Rates):
    """Material = stock cm3 * density * INR/kg * (1 + scrap allowance).

    Cycle min = removed cm3 / MRR * (1 + noncutting factor) + handling min.
    Setup/unit = (setup hours * machine INR/hour + programming INR) / batch.
    """
    if part.process != Process.MILLING:
        raise ValueError("Milling estimator requires CNC milling")
    return machining_cost(part, rates, rates.machining.milling)


def machining_cost(part, rates, machine):
    validate_selection(part, rates)
    material, cfg = rates.materials[part.material], rates.machining
    stock = part.envelope_cm3 * cfg.stock_factor
    removed = stock - part.net_volume_cm3
    cycle = removed / material.mrr_cm3_min * (1 + cfg.noncutting_factor) + cfg.handling_min
    machining = cycle / 60 * machine.hour_rate
    direct = {
        "Material": stock * material.density_kg_cm3 * material.price_kg * (1 + cfg.scrap_allowance),
        "Machining": machining,
        "Setup": (machine.setup_hours * machine.hour_rate + machine.programming) / part.quantity,
        "Tooling": machining * cfg.tooling_fraction,
    }
    return assemble(
        part,
        rates,
        direct,
        part.net_volume_cm3 * material.density_kg_cm3,
        cycle,
        [
            f"Stock volume {stock:.3f} cm3; removed volume {removed:.3f} cm3.",
            "Stock allowance is a volume multiplier, not an allowance on each axis.",
            "MRR is a single effective removal rate; holes and toolpaths are not timed.",
            "Setup includes programming; tooling is a fraction of machine cost.",
        ],
    )

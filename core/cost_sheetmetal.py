from core.config import Rates
from core.cost_common import assemble, validate_selection
from core.models import Part, Process


def estimate_sheetmetal(part: Part, rates: Rates):
    """Stock mass = blank length * width * thickness * density / utilisation.

    Cut min = perimeter / thickness-adjusted laser speed + pierces * seconds / 60.
    Forming = bends * bend charge; setup and tooling are amortised by batch.
    """
    if part.process != Process.SHEET:
        raise ValueError("Sheet estimator requires Sheet metal")
    validate_selection(part, rates)
    material, cfg = rates.materials[part.material], rates.sheet
    blank_mass = part.envelope_cm3 * material.density_kg_cm3
    perimeter = part.cut_perimeter_mm or 2 * (part.length_mm + part.width_mm)
    speed = cfg.laser_speed_mm_min * min(1, cfg.speed_reference_thickness_mm / part.height_mm)
    cycle = perimeter / speed + part.pierces * cfg.pierce_seconds / 60
    direct = {
        "Material": blank_mass / cfg.utilisation * material.price_kg,
        "Cutting and bending": cycle / 60 * cfg.laser_hour_rate + part.bends * cfg.bend_cost,
        "Setup": (cfg.setup_hours * cfg.laser_hour_rate + cfg.programming) / part.quantity,
        "Tooling": cfg.tooling_per_batch / part.quantity,
    }
    return assemble(part, rates, direct, part.net_volume_cm3 * material.density_kg_cm3,
                    cycle, [
                        "Length and width describe the developed flat blank; height is thickness.",
                        f"Nesting utilisation is {cfg.utilisation:.0%}; no scrap resale credit.",
                        "Laser speed scales inversely with thickness above the reference gauge.",
                        "Cut perimeter defaults to the outer rectangle; enter internal cuts explicitly.",
                        "Cycle time includes laser cutting and pierces only; bends use a flat rate.",
                    ])

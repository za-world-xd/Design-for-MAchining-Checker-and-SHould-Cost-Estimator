from core.config import Rates
from core.cost_common import assemble, validate_selection
from core.models import Part, Process


def estimate_casting(part: Part, rates: Rates):
    """Charge mass = net casting mass / metal yield.

    Material = charge mass * INR/kg; conversion and fettling use net mass.
    Tooling and setup are divided by batch quantity. No post-machining is included.
    """
    if part.process not in (Process.SAND, Process.DIE):
        raise ValueError("Casting estimator requires sand or die casting")
    validate_selection(part, rates)
    material = rates.materials[part.material]
    cfg = rates.casting.sand if part.process == Process.SAND else rates.casting.die
    mass = part.net_volume_cm3 * material.density_kg_cm3
    direct = {
        "Material": mass / cfg.yield_fraction * material.price_kg,
        "Casting conversion": mass * cfg.conversion_per_kg,
        "Fettling": mass * cfg.fettling_per_kg,
        "Setup": cfg.setup_per_batch / part.quantity,
        "Tooling": cfg.tooling_per_batch / part.quantity,
    }
    return assemble(
        part,
        rates,
        direct,
        mass,
        cfg.cycle_min,
        [
            f"Metal yield {cfg.yield_fraction:.0%}; gating and riser returns have no credit.",
            "The entire pattern or die cost is amortised over this batch only.",
            "Casting conversion is charged per kg of net casting mass.",
            "Cycle time is informational; conversion charges already include processing.",
            "Post-machining, cores, heat treatment and additional mould cavities are not included.",
        ],
    )

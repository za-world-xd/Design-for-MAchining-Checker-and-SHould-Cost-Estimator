from core.config import Rates
from core.models import Estimate, Part


def validate_selection(part: Part, rates: Rates):
    if part.material not in rates.materials:
        raise ValueError(f"Unknown material: {part.material}")
    if part.process not in rates.materials[part.material].processes:
        raise ValueError("Material is not supported for the selected process")
    for key in part.secondary:
        if key not in rates.finishing:
            raise ValueError(f"Unknown finishing operation: {key}")
        if part.material not in rates.finishing[key].materials:
            raise ValueError(f"{rates.finishing[key].label} is not supported for this material")


def finish_cost(part: Part, rates: Rates, mass_kg: float) -> float:
    """Sum max(variable charge per unit, minimum lot / quantity) for each finish."""
    total = 0.0
    for key in part.secondary:
        finish = rates.finishing[key]
        basis = mass_kg if finish.basis == "kg" else part.area_cm2 / 100
        total += max(basis * finish.rate, finish.minimum_lot / part.quantity)
    return total


def assemble(part, rates, direct, mass_kg, cycle_min, assumptions) -> Estimate:
    """Overhead = direct * rate; profit markup = (direct + overhead) * rate."""
    direct["Finishing"] = finish_cost(part, rates, mass_kg)
    direct["Inspection"] = rates.inspection.minutes_per_part / 60 * rates.inspection.hour_rate
    direct["Overhead"] = sum(direct.values()) * part.overhead_pct / 100
    direct["Margin (markup)"] = sum(direct.values()) * part.margin_pct / 100
    return Estimate(
        part=part, costs=direct, mass_kg=mass_kg, cycle_min=cycle_min,
        assumptions=assumptions + [
            "Finishing uses envelope surface area unless measured area is supplied.",
            "Margin is a markup on direct cost plus overhead, not a gross margin.",
            "DFM warnings do not automatically change costs; model extra operations explicitly.",
            "Estimates exclude GST, freight, scrap resale credits and commercial discounts.",
        ],
        rate_source=rates.metadata.source,
        rate_date=rates.metadata.date or "Undated placeholder",
    )

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
    if part.preset_source:
        assumptions += [f"Parametric preset: {part.preset_source.label}, nominal geometry."]
        assumptions += part.preset_source.assumptions
        assumptions += [
            "Threads, purchased-part discounts and process optimisation are not inferred."
        ]
    if part.geometry_import:
        assumptions += [
            f"STEP source: {part.geometry_import.file_name}; review any edited dimensions.",
            "STEP supplies bounds, solid volume and area, not holes, walls or tolerances.",
        ]
        if part.process.value == "CNC turning":
            assumptions.append(
                f"STEP spindle axis: {part.turning_axis}; stock diameter was seeded from the "
                "transverse bounding-box diagonal. Review the actual outside diameter."
            )
    price_reference = rates.materials[part.material].price_reference
    if price_reference:
        assumptions += [
            f"Material budget rate INR {rates.materials[part.material].price_kg:g}/kg; "
            f"public supplier listing checked {price_reference.checked_on}, not a firm quote.",
            price_reference.tax_basis,
            "Supplier minimum order is a sourcing condition, not a modelled batch purchase charge.",
        ]
    return Estimate(
        part=part,
        costs=direct,
        mass_kg=mass_kg,
        cycle_min=cycle_min,
        assumptions=assumptions
        + [
            "Finishing uses envelope surface area unless measured area is supplied.",
            "Margin is a markup on direct cost plus overhead, not a gross margin.",
            "DFM warnings do not automatically change costs; model extra operations explicitly.",
            "Estimates exclude GST, freight, scrap resale credits and commercial discounts.",
        ],
        rate_source=rates.metadata.source,
        rate_date=str(rates.metadata.date) if rates.metadata.date else "Undated placeholder",
    )

from core.config import Rates
from core.cost_casting import estimate_casting
from core.cost_milling import estimate_milling
from core.cost_sheetmetal import estimate_sheetmetal
from core.cost_turning import estimate_turning
from core.models import Estimate, Part, Process

ESTIMATORS = {
    Process.MILLING: estimate_milling,
    Process.TURNING: estimate_turning,
    Process.SHEET: estimate_sheetmetal,
    Process.SAND: estimate_casting,
    Process.DIE: estimate_casting,
}


def estimate(part: Part, rates: Rates) -> Estimate:
    return ESTIMATORS[part.process](part, rates)


def with_changes(part: Part, **changes) -> Part:
    """Revalidate edits; Pydantic model_copy(update=...) deliberately skips validation."""
    return Part.model_validate(part.model_dump() | changes)


def batch_sensitivity(part: Part, rates: Rates, quantities=None) -> list[dict]:
    quantities = quantities if quantities is not None else [1, 10, 25, 50, 100, 250, 500, 1000]
    return [
        {"Quantity": qty, "Unit cost (INR)": estimate(with_changes(part, quantity=qty), rates).unit_cost}
        for qty in sorted(set([*quantities, part.quantity]))
    ]

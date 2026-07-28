from core.config import Rates
from core.cost_milling import machining_cost
from core.models import Part, Process


def estimate_turning(part: Part, rates: Rates):
    """Use cylindrical stock: pi * (diameter / 2)^2 * length / 1000 cm3.

    Removal, handling, material and setup follow the milling formula, using lathe rates.
    """
    if part.process != Process.TURNING:
        raise ValueError("Turning estimator requires CNC turning")
    return machining_cost(part, rates, rates.machining.turning)

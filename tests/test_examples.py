import csv

import pytest

from core.config import ROOT, load_rates
from core.estimator import estimate
from core.models import Part


def test_three_examples_match_independent_hand_calculations():
    with (ROOT / "examples" / "hand_calculations.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    rates = load_rates()
    for key in {row["part"] for row in rows}:
        part = Part.model_validate_json((ROOT / "examples" / f"{key}.json").read_text())
        result = estimate(part, rates)
        for row in [item for item in rows if item["part"] == key]:
            actual = (
                result.unit_cost if row["component"] == "Total" else result.costs[row["component"]]
            )
            assert actual == pytest.approx(float(row["expected_inr_per_unit"]), abs=1e-7), row

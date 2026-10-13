from datetime import date

import pytest
from pydantic import ValidationError

from core.config import Rates, load_rates
from core.dfm_rules import Thresholds, load_thresholds
from core.estimator import estimate
from core.models import Part


@pytest.mark.parametrize("loader", [load_rates, load_thresholds])
def test_malformed_yaml_has_readable_error(loader, tmp_path):
    card = tmp_path / "broken.yaml"
    card.write_text("bad: [oops")
    with pytest.raises(ValueError, match="invalid YAML"):
        loader(card)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("sheet", "utilisation", 0),
        ("sheet", "utilisation", 1.1),
        ("machining", "stock_factor", 0.9),
        ("inspection", "minutes_per_part", -1),
    ],
)
def test_invalid_rates_rejected(section, key, value):
    data = load_rates().model_dump(by_alias=True)
    data[section][key] = value
    with pytest.raises(ValidationError):
        Rates.model_validate(data)


def test_quote_provenance_and_date_serialization():
    data = load_rates().model_dump(by_alias=True)
    data["metadata"]["status"] = "quoted"
    with pytest.raises(ValueError, match="source and quote date"):
        Rates.model_validate(data)
    data["metadata"].update(source="Synthetic quote fixture", date="2026-10-01")
    rates = Rates.model_validate(data)
    assert rates.metadata.date == date(2026, 10, 1)
    assert estimate(Part(), rates).rate_date == "2026-10-01"


def test_missing_process_threshold_rejected():
    data = load_thresholds().model_dump(mode="json")
    data["minimum_ra"].pop("CNC milling")
    with pytest.raises(ValueError, match="Every process"):
        Thresholds.model_validate(data)


def test_indian_material_budget_rates_have_dated_primary_sources():
    rates = load_rates()
    assert rates.metadata.status == "illustrative"
    for material in rates.materials.values():
        assert material.price_reference is not None
        assert material.price_reference.checked_on == date(2026, 11, 5)
        assert material.price_reference.url.startswith("https://")
        assert material.price_reference.listed_price_kg > 0

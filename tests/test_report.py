from io import BytesIO

from pypdf import PdfReader

from core.config import load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.estimator import estimate
from core.models import Part
from core.report import build_report


def test_report_contains_snapshot_costs_and_escaped_part_name():
    rates, thresholds = load_rates(), load_thresholds()
    part = Part(name="Bracket <A&B>", corner_radius_mm=0, volume_cm3=60)
    result = estimate(part, rates)
    data = build_report(result, check_dfm(part, rates, thresholds), rates, thresholds)
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert data.startswith(b"%PDF")
    assert "Bracket <A&B>" in text
    assert "311.20" in text
    assert "mill.corner" in text
    assert "stock_factor" in text
    assert "Input snapshot" in text
    assert "not a supplier quote" in text

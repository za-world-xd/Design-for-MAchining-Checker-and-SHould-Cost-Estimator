from io import BytesIO

from pypdf import PdfReader

from core.config import ROOT, load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.estimator import estimate
from core.models import Part
from core.report import build_report
from core.step_reader import read_step


def test_report_contains_snapshot_costs_and_escaped_part_name():
    rates, thresholds = load_rates(), load_thresholds()
    part = Part(name="Bracket <A&B>", corner_radius_mm=0, volume_cm3=60)
    result = estimate(part, rates)
    data = build_report(result, check_dfm(part, rates, thresholds), rates, thresholds)
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert data.startswith(b"%PDF")
    assert "Bracket <A&B>" in text
    assert "350.79" in text
    assert "mill.corner" in text
    assert "stock_factor" in text
    assert "Input snapshot" in text
    assert "not a supplier quote" in text


def test_report_includes_step_source_and_material_price_reference():
    source = ROOT / "examples/step_block.step"
    geometry = read_step(source.read_bytes(), source.name)
    rates, thresholds = load_rates(), load_thresholds()
    part = Part(geometry_import=geometry)
    result = estimate(part, rates)
    report = build_report(result, [], rates, thresholds)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(report)).pages)
    assert "step_block.step" in text
    assert geometry.sha256 in text.replace("\n", "").replace(" ", "")
    assert "Sachin Steel Centre" in text
    assert "2026-11-05" in text

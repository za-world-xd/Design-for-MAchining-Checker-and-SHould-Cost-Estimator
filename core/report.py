from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core.config import Rates
from core.dfm_rules import Thresholds
from core.models import Estimate, Finding


def build_report(result: Estimate, findings: list[Finding], rates: Rates,
                 thresholds: Thresholds) -> bytes:
    """Render a reproducible estimate summary. INR text avoids missing rupee glyphs."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm),
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"Should-cost: {result.part.name}", author="DFM worksheet")
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    story = []

    def paragraph(text, style="BodyText"):
        return Paragraph(escape(str(text)), styles[style])

    def table(rows):
        cells = [[paragraph(cell) for cell in row] for row in rows]
        item = Table(cells, colWidths=(105 * mm, 69 * mm), repeatRows=1, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eee9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#52635a")),
            ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#d4d9d5")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return item

    part = result.part
    story += [paragraph("DFM and should-cost worksheet", "Title"),
              paragraph(part.name, "Heading1"),
              paragraph(f"{part.process.value} | {rates.materials[part.material].label} | "
                        f"Batch {part.quantity:,}"),
              paragraph("Generated " + datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(
                  timespec="minutes")),
              Spacer(1, 4 * mm),
              paragraph("Engineering estimate, not a supplier quote. "
                        f"Rate status: {rates.metadata.status}. DFM thresholds are heuristics."),
              paragraph(f"Unit cost: INR {result.unit_cost:,.2f}", "Heading1"),
              paragraph(f"Batch cost: INR {result.batch_cost:,.2f}; "
                        f"net mass: {result.mass_kg:.4f} kg; "
                        f"modelled cycle: {result.cycle_min:.3f} min."),
              Spacer(1, 3 * mm),
              table([["Cost component", "INR / unit"],
                     *[[key, f"{value:,.4f}"] for key, value in result.costs.items()],
                     ["Total", f"{result.unit_cost:,.4f}"]]),
              paragraph("DFM screening", "Heading2")]
    if not findings:
        story.append(paragraph("No configured rule triggered. This is not manufacturing approval."))
    for finding in findings:
        story.append(KeepTogether([
            paragraph(f"{finding.severity.upper()}: {finding.rule}", "Heading3"),
            paragraph(finding.message), paragraph("Suggested action: " + finding.suggestion),
        ]))
    story.append(paragraph("Assumptions and exclusions", "Heading2"))
    for assumption in result.assumptions:
        story.append(paragraph(assumption))
    story += [paragraph("Rate basis", "Heading2"),
              paragraph(f"Source: {result.rate_source}; date: {result.rate_date}."),
              paragraph("All rate values below use the units in config/rates.yaml.")]
    selected_rates = {
        "material": rates.materials[part.material].model_dump(mode="json"),
        "machining": rates.machining.model_dump(mode="json"),
        "sheet": rates.sheet.model_dump(mode="json"),
        "casting": rates.casting.model_dump(mode="json", by_alias=True),
        "inspection": rates.inspection.model_dump(mode="json"),
        "finishing": {k: rates.finishing[k].model_dump(mode="json") for k in part.secondary},
    }

    def flattened(data, prefix=""):
        for key, value in data.items():
            name = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                yield from flattened(value, name)
            else:
                yield [name, ", ".join(map(str, value)) if isinstance(value, list) else str(value)]

    story.append(table([["Rate", "Value"], *flattened(selected_rates)]))
    story.append(paragraph("Input snapshot", "Heading2"))
    snapshot = part.model_dump(mode="json")
    snapshot["resolved_volume_cm3"] = part.net_volume_cm3
    snapshot["resolved_area_cm2"] = part.area_cm2
    story.append(table([["Input", "Value"], *flattened(snapshot)]))
    story.append(paragraph("Screening threshold snapshot", "Heading2"))
    story.append(table([["Threshold", "Value"], *flattened(thresholds.model_dump(mode="json"))]))

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 10 * mm, "DFM worksheet | INR | illustrative until calibrated")
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {document.page}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

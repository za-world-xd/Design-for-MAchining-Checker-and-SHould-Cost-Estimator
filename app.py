import json

import pandas as pd
import plotly.express as px
import streamlit as st
from pydantic import ValidationError

from core.config import ROOT, load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.estimator import batch_sensitivity, estimate, with_changes
from core.models import Hole, Part, Process
from core.report import build_report

st.set_page_config(page_title="DFM cost worksheet", layout="wide")
st.html("""
<style>
  .stMainBlockContainer { max-width: 1200px; }
  button, a[href], select, summary, [role="combobox"], label { cursor: pointer; }
  button:disabled { cursor: not-allowed; }
  :focus-visible { outline: 3px solid #24603e !important; outline-offset: 3px; }
  [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
  @media (max-width: 640px) {
    .stMainBlockContainer { padding: 2rem 1rem; }
    h1 { font-size: 1.8rem; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
</style>
""")
st.title("DFM cost worksheet")
st.write("Screen manufacturing risks and inspect a should-cost estimate in INR.")

try:
    rates, thresholds = load_rates(), load_thresholds()
except (OSError, ValueError) as exc:
    st.error(f"Could not load the rate card or DFM thresholds: {exc}")
    st.stop()

st.warning(f"Rate card: {rates.metadata.status}. {rates.metadata.source}")

EXAMPLES = {
    "Milled bracket": "milled_bracket.json",
    "Turned spacer": "turned_spacer.json",
    "Sheet bracket": "sheet_bracket.json",
}
starting_point = st.selectbox("Starting example", list(EXAMPLES),
                              help="Illustrative dimensions, not measured production parts.")
sample = Part.model_validate_json((ROOT / "examples" / EXAMPLES[starting_point]).read_text())
process = st.selectbox("Manufacturing process", list(Process),
                       index=list(Process).index(sample.process),
                       format_func=lambda p: p.value, key=f"process_{starting_point}")
materials = [key for key, material in rates.materials.items() if process in material.processes]
material = st.selectbox("Material grade", materials,
                        index=materials.index(sample.material) if sample.material in materials else 0,
                        format_func=lambda key: rates.materials[key].label,
                        key=f"material_{starting_point}_{process.value}")
context = (starting_point, process.value, material)
if st.session_state.get("context") != context:
    st.session_state.pop("result", None)
    st.session_state["context"] = context

st.caption("Changing example, process or material clears the previous result. "
           "Form edits take effect when you calculate again.")
form_key = f"part_{starting_point}_{process.value}_{material}"
with st.form(form_key):
    st.subheader("Part and envelope")
    name = st.text_input("Part name", value=sample.name, max_chars=100)
    qty = st.number_input("Batch quantity", min_value=1, max_value=10000000,
                          value=sample.quantity, step=1)
    if process == Process.SHEET:
        st.caption("Enter the developed flat blank. Height is the sheet thickness.")
    elif process == Process.TURNING:
        st.caption("Width is the outside diameter of the cylindrical envelope.")
    cols = st.columns(3)
    length = cols[0].number_input("Length (mm)", min_value=0.01, max_value=10000.0,
                                  value=sample.length_mm)
    width = cols[1].number_input("Diameter (mm)" if process == Process.TURNING else "Width (mm)",
                                 min_value=0.01, max_value=10000.0, value=sample.width_mm)
    height = cols[2].number_input("Thickness (mm)" if process == Process.SHEET else "Height (mm)",
                                  min_value=0.01, max_value=10000.0,
                                  value=2.0 if process == Process.SHEET else sample.height_mm,
                                  disabled=process == Process.TURNING)
    cols = st.columns(2)
    volume = cols[0].number_input("Finished volume (cm³; 0 uses envelope)", min_value=0.0,
                                  value=(sample.volume_cm3 or 0.0) if process == sample.process else 0.0,
                                  help="Measured solid volume overrides the bounding envelope volume.")
    area = cols[1].number_input("Surface area (cm²; 0 uses envelope)", min_value=0.0, value=0.0,
                                help="Use measured area for finishing charges when available.")
    st.subheader("Features and DFM inputs")
    wall, max_wall = 3.0, 3.0
    corner, pocket_depth, pocket_width = 3.0, 0.0, 10.0
    supported = False
    bends, bend_radius, edge, bend_gap, perimeter, pierces = 0, 3.0, 0.0, 0.0, 0.0, 1
    draft = 2.0
    holes = []
    if process != Process.SHEET:
        wall = st.number_input("Minimum wall (mm)", min_value=0.01, value=3.0)
        max_wall = wall
    if process in (Process.MILLING, Process.TURNING):
        cols = st.columns(3)
        hole_count = cols[0].number_input("Identical hole count", min_value=0,
                                          max_value=10000, value=0, step=1)
        hole_diameter = cols[1].number_input("Hole diameter (mm)", min_value=0.01, value=6.0)
        hole_depth = cols[2].number_input("Hole depth (mm)", min_value=0.01, value=20.0)
        if hole_count:
            holes = [Hole(count=hole_count, diameter_mm=hole_diameter, depth_mm=hole_depth)]
        st.caption("One uniform hole group. Hole timing is represented by the effective MRR.")
    if process == Process.MILLING:
        cols = st.columns(3)
        corner = cols[0].number_input("Internal corner radius (mm)", min_value=0.0, value=3.0)
        pocket_depth = cols[1].number_input("Deepest pocket (mm; 0 means none)",
                                            min_value=0.0, value=0.0)
        pocket_width = cols[2].number_input("Pocket width (mm)", min_value=0.01, value=10.0)
    elif process == Process.TURNING:
        supported = st.checkbox("Tailstock or steady rest planned", value=sample.supported)
    elif process == Process.SHEET:
        cols = st.columns(2)
        bends = cols[0].number_input("Bend count", min_value=0, max_value=1000, value=2, step=1)
        bend_radius = cols[1].number_input("Inside bend radius (mm)", min_value=0.0, value=3.0)
        edge = cols[0].number_input("Hole-edge to blank-edge clearance (mm; 0 unknown)",
                                     min_value=0.0, value=0.0)
        bend_gap = cols[1].number_input("Hole-edge to bend tangent (mm; 0 unknown)",
                                         min_value=0.0, value=0.0)
        perimeter = cols[0].number_input("Total cut perimeter (mm; 0 uses outer rectangle)",
                                          min_value=0.0, value=0.0)
        pierces = cols[1].number_input("Laser pierces", min_value=0, max_value=100000,
                                        value=1, step=1)
    else:
        max_wall = st.number_input("Maximum wall (mm)", min_value=0.01, value=6.0)
        draft = st.number_input("Draft angle (degrees)", min_value=0.0, max_value=30.0, value=2.0)
    cols = st.columns(2)
    tolerance = cols[0].number_input("Tightest tolerance (IT grade)", min_value=1,
                                      max_value=16, value=9, step=1)
    default_ra = thresholds.minimum_ra[process]
    finish = cols[1].number_input("Required surface finish Ra (µm)", min_value=0.01,
                                   value=default_ra)
    available_finishes = [key for key, item in rates.finishing.items() if material in item.materials]
    secondary = st.multiselect("Secondary operations", available_finishes,
                               format_func=lambda key: rates.finishing[key].label)
    st.subheader("Commercial assumptions")
    cols = st.columns(2)
    overhead = cols[0].number_input("Overhead (%)", min_value=0.0, max_value=100.0, value=15.0)
    margin = cols[1].number_input("Margin as markup (%)", min_value=0.0, max_value=100.0, value=10.0)
    submitted = st.form_submit_button("Calculate cost and check DFM", type="primary")

if submitted:
    st.session_state.pop("result", None)
    try:
        part = Part(
            name=name, process=process, material=material, quantity=qty,
            length_mm=length, width_mm=width, height_mm=height,
            volume_cm3=volume or None, surface_area_cm2=area or None, holes=holes,
            wall_mm=wall, max_wall_mm=max_wall, corner_radius_mm=corner,
            pocket_depth_mm=pocket_depth, pocket_width_mm=pocket_width, supported=supported,
            bends=bends, bend_radius_mm=bend_radius, hole_edge_mm=edge or None,
            hole_bend_mm=bend_gap or None, cut_perimeter_mm=perimeter or None, pierces=pierces,
            draft_deg=draft, tolerance_it=tolerance, finish_ra_um=finish, secondary=secondary,
            overhead_pct=overhead, margin_pct=margin,
        )
        with st.spinner("Calculating cost and screening geometry..."):
            result = estimate(part, rates)
            findings = check_dfm(part, rates, thresholds)
            pdf = build_report(result, findings, rates, thresholds)
        st.session_state["result"] = (result, findings, pdf, rates, thresholds)
    except (ValidationError, ValueError) as exc:
        st.error(f"Check the part inputs: {exc}")

if "result" not in st.session_state:
    st.info("Enter a part above, then calculate to see costs, DFM findings and batch sensitivity.")
    st.stop()

result, findings, pdf, saved_rates, saved_thresholds = st.session_state["result"]
part = result.part
st.divider()
st.header("Estimate")
st.caption(f"Last calculated: {part.name} | {part.process.value} | batch {part.quantity:,}. "
           "Results and exports use this submitted snapshot.")
cols = st.columns([2, 1, 1])
cols[0].metric("Should-cost / unit", f"₹{result.unit_cost:,.2f}")
cols[1].metric("Batch total", f"₹{result.batch_cost:,.2f}")
cols[2].metric("Net part mass", f"{result.mass_kg:.4f} kg")
st.caption(f"Modelled cycle: {result.cycle_min:.3f} min. "
           "Sheet cycle covers cutting only; casting cycle is informational.")
breakdown = pd.DataFrame({"Component": result.costs.keys(), "INR / unit": result.costs.values()})
cols = st.columns(2)
cols[0].dataframe(breakdown, hide_index=True, width="stretch",
                  column_config={"INR / unit": st.column_config.NumberColumn(format="%.2f")})
fig = px.bar(breakdown, x="INR / unit", y="Component", orientation="h",
              color_discrete_sequence=["#24603e"])
fig.update_layout(showlegend=False, margin=dict(l=0, r=10, t=10, b=0),
                   yaxis=dict(autorange="reversed"), height=350)
cols[1].plotly_chart(fig, width="stretch", config={"displayModeBar": False})

st.subheader("DFM findings")
st.caption("Heuristic screening only. Review with the manufacturing shop; "
           "these findings do not change the estimate automatically.")
if not findings:
    st.success("No configured rule triggered. This is not manufacturing approval.")
for finding in findings:
    show = {"critical": st.error, "warning": st.warning, "info": st.info}[finding.severity]
    show(f"{finding.severity.capitalize()}: {finding.message} Suggested fix: {finding.suggestion}")

st.subheader("Batch-size sensitivity")
sensitivity = pd.DataFrame(batch_sensitivity(part, saved_rates))
fig = px.line(sensitivity, x="Quantity", y="Unit cost (INR)", markers=True, log_x=True,
               color_discrete_sequence=["#24603e"])
fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), height=300)
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
with st.expander("Inspect sensitivity values"):
    st.dataframe(sensitivity, hide_index=True, width="stretch")

with st.expander("Assumptions and rate basis"):
    for assumption in result.assumptions:
        st.write(assumption)
    st.write(f"Rate source: {result.rate_source}. Date: {result.rate_date}.")
    st.json(saved_rates.model_dump(mode="json", by_alias=True), expanded=False)
    st.caption("STEP import and automatic feature recognition are not implemented. "
               "Use measured geometry in the form. No files are uploaded to a remote service.")

st.subheader("Compare an alternative")
st.caption("Comparison holds the submitted dimensions, volume, finish and quantity fixed. "
           "A process change may need a redesigned part or additional operations.")
cols = st.columns(2)
alternative_process = cols[0].selectbox("Alternative process", list(Process),
                                        index=list(Process).index(part.process),
                                        format_func=lambda p: p.value)
alternative_materials = [key for key, item in saved_rates.materials.items()
                         if alternative_process in item.processes]
alternative_material = cols[1].selectbox("Alternative material", alternative_materials,
                                         format_func=lambda key: saved_rates.materials[key].label)
try:
    alternative_part = with_changes(part, process=alternative_process, material=alternative_material)
    alternative = estimate(alternative_part, saved_rates)
    comparison = pd.DataFrame({
        "Component": list(result.costs) + [key for key in alternative.costs if key not in result.costs],
    })
    comparison["Submitted (INR)"] = comparison["Component"].map(result.costs).fillna(0)
    comparison["Alternative (INR)"] = comparison["Component"].map(alternative.costs).fillna(0)
    st.dataframe(comparison, hide_index=True, width="stretch")
    delta = alternative.unit_cost - result.unit_cost
    st.write(f"Submitted ₹{result.unit_cost:,.2f}/unit; alternative ₹{alternative.unit_cost:,.2f}/unit. "
             f"Difference: ₹{delta:+,.2f} ({delta / result.unit_cost:+.1%}).")
    alternative_findings = check_dfm(alternative_part, saved_rates, saved_thresholds)
    st.caption(f"Alternative screening: {len(alternative_findings)} finding(s). "
               "Exports below contain the submitted estimate only.")
    for finding in alternative_findings:
        st.write(f"{finding.severity.capitalize()}: {finding.message} {finding.suggestion}")
except (ValidationError, ValueError) as exc:
    st.warning(f"This alternative cannot use the submitted geometry or finish: {exc}")

st.subheader("Export submitted estimate")
cols = st.columns(3)
cols[0].download_button("Download PDF report", pdf, file_name="dfm-estimate.pdf",
                         mime="application/pdf")
cols[1].download_button("Download cost CSV", breakdown.to_csv(index=False).encode("utf-8"),
                         file_name="cost-breakdown.csv", mime="text/csv")
audit = {
    "estimate": result.model_dump(mode="json"), "unit_cost": result.unit_cost,
    "findings": [finding.model_dump() for finding in findings],
    "rates": saved_rates.model_dump(mode="json", by_alias=True),
    "thresholds": saved_thresholds.model_dump(mode="json"),
}
cols[2].download_button("Download audit JSON", json.dumps(audit, indent=2).encode("utf-8"),
                         file_name="estimate-audit.json", mime="application/json")

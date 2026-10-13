import hashlib

import streamlit as st
from pydantic import ValidationError

from core.config import ROOT, load_rates
from core.dfm_rules import load_thresholds
from core.models import Hole, Part, Process
from core.step_reader import StepImportError, geometry_defaults, read_step, step_available
from ui.preset_inputs import render_preset_inputs
from ui.results import calculate_estimate, render_estimate

st.set_page_config(page_title="DFM cost worksheet", layout="wide")
st.html("""
<style>
  .stMainBlockContainer { max-width: 1200px; }
  button, a[href], select, summary, [role="combobox"], label { cursor: pointer; }
  button:disabled { cursor: not-allowed; }
  button { min-height: 44px; min-width: 44px; }
  [role="combobox"], [data-testid="stNumberInput"] input {
    min-height: 44px;
  }
  :focus-visible { outline: 3px solid #24603e !important; outline-offset: 3px; }
  [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
  .stCaption, .stCaption *, [data-testid="stCaptionContainer"],
  [data-testid="stCaptionContainer"] * { color: #4b584f !important; }
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

entry_mode = st.radio(
    "Part input", ["Common part presets", "Custom / STEP"], horizontal=True, key="entry_mode"
)
if st.session_state.get("last_entry_mode") != entry_mode:
    st.session_state.pop("result", None)
    st.session_state["last_entry_mode"] = entry_mode
if entry_mode == "Common part presets":
    render_preset_inputs(rates, thresholds)
    st.stop()
st.header("Custom part")

EXAMPLES = {
    "Milled bracket": "milled_bracket.json",
    "Turned spacer": "turned_spacer.json",
    "Sheet bracket": "sheet_bracket.json",
}
starting_point = st.selectbox(
    "Starting example",
    list(EXAMPLES),
    help="Illustrative dimensions, not measured production parts.",
)
sample = Part.model_validate_json((ROOT / "examples" / EXAMPLES[starting_point]).read_text())
process = st.selectbox(
    "Manufacturing process",
    list(Process),
    index=list(Process).index(sample.process),
    format_func=lambda p: p.value,
    key=f"process_{starting_point}",
)
materials = [key for key, material in rates.materials.items() if process in material.processes]
if not materials:
    st.error("This rate card has no material compatible with the selected process.")
    st.stop()
material = st.selectbox(
    "Material grade",
    materials,
    index=materials.index(sample.material) if sample.material in materials else 0,
    format_func=lambda key: rates.materials[key].label,
    key=f"material_{starting_point}_{process.value}",
)
selected_material = rates.materials[material]
price_reference = selected_material.price_reference
st.caption(f"Material budget rate: ₹{selected_material.price_kg:,.2f}/kg.")
if price_reference:
    st.caption(
        f"[Supplier listing]({price_reference.url}), {price_reference.supplier}. "
        f"Checked {price_reference.checked_on}. {price_reference.note}"
    )
upload_id, step_geometry, spindle_axis, flat_blank = None, None, "Z", False
with st.expander("Import a STEP solid"):
    st.caption(
        "Read one closed solid from a .step or .stp file, up to 20 MiB. "
        "File units are converted to mm. Holes, walls, tolerances and finish remain manual."
    )
    uploaded = st.file_uploader("STEP part", type=["step", "stp"], key="step_file")
    if uploaded is not None:
        upload_data = uploaded.getvalue()
        upload_id = uploaded.name + ":" + hashlib.sha256(upload_data).hexdigest()
    if st.session_state.get("step_upload_id") != upload_id:
        st.session_state.pop("step_geometry", None)
        st.session_state.pop("step_error", None)
        st.session_state.pop("result", None)
        st.session_state["step_upload_id"] = upload_id
    if uploaded is not None and process == Process.TURNING:
        spindle_axis = st.selectbox("STEP spindle axis", ["X", "Y", "Z"], index=2)
        st.caption(
            "Length follows the chosen axis. The initial stock diameter is the diagonal "
            "of the transverse bounding box, a conservative envelope. Review the actual diameter."
        )
    if uploaded is not None and process == Process.SHEET:
        flat_blank = st.checkbox("This STEP represents a developed flat blank")
        st.caption(
            "Folded sheet parts are not unfolded. Export a flat blank with thickness along Z."
        )
    if uploaded is not None:
        available = step_available()
        if not available:
            st.warning("Install this project's requirements.txt to enable the CAD reader.")
        if st.button(
            "Read and fill geometry",
            key="read_step",
            disabled=not available or (process == Process.SHEET and not flat_blank),
        ):
            st.session_state.pop("result", None)
            st.session_state.pop("step_geometry", None)
            st.session_state.pop("step_error", None)
            try:
                with st.spinner("Reading STEP solid, up to 30 seconds..."):
                    st.session_state["step_geometry"] = read_step(upload_data, uploaded.name)
                    st.session_state["step_generation"] = (
                        st.session_state.get("step_generation", 0) + 1
                    )
            except StepImportError as exc:
                st.session_state["step_error"] = str(exc)
    if st.session_state.get("step_error"):
        st.error(st.session_state["step_error"])
    step_geometry = st.session_state.get("step_geometry")
    if step_geometry:
        x, y, z = step_geometry.bounding_box_mm
        st.success(
            f"Read {step_geometry.file_name}. Review the geometry fields before calculating."
        )
        st.write(
            f"Global XYZ bounds: {x:.4f} × {y:.4f} × {z:.4f} mm. "
            f"Volume: {step_geometry.volume_cm3:.4f} cm³. "
            f"Surface area: {step_geometry.surface_area_cm2:.4f} cm²."
        )
        st.caption("Declared file units: " + ", ".join(step_geometry.source_length_units))

import_defaults = None
if step_geometry and (process != Process.SHEET or flat_blank):
    try:
        import_defaults = geometry_defaults(step_geometry, process, spindle_axis, flat_blank)
    except StepImportError as exc:
        st.error(str(exc))
if import_defaults:
    st.caption(f"Geometry seeded from {step_geometry.file_name}. Every dimension remains editable.")
context = (
    starting_point,
    process.value,
    material,
    upload_id,
    bool(import_defaults),
    spindle_axis,
    flat_blank,
    st.session_state.get("step_generation", 0),
)
stored_result = st.session_state.get("result")
if st.session_state.get("context") != context or (stored_result and len(stored_result) != 6):
    st.session_state.pop("result", None)
    st.session_state["context"] = context

st.caption(
    "Changing example, process or material clears the previous result. "
    "Form edits take effect when you calculate again."
)
form_key = "part_" + hashlib.sha256(repr(context).encode()).hexdigest()[:16]
defaults = sample.model_dump() | (import_defaults or {})
with st.form(form_key):
    st.subheader("Part and envelope")
    name = st.text_input("Part name", value=defaults["name"], max_chars=100)
    qty = st.number_input(
        "Batch quantity", min_value=1, max_value=10000000, value=sample.quantity, step=1
    )
    if process == Process.SHEET:
        st.caption("Enter the developed flat blank. Height is the sheet thickness.")
    elif process == Process.TURNING:
        st.caption("Width is the outside diameter of the cylindrical envelope.")
    cols = st.columns(3)
    length = cols[0].number_input(
        "Length (mm)", min_value=0.01, max_value=10000.0, value=defaults["length_mm"]
    )
    width = cols[1].number_input(
        "Diameter (mm)" if process == Process.TURNING else "Width (mm)",
        min_value=0.01,
        max_value=10000.0,
        value=defaults["width_mm"],
    )
    height = cols[2].number_input(
        "Thickness (mm)" if process == Process.SHEET else "Height (mm)",
        min_value=0.01,
        max_value=10000.0,
        value=2.0 if process == Process.SHEET and not import_defaults else defaults["height_mm"],
        disabled=process == Process.TURNING,
    )
    cols = st.columns(2)
    volume = cols[0].number_input(
        "Finished volume (cm³; 0 uses envelope)",
        min_value=0.0,
        value=(defaults["volume_cm3"] or 0.0)
        if import_defaults or process == sample.process
        else 0.0,
        help="Measured solid volume overrides the bounding envelope volume.",
    )
    area = cols[1].number_input(
        "Surface area (cm²; 0 uses envelope)",
        min_value=0.0,
        value=defaults["surface_area_cm2"] or 0.0,
        help="Use measured area for finishing charges when available.",
    )
    st.subheader("Features and DFM inputs")
    wall, max_wall = 3.0, 3.0
    corner, pocket_depth, pocket_width = 3.0, 0.0, 10.0
    supported = False
    bends, bend_radius, edge, bend_gap, perimeter, pierces = 0, 3.0, 0.0, 0.0, 0.0, 1
    draft = 2.0
    clearances_known = False
    holes = []
    if process != Process.SHEET:
        wall = st.number_input("Minimum wall (mm)", min_value=0.01, value=3.0)
        max_wall = wall
    if process in (Process.MILLING, Process.TURNING):
        cols = st.columns(3)
        hole_count = cols[0].number_input(
            "Identical hole count", min_value=0, max_value=10000, value=0, step=1
        )
        hole_diameter = cols[1].number_input("Hole diameter (mm)", min_value=0.01, value=6.0)
        hole_depth = cols[2].number_input("Hole depth (mm)", min_value=0.01, value=20.0)
        if hole_count:
            holes = [Hole(count=hole_count, diameter_mm=hole_diameter, depth_mm=hole_depth)]
        st.caption("One uniform hole group. Hole timing is represented by the effective MRR.")
    if process == Process.MILLING:
        cols = st.columns(3)
        corner = cols[0].number_input("Internal corner radius (mm)", min_value=0.0, value=3.0)
        pocket_depth = cols[1].number_input(
            "Deepest pocket (mm; 0 means none)", min_value=0.0, value=0.0
        )
        pocket_width = cols[2].number_input("Pocket width (mm)", min_value=0.01, value=10.0)
    elif process == Process.TURNING:
        supported = st.checkbox("Tailstock or steady rest planned", value=sample.supported)
    elif process == Process.SHEET:
        clearances_known = st.checkbox("Hole clearances are measured", value=False)
        st.caption("Leave unchecked to omit clearance checks. Measured zero clearance is checked.")
        cols = st.columns(2)
        bends = cols[0].number_input("Bend count", min_value=0, max_value=1000, value=2, step=1)
        bend_radius = cols[1].number_input("Inside bend radius (mm)", min_value=0.0, value=3.0)
        edge = cols[0].number_input(
            "Hole-edge to blank-edge clearance (mm)", min_value=0.0, value=0.0
        )
        bend_gap = cols[1].number_input("Hole-edge to bend tangent (mm)", min_value=0.0, value=0.0)
        perimeter = cols[0].number_input(
            "Total cut perimeter (mm; 0 uses outer rectangle)", min_value=0.0, value=0.0
        )
        pierces = cols[1].number_input(
            "Laser pierces", min_value=0, max_value=100000, value=1, step=1
        )
    else:
        max_wall = st.number_input("Maximum wall (mm)", min_value=0.01, value=6.0)
        draft = st.number_input("Draft angle (degrees)", min_value=0.0, max_value=30.0, value=2.0)
    cols = st.columns(2)
    tolerance = cols[0].number_input(
        "Tightest tolerance (IT grade)", min_value=1, max_value=16, value=9, step=1
    )
    default_ra = thresholds.minimum_ra[process]
    finish = cols[1].number_input(
        "Required surface finish Ra (µm)", min_value=0.01, value=default_ra
    )
    available_finishes = [
        key for key, item in rates.finishing.items() if material in item.materials
    ]
    secondary = st.multiselect(
        "Secondary operations",
        available_finishes,
        format_func=lambda key: rates.finishing[key].label,
    )
    st.subheader("Commercial assumptions")
    cols = st.columns(2)
    overhead = cols[0].number_input("Overhead (%)", min_value=0.0, max_value=100.0, value=15.0)
    margin = cols[1].number_input(
        "Margin as markup (%)", min_value=0.0, max_value=100.0, value=10.0
    )
    submitted = st.form_submit_button("Calculate cost and check DFM", type="primary")

if submitted:
    st.session_state.pop("result", None)
    try:
        part = Part(
            name=name,
            process=process,
            material=material,
            quantity=qty,
            length_mm=length,
            width_mm=width,
            height_mm=height,
            volume_cm3=volume or None,
            surface_area_cm2=area or None,
            holes=holes,
            wall_mm=wall,
            max_wall_mm=max_wall,
            corner_radius_mm=corner,
            pocket_depth_mm=pocket_depth,
            pocket_width_mm=pocket_width,
            supported=supported,
            bends=bends,
            bend_radius_mm=bend_radius,
            hole_edge_mm=edge if clearances_known else None,
            hole_bend_mm=bend_gap if clearances_known else None,
            cut_perimeter_mm=perimeter or None,
            pierces=pierces,
            draft_deg=draft,
            tolerance_it=tolerance,
            finish_ra_um=finish,
            secondary=secondary,
            overhead_pct=overhead,
            margin_pct=margin,
            geometry_import=step_geometry if import_defaults else None,
            turning_axis=spindle_axis if import_defaults and process == Process.TURNING else None,
        )
        with st.spinner("Calculating cost and screening geometry..."):
            st.session_state["result"] = calculate_estimate(part, rates, thresholds)
    except (ValidationError, ValueError) as exc:
        st.error(f"Check the part inputs: {exc}")

if "result" not in st.session_state:
    st.info("Enter a part above, then calculate to see costs, DFM findings and batch sensitivity.")
    st.stop()

render_estimate(st.session_state["result"])

import streamlit as st

from core.models import Process
from core.presets import PRESETS, build_preset
from ui.preset_diagram import preset_diagram
from ui.results import calculate_estimate, render_estimate


def render_preset_inputs(rates, thresholds):
    st.header("Choose a common part")
    st.write("Pick a part family, enter basic dimensions, and compare the estimated cost.")
    family = st.selectbox(
        "Part family", ["All parts", *dict.fromkeys(p.family for p in PRESETS.values())]
    )
    options = [key for key, p in PRESETS.items() if family == "All parts" or p.family == family]
    key = st.selectbox(
        "Common part",
        options,
        index=None,
        placeholder="Choose a part type",
        format_func=lambda value: PRESETS[value].label,
        key=f"preset_pick_{family}",
    )
    st.session_state.pop("result", None)
    if key is None:
        st.info(
            "Choose a part type to start. Geometry and cost update when you edit the dimensions."
        )
        return
    preset = PRESETS[key]
    st.subheader(preset.label)
    st.write(preset.description)
    st.caption(
        f"Process: {preset.process.value}. Nominal parametric geometry, not a standard drawing."
    )
    columns = st.columns(2)
    materials = [
        name for name, material in rates.materials.items() if preset.process in material.processes
    ]
    if not materials:
        st.error("No compatible material in the rate card for this preset.")
        return
    material = columns[0].selectbox(
        "Material grade",
        materials,
        index=materials.index(preset.material) if preset.material in materials else 0,
        format_func=lambda value: rates.materials[value].label,
        key=f"preset_material_{key}",
    )
    quantity = columns[1].number_input(
        "Batch quantity",
        min_value=1,
        max_value=10000000,
        value=100,
        step=1,
        key=f"preset_quantity_{key}",
    )
    price = rates.materials[material]
    st.caption(f"Material budget rate: ₹{price.price_kg:,.2f}/kg.")
    if price.price_reference:
        reference = price.price_reference
        st.caption(
            f"[Supplier listing]({reference.url}), checked {reference.checked_on}. "
            "Budget price; stock form, tax and order minimums need review."
        )
    inputs, diagram = st.columns([2, 1])
    parameters = {}
    with inputs:
        st.write("Basic dimensions")
        st.caption("Dimensions are in mm. Press Enter or leave a field to refresh the estimate.")
        cols = st.columns(2)
        for index, parameter in enumerate(p for p in preset.parameters if not p.advanced):
            suffix = f" ({parameter.unit})" if parameter.unit else ""
            value_type = int if parameter.integer else float
            parameters[parameter.key] = cols[index % 2].number_input(
                parameter.label + suffix,
                min_value=value_type(parameter.minimum),
                max_value=value_type(parameter.maximum),
                value=value_type(parameter.default),
                step=1 if parameter.integer else 0.5,
                key=f"preset_dim_{key}_{parameter.key}",
            )
    with st.expander("Finish and costing assumptions"):
        for parameter in (p for p in preset.parameters if p.advanced):
            parameters[parameter.key] = st.number_input(
                parameter.label,
                min_value=parameter.minimum,
                max_value=parameter.maximum,
                value=parameter.default,
                step=0.01,
                key=f"preset_dim_{key}_{parameter.key}",
            )
        finishes = [
            name for name, finish in rates.finishing.items() if material in finish.materials
        ]
        secondary = st.multiselect(
            "Secondary operations",
            finishes,
            format_func=lambda value: rates.finishing[value].label,
            key=f"preset_finishes_{key}_{material}",
        )
        cols = st.columns(2)
        overhead = cols[0].number_input(
            "Overhead (%)", min_value=0.0, max_value=100.0, value=15.0, key=f"preset_overhead_{key}"
        )
        margin = cols[1].number_input(
            "Margin as markup (%)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            key=f"preset_margin_{key}",
        )
        tolerance = cols[0].number_input(
            "Tightest tolerance (IT grade)",
            min_value=1,
            max_value=16,
            value=9,
            key=f"preset_it_{key}",
        )
        finish = cols[1].number_input(
            "Required surface finish Ra (µm)",
            min_value=0.01,
            value=thresholds.minimum_ra[preset.process],
            key=f"preset_ra_{key}",
        )
        supported = False
        draft = 2.0
        if preset.process == Process.TURNING:
            supported = st.checkbox("Tailstock or steady rest planned", key=f"preset_support_{key}")
        elif preset.process in (Process.SAND, Process.DIE):
            draft = st.number_input(
                "Draft angle (degrees)",
                min_value=0.0,
                max_value=30.0,
                value=2.0,
                key=f"preset_draft_{key}",
            )
        for assumption in preset.assumptions:
            st.write(assumption)
    try:
        part = build_preset(
            key,
            parameters,
            material=material,
            quantity=quantity,
            secondary=secondary,
            overhead_pct=overhead,
            margin_pct=margin,
            tolerance_it=tolerance,
            finish_ra_um=finish,
            supported=supported,
            draft_deg=draft,
        )
    except ValueError as exc:
        st.error(f"Check the preset dimensions: {exc}")
        return
    with diagram:
        st.image(
            preset_diagram(key, parameters),
            caption=f"{preset.label} schematic",
            width="stretch",
        )
        st.caption("Schematic plan / section. Bend radii and small details are not drawn to scale.")
    st.caption(
        f"Calculated geometry: {part.net_volume_cm3:.3f} cm³, {part.area_cm2:.3f} cm². "
        f"Stock envelope {part.length_mm:.2f} × {part.width_mm:.2f} × {part.height_mm:.2f} mm."
    )
    try:
        with st.spinner("Updating the estimate..."):
            bundle = calculate_estimate(part, rates, thresholds)
    except ValueError as exc:
        st.error(f"Could not estimate this preset: {exc}")
        return
    st.session_state["result"] = bundle
    render_estimate(bundle, live=True)

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from core.audit import audit_payload
from core.dfm_rules import check_dfm
from core.estimator import batch_sensitivity, estimate, with_changes
from core.models import Process
from core.report import build_report


def calculate_estimate(part, rates, thresholds):
    result = estimate(part, rates)
    findings = check_dfm(part, rates, thresholds)
    pdf = build_report(result, findings, rates, thresholds)
    audit = audit_payload(result, findings, rates, thresholds)
    return result, findings, pdf, rates, thresholds, audit


def render_estimate(bundle, *, live=False):
    result, findings, pdf, saved_rates, saved_thresholds, audit = bundle
    part = result.part
    st.divider()
    st.header("Estimate")
    st.caption(
        f"{part.name} | {part.process.value} | batch {part.quantity:,}. "
        + (
            "Updated from the dimensions above."
            if live
            else "Results and exports use the last submitted inputs."
        )
    )
    cols = st.columns([2, 1, 1])
    cols[0].metric("Should-cost / unit", f"₹{result.unit_cost:,.2f}")
    cols[1].metric("Batch total", f"₹{result.batch_cost:,.2f}")
    cols[2].metric("Net part mass", f"{result.mass_kg:.4f} kg")
    st.caption(
        f"Modelled cycle: {result.cycle_min:.3f} min. "
        "Sheet cycle covers cutting only; casting cycle is informational."
    )
    breakdown = pd.DataFrame(
        {"Component": result.costs.keys(), "INR / unit": result.costs.values()}
    )
    cols = st.columns(2)
    cols[0].dataframe(
        breakdown,
        hide_index=True,
        width="stretch",
        column_config={"INR / unit": st.column_config.NumberColumn(format="%.2f")},
    )
    fig = px.bar(
        breakdown,
        x="INR / unit",
        y="Component",
        orientation="h",
        color_discrete_sequence=["#24603e"],
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=10, t=10, b=0),
        yaxis=dict(autorange="reversed"),
        height=350,
    )
    cols[1].plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.subheader("DFM findings")
    st.caption(
        "Heuristic screening only. Review with the manufacturing shop; "
        "these findings do not change the estimate automatically."
    )
    if not findings:
        st.success("No configured rule triggered. This is not manufacturing approval.")
    for finding in findings:
        show = {"critical": st.error, "warning": st.warning, "info": st.info}[finding.severity]
        show(
            f"{finding.severity.capitalize()}: {finding.message} "
            f"Suggested fix: {finding.suggestion}"
        )
    st.subheader("Batch-size sensitivity")
    sensitivity = pd.DataFrame(batch_sensitivity(part, saved_rates))
    fig = px.line(
        sensitivity,
        x="Quantity",
        y="Unit cost (INR)",
        markers=True,
        log_x=True,
        color_discrete_sequence=["#24603e"],
    )
    fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), height=300)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with st.expander("Inspect sensitivity values"):
        st.dataframe(sensitivity, hide_index=True, width="stretch")
    with st.expander("Assumptions and rate basis"):
        for assumption in result.assumptions:
            st.write(assumption)
        st.write(f"Rate source: {result.rate_source}. Date: {result.rate_date}.")
        st.json(saved_rates.model_dump(mode="json", by_alias=True), expanded=False)
        st.caption(
            "STEP import measures bounds, solid volume and surface area only. "
            "Features are entered manually. Files are processed on the app server; "
            "no external CAD service is used."
        )
    st.subheader("Compare an alternative")
    st.caption(
        "Comparison holds the current estimate's dimensions, volume, finish and quantity fixed. "
        "A process change may need a redesigned part or additional operations."
    )
    cols = st.columns(2)
    alternative_process = cols[0].selectbox(
        "Alternative process",
        list(Process),
        index=list(Process).index(part.process),
        format_func=lambda p: p.value,
    )
    alternative_materials = [
        key for key, item in saved_rates.materials.items() if alternative_process in item.processes
    ]
    if alternative_materials:
        alternative_material = cols[1].selectbox(
            "Alternative material",
            alternative_materials,
            format_func=lambda key: saved_rates.materials[key].label,
        )
        try:
            alternative_part = with_changes(
                part, process=alternative_process, material=alternative_material
            )
            alternative = estimate(alternative_part, saved_rates)
            comparison = pd.DataFrame(
                {
                    "Component": list(result.costs)
                    + [key for key in alternative.costs if key not in result.costs]
                }
            )
            comparison["Submitted (INR)"] = comparison["Component"].map(result.costs).fillna(0)
            comparison["Alternative (INR)"] = (
                comparison["Component"].map(alternative.costs).fillna(0)
            )
            st.dataframe(
                comparison,
                hide_index=True,
                width="stretch",
                column_config={
                    "Submitted (INR)": st.column_config.NumberColumn(format="%.2f"),
                    "Alternative (INR)": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            delta = alternative.unit_cost - result.unit_cost
            st.write(
                f"Submitted ₹{result.unit_cost:,.2f}/unit; "
                f"alternative ₹{alternative.unit_cost:,.2f}/unit. "
                f"Difference: ₹{delta:+,.2f} ({delta / result.unit_cost:+.1%})."
            )
            alternative_findings = check_dfm(alternative_part, saved_rates, saved_thresholds)
            st.caption(
                f"Alternative screening: {len(alternative_findings)} finding(s). "
                "Exports below contain the primary estimate only."
            )
            for finding in alternative_findings:
                st.write(f"{finding.severity.capitalize()}: {finding.message} {finding.suggestion}")
        except ValueError as exc:
            st.warning(f"This alternative cannot use the submitted geometry or finish: {exc}")
    else:
        st.info("No compatible material in this rate card for the alternative process.")
    st.subheader("Export estimate")
    cols = st.columns(3)
    cols[0].download_button(
        "Download PDF report", pdf, file_name="dfm-estimate.pdf", mime="application/pdf"
    )
    cols[1].download_button(
        "Download cost CSV",
        breakdown.to_csv(index=False).encode("utf-8"),
        file_name="cost-breakdown.csv",
        mime="text/csv",
    )
    cols[2].download_button(
        "Download audit JSON",
        json.dumps(audit, indent=2).encode("utf-8"),
        file_name="estimate-audit.json",
        mime="application/json",
    )

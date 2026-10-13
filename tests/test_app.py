from streamlit.testing.v1 import AppTest

from core.config import ROOT


def number(app, label):
    return next(item for item in app.number_input if item.label == label)


def select(app, label):
    return next(item for item in app.selectbox if item.label == label)


def test_form_empty_calculate_error_and_result_reset():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not app.exception
    assert "Enter a part above" in app.info[0].value
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "₹350.79"
    assert len(app.get("download_button")) == 3
    number(app, "Finished volume (cm³; 0 uses envelope)").set_value(99999)
    app.button[0].click().run()
    assert not app.exception
    assert app.error
    assert len(app.metric) == 0
    select(app, "Starting example").select("Turned spacer").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    select(app, "Manufacturing process").select("Sheet metal").run()
    assert len(app.metric) == 0


def test_sheet_and_casting_and_alternative_processes():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    select(app, "Starting example").select("Sheet bracket").run()
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "₹80.33"
    select(app, "Alternative process").select("Die casting").run()
    assert not app.exception
    select(app, "Manufacturing process").select("Sand casting").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    select(app, "Manufacturing process").select("Die casting").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3


def test_all_milling_inputs_are_submitted_and_stale_results_are_labelled():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    app.text_input[0].set_value("Fixture housing")
    changes = {
        "Batch quantity": 25,
        "Length (mm)": 80.0,
        "Width (mm)": 50.0,
        "Height (mm)": 20.0,
        "Finished volume (cm³; 0 uses envelope)": 40.0,
        "Surface area (cm²; 0 uses envelope)": 100.0,
        "Minimum wall (mm)": 2.0,
        "Identical hole count": 2,
        "Hole diameter (mm)": 2.0,
        "Hole depth (mm)": 20.0,
        "Internal corner radius (mm)": 0.5,
        "Deepest pocket (mm; 0 means none)": 10.0,
        "Pocket width (mm)": 2.0,
        "Tightest tolerance (IT grade)": 6,
        "Required surface finish Ra (µm)": 0.8,
        "Overhead (%)": 20.0,
        "Margin as markup (%)": 5.0,
    }
    for label, value in changes.items():
        number(app, label).set_value(value)
    app.multiselect[0].select("anodize")
    app.button[0].click().run()
    assert not app.exception
    result, findings, pdf, _, _, audit = app.session_state["result"]
    assert result.part.name == "Fixture housing"
    assert result.part.quantity == 25
    assert result.costs["Finishing"] == 24
    assert len(findings) >= 5
    assert pdf.startswith(b"%PDF")
    assert audit["estimate"]["part"]["holes"][0]["count"] == 2
    old_cost = app.metric[0].value
    number(app, "Batch quantity").set_value(500)
    app.run()
    assert app.metric[0].value == old_cost
    assert app.session_state["result"][0].part.quantity == 25


def test_zero_measured_clearances_and_turning_support():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    select(app, "Starting example").select("Sheet bracket").run()
    app.checkbox[0].check()
    number(app, "Thickness (mm)").set_value(3.0)
    number(app, "Bend count").set_value(3)
    number(app, "Inside bend radius (mm)").set_value(1.0)
    number(app, "Total cut perimeter (mm; 0 uses outer rectangle)").set_value(500.0)
    number(app, "Laser pierces").set_value(4)
    app.button[0].click().run()
    assert not app.exception
    rules = {finding.rule for finding in app.session_state["result"][1]}
    assert {"sheet.hole_edge", "sheet.hole_bend"}.issubset(rules)
    select(app, "Starting example").select("Turned spacer").run()
    app.checkbox[0].uncheck()
    app.button[0].click().run()
    assert not app.exception
    assert "turn.slender" in {finding.rule for finding in app.session_state["result"][1]}


def test_material_and_alternative_geometry_validation():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    number(app, "Width (mm)").set_value(10.0)
    number(app, "Finished volume (cm³; 0 uses envelope)").set_value(10.0)
    app.button[0].click().run()
    select(app, "Alternative process").select("CNC turning").run()
    assert not app.exception
    assert any("cannot use" in warning.value for warning in app.warning)
    select(app, "Material grade").select("stainless_304").run()
    assert not app.exception
    assert len(app.metric) == 0
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3


def test_casting_features_reach_screening_and_report():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    select(app, "Manufacturing process").select("Sand casting").run()
    number(app, "Maximum wall (mm)").set_value(9.0)
    number(app, "Draft angle (degrees)").set_value(0.0)
    app.button[0].click().run()
    assert not app.exception
    result, findings, pdf, _, _, _ = app.session_state["result"]
    assert result.part.max_wall_mm == 9
    assert {"cast.wall_variation", "cast.draft"}.issubset(finding.rule for finding in findings)
    assert pdf.startswith(b"%PDF")

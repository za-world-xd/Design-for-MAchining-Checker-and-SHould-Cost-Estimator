from streamlit.testing.v1 import AppTest

from core.config import ROOT


def button(app, label):
    return next(item for item in app.button if item.label == label)


def select(app, label):
    return next(item for item in app.selectbox if item.label == label)


def test_uploaded_step_fills_geometry_and_export_provenance():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=45).run()
    data = (ROOT / "examples/step_block.step").read_bytes()
    app.file_uploader[0].set_value(("block.step", data, "application/step")).run()
    button(app, "Read and fill geometry").click().run()
    assert not app.exception
    inputs = {widget.label: widget.value for widget in app.number_input}
    assert inputs["Length (mm)"] == 100
    assert inputs["Width (mm)"] == 60
    assert inputs["Height (mm)"] == 20
    assert inputs["Finished volume (cm³; 0 uses envelope)"] == 120
    assert inputs["Surface area (cm²; 0 uses envelope)"] == 184
    next(widget for widget in app.number_input if widget.label == "Length (mm)").set_value(200)
    app.run()
    button(app, "Read and fill geometry").click().run()
    assert next(widget for widget in app.number_input if widget.label == "Length (mm)").value == 100
    button(app, "Calculate cost and check DFM").click().run()
    assert not app.exception
    audit = app.session_state["result"][5]
    assert audit["estimate"]["part"]["geometry_import"]["file_name"] == "block.step"
    assert len(audit["estimate"]["part"]["geometry_import"]["sha256"]) == 64
    app.file_uploader[0].set_value(None).run()
    assert not app.exception
    assert not app.metric
    assert app.session_state.get("step_geometry") is None


def test_replacing_import_with_bad_file_cannot_reuse_old_geometry():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=45).run()
    data = (ROOT / "examples/step_block.step").read_bytes()
    app.file_uploader[0].set_value(("block.step", data, "application/step")).run()
    button(app, "Read and fill geometry").click().run()
    button(app, "Calculate cost and check DFM").click().run()
    app.file_uploader[0].set_value(("broken.step", b"not STEP", "application/step")).run()
    button(app, "Read and fill geometry").click().run()
    assert not app.exception
    assert any("Part 21" in error.value for error in app.error)
    assert not app.metric
    assert app.session_state.get("step_geometry") is None
    button(app, "Calculate cost and check DFM").click().run()
    assert not app.exception
    assert app.session_state["result"][0].part.geometry_import is None


def test_sheet_requires_confirmation_and_turning_axis_is_editable():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=45).run()
    data = (ROOT / "examples/step_block.step").read_bytes()
    select(app, "Manufacturing process").select("Sheet metal").run()
    app.file_uploader[0].set_value(("flat.step", data, "application/step")).run()
    assert button(app, "Read and fill geometry").disabled
    next(item for item in app.checkbox if item.label.startswith("This STEP")).check().run()
    button(app, "Read and fill geometry").click().run()
    assert not app.exception
    assert next(item for item in app.number_input if item.label == "Thickness (mm)").value == 20
    select(app, "Manufacturing process").select("CNC turning").run()
    select(app, "STEP spindle axis").select("X").run()
    button(app, "Calculate cost and check DFM").click().run()
    assert not app.exception
    assert app.session_state["result"][0].part.length_mm == 100
    assert app.session_state["result"][0].part.turning_axis == "X"

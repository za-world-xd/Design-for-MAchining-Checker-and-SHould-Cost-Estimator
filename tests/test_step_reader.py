import math
import subprocess

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pln, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopoDS import TopoDS_Compound

from core.models import Part, Process
from core.step_reader import StepImportError, geometry_defaults, read_step


def export_step(path, shape, unit="MM"):
    Interface_Static.SetCVal_s("write.step.unit", unit)
    try:
        writer = STEPControl_Writer()
        assert writer.Transfer(shape, STEPControl_AsIs) == IFSelect_RetDone
        assert writer.Write(str(path)) == IFSelect_RetDone
    finally:
        Interface_Static.SetCVal_s("write.step.unit", "MM")
    return path.read_bytes()


@pytest.fixture
def box_step(tmp_path):
    return export_step(tmp_path / "box.step", BRepPrimAPI_MakeBox(100, 60, 20).Shape())


def test_box_measurements_and_provenance(box_step):
    geometry = read_step(box_step, "bracket.STEP")
    assert geometry.bounding_box_mm == pytest.approx((100, 60, 20))
    assert geometry.volume_cm3 == pytest.approx(120)
    assert geometry.surface_area_cm2 == pytest.approx(184)
    assert len(geometry.sha256) == 64
    part = Part(**geometry_defaults(geometry, Process.MILLING))
    assert part.net_volume_cm3 == pytest.approx(120)
    assert part.geometry_import.file_name == "bracket.STEP"


def test_declared_inch_units_are_converted_to_mm(tmp_path):
    data = export_step(tmp_path / "inch.stp", BRepPrimAPI_MakeBox(25.4, 50.8, 12.7).Shape(), "INCH")
    assert b"CONVERSION_BASED_UNIT" in data
    geometry = read_step(data, "inch.stp")
    assert geometry.bounding_box_mm == pytest.approx((25.4, 50.8, 12.7))
    assert geometry.volume_cm3 == pytest.approx(25.4 * 50.8 * 12.7 / 1000)


def test_turning_axis_maps_conservative_envelope(tmp_path):
    data = export_step(tmp_path / "spacer.step", BRepPrimAPI_MakeCylinder(10, 80).Shape())
    geometry = read_step(data, "spacer.step")
    part = Part(process=Process.TURNING, **geometry_defaults(geometry, Process.TURNING, axis="Z"))
    assert part.length_mm == pytest.approx(80)
    assert part.width_mm == pytest.approx(math.hypot(20, 20))
    assert part.net_volume_cm3 == pytest.approx(math.pi * 10**2 * 80 / 1000)
    assert part.turning_axis == "Z"


def test_drilled_block_uses_solid_volume_and_internal_surface_area(tmp_path):
    box = BRepPrimAPI_MakeBox(100, 60, 20).Shape()
    cutter = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(50, 30, -1), gp_Dir(0, 0, 1)), 3, 22).Shape()
    drilled = BRepAlgoAPI_Cut(box, cutter).Shape()
    data = export_step(tmp_path / "drilled.step", drilled)
    geometry = read_step(data, "drilled.step")
    assert geometry.volume_cm3 == pytest.approx(120 - math.pi * 3**2 * 20 / 1000)
    assert geometry.surface_area_cm2 == pytest.approx(
        184 - 2 * math.pi * 3**2 / 100 + 2 * math.pi * 3 * 20 / 100
    )
    assert Part(**geometry_defaults(geometry, Process.MILLING)).holes == []


def test_sheet_requires_flat_blank_confirmation(box_step):
    geometry = read_step(box_step, "blank.step")
    with pytest.raises(StepImportError, match="flat blank"):
        geometry_defaults(geometry, Process.SHEET)
    assert geometry_defaults(geometry, Process.SHEET, flat_blank=True)["height_mm"] == 20


def test_multiple_solids_rejected(tmp_path):
    builder, compound = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, BRepPrimAPI_MakeBox(10, 10, 10).Shape())
    builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(30, 0, 0), 10, 10, 10).Shape())
    data = export_step(tmp_path / "assembly.step", compound)
    with pytest.raises(StepImportError, match="one solid"):
        read_step(data, "assembly.step")


def test_open_surface_rejected(tmp_path):
    face = BRepBuilderAPI_MakeFace(gp_Pln(), 0, 10, 0, 10).Face()
    data = export_step(tmp_path / "face.step", face)
    with pytest.raises(StepImportError, match="closed solid"):
        read_step(data, "face.step")


@pytest.mark.parametrize(
    "data,name,message",
    [
        (b"", "empty.step", "nonempty"),
        (b"not CAD", "part.step", "Part 21"),
        (b"ISO-10303-21;", "part.stl", ".step or .stp"),
        (b"ISO-10303-21; DATA; ENDSEC; END-ISO-10303-21;", "bad.stp", "malformed"),
    ],
)
def test_invalid_uploads(data, name, message):
    with pytest.raises(StepImportError, match=message):
        read_step(data, name)


def test_size_limit_checked_before_parser(monkeypatch, box_step):
    monkeypatch.setattr("core.step_reader.MAX_STEP_BYTES", 10)
    with pytest.raises(StepImportError, match="20 MiB"):
        read_step(box_step, "part.step")


def test_missing_dependency_is_readable(monkeypatch, box_step):
    monkeypatch.setattr("core.step_reader.step_available", lambda: False)
    with pytest.raises(StepImportError, match="requirements.txt"):
        read_step(box_step, "part.step")


def test_native_parser_timeout_is_readable(monkeypatch, box_step):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("CAD reader", 30)

    monkeypatch.setattr("core.step_reader.subprocess.run", timeout)
    with pytest.raises(StepImportError, match="30 seconds"):
        read_step(box_step, "part.step")

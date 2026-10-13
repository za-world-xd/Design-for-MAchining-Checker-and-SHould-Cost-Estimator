"""Single-solid STEP measurements; the native parser runs in a disposable subprocess."""

import hashlib
import json
import math
import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from core.config import ROOT
from core.models import Process, StepGeometry

MAX_STEP_BYTES = 20 * 1024 * 1024
STEP_TIMEOUT_SECONDS = 30


class StepImportError(ValueError):
    pass


def step_available() -> bool:
    return find_spec("OCP") is not None


def read_step(data: bytes, filename: str) -> StepGeometry:
    """Read STEP Part 21 bytes, returning mm, cm3 and cm2 with source provenance."""
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if Path(filename).suffix.lower() not in (".step", ".stp"):
        raise StepImportError("Choose a .step or .stp file (STEP Part 21).")
    if not data or len(data) > MAX_STEP_BYTES:
        raise StepImportError("STEP files must be nonempty and no larger than 20 MiB.")
    if len(filename) > 255:
        raise StepImportError("The STEP filename must be at most 255 characters.")
    if not data[:256].lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"ISO-10303-21;"):
        raise StepImportError("This is not a STEP Part 21 file. Export an uncompressed STEP solid.")
    if not step_available():
        raise StepImportError(
            "STEP support is unavailable. Install this project's requirements.txt."
        )
    try:
        with TemporaryDirectory(prefix="dfm-step-") as temporary:
            source, output = Path(temporary) / "part.step", Path(temporary) / "measurements.json"
            source.write_bytes(data)
            completed = subprocess.run(
                [sys.executable, "-m", "core.step_reader", str(source), str(output)],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=STEP_TIMEOUT_SECONDS,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                check=False,
            )
            if not output.exists():
                raise StepImportError("The CAD reader could not complete this file. Re-export it.")
            payload = json.loads(output.read_text(encoding="utf-8"))
            if completed.returncode or "error" in payload:
                raise StepImportError(payload.get("error", "STEP geometry could not be read."))
            return StepGeometry(
                file_name=filename, sha256=hashlib.sha256(data).hexdigest(), **payload
            )
    except subprocess.TimeoutExpired as exc:
        raise StepImportError(
            "STEP import exceeded 30 seconds. Simplify or split the part."
        ) from exc
    except (ValidationError, json.JSONDecodeError) as exc:
        raise StepImportError(
            "STEP measurements are invalid or outside the supported 0.01 to 10,000 mm envelope."
        ) from exc
    except OSError as exc:
        raise StepImportError(
            "The temporary CAD reader could not start or access its files."
        ) from exc


def geometry_defaults(geometry: StepGeometry, process: Process, axis="Z", flat_blank=False) -> dict:
    """Map global XYZ extents to the costing envelope without inferring manufacturing features."""
    if axis not in ("X", "Y", "Z"):
        raise StepImportError("Choose X, Y or Z as the turning axis.")
    if process == Process.SHEET and not flat_blank:
        raise StepImportError(
            "Sheet-metal import requires a developed flat blank, not a folded part."
        )
    dimensions = geometry.bounding_box_mm
    length, width, height = dimensions
    if process == Process.TURNING:
        spindle = "XYZ".index(axis)
        length = dimensions[spindle]
        transverse = [value for index, value in enumerate(dimensions) if index != spindle]
        # A circle through the bounding rectangle corners contains arbitrary cross-sections.
        width = math.hypot(*transverse)
        height = width
    if width > 10000:
        raise StepImportError("The mapped stock diameter exceeds the 10,000 mm input limit.")
    return {
        "name": Path(geometry.file_name).stem[:100],
        "length_mm": length,
        "width_mm": width,
        "height_mm": height,
        "volume_cm3": geometry.volume_cm3,
        "surface_area_cm2": geometry.surface_area_cm2,
        "geometry_import": geometry,
        "turning_axis": axis if process == Process.TURNING else None,
    }


def _measure_solid(path: Path) -> dict:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_SOLID
    from OCP.TopoDS import TopoDS_Iterator

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise StepImportError("The STEP document is malformed or unsupported. Re-export the solid.")
    if reader.NbRootsForTransfer() != 1:
        raise StepImportError(
            "Import one solid part at a time; multi-part assemblies are unsupported."
        )
    reader.SetSystemLengthUnit(1.0)
    if reader.TransferRoots() != 1:
        raise StepImportError("The STEP geometry could not be transferred into a solid.")
    pending, solids = [reader.OneShape()], []
    while pending:
        shape = pending.pop()
        if shape.IsNull():
            raise StepImportError("The STEP file contains empty geometry.")
        if shape.ShapeType() == TopAbs_SOLID:
            solids.append(shape)
        elif shape.ShapeType() == TopAbs_COMPOUND:
            children = TopoDS_Iterator(shape)
            while children.More():
                pending.append(children.Value())
                children.Next()
        else:
            raise StepImportError(
                "Import a closed solid; open surfaces and wire geometry are unsupported."
            )
        if len(solids) > 1:
            raise StepImportError(
                "Import one solid part at a time; multi-part assemblies are unsupported."
            )
    if len(solids) != 1 or not BRepCheck_Analyzer(solids[0]).IsValid():
        raise StepImportError(
            "The STEP shape is not a valid solid. Repair it in CAD and re-export."
        )
    solid = solids[0]
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(solid, box, False, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    volume, area = GProp_GProps(), GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, volume)
    BRepGProp.SurfaceProperties_s(solid, area)
    return {
        "bounding_box_mm": (xmax - xmin, ymax - ymin, zmax - zmin),
        "volume_cm3": volume.Mass() / 1000,
        "surface_area_cm2": area.Mass() / 100,
    }


def _worker(source: Path, output: Path) -> int:
    try:
        measurements = _measure_solid(source)
    except StepImportError as exc:
        output.write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
        return 1
    except ImportError:
        output.write_text(
            json.dumps({"error": "CAD libraries could not load. Reinstall requirements.txt."})
        )
        return 1
    except Exception:
        output.write_text(
            json.dumps({"error": "The CAD kernel could not measure this solid. Re-export it."})
        )
        return 1
    output.write_text(json.dumps(measurements), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker(Path(sys.argv[1]), Path(sys.argv[2])))

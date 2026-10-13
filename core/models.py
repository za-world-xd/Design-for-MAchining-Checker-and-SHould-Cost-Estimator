from enum import Enum
from math import pi
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Process(str, Enum):
    MILLING = "CNC milling"
    TURNING = "CNC turning"
    SHEET = "Sheet metal"
    SAND = "Sand casting"
    DIE = "Die casting"


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    diameter_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    count: int = Field(default=1, ge=1, le=10000)


class StepGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
    file_name: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bounding_box_mm: tuple[
        Annotated[float, Field(ge=0.01, le=10000)],
        Annotated[float, Field(ge=0.01, le=10000)],
        Annotated[float, Field(ge=0.01, le=10000)],
    ]
    volume_cm3: float = Field(gt=0)
    surface_area_cm2: float = Field(gt=0)


class Part(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(default="Machined bracket", min_length=1, max_length=100)
    process: Process = Process.MILLING
    material: str = "aluminium_6061"
    quantity: int = Field(default=100, ge=1, le=10000000)
    length_mm: float = Field(default=100, gt=0, le=10000)
    width_mm: float = Field(default=60, gt=0, le=10000)
    height_mm: float = Field(default=20, gt=0, le=10000)
    volume_cm3: float | None = Field(default=None, gt=0)
    surface_area_cm2: float | None = Field(default=None, gt=0)
    holes: list[Hole] = Field(default_factory=list, max_length=100)
    wall_mm: float = Field(default=3, gt=0)
    corner_radius_mm: float = Field(default=3, ge=0)
    pocket_depth_mm: float = Field(default=0, ge=0)
    pocket_width_mm: float = Field(default=10, gt=0)
    tolerance_it: int = Field(default=9, ge=1, le=16)
    finish_ra_um: float = Field(default=3.2, gt=0)
    supported: bool = False
    bends: int = Field(default=2, ge=0, le=1000)
    bend_radius_mm: float = Field(default=3, ge=0)
    hole_edge_mm: float | None = Field(default=None, ge=0)
    hole_bend_mm: float | None = Field(default=None, ge=0)
    cut_perimeter_mm: float | None = Field(default=None, gt=0)
    pierces: int = Field(default=1, ge=0, le=100000)
    max_wall_mm: float = Field(default=3, gt=0)
    draft_deg: float = Field(default=2, ge=0, le=30)
    secondary: list[str] = Field(default_factory=list, max_length=4)
    overhead_pct: float = Field(default=15, ge=0, le=100)
    margin_pct: float = Field(default=10, ge=0, le=100)
    geometry_import: StepGeometry | None = None
    turning_axis: Literal["X", "Y", "Z"] | None = None

    @property
    def envelope_cm3(self) -> float:
        if self.process == Process.TURNING:
            # Width is the stock diameter; height is unused for axisymmetric parts.
            return pi * (self.width_mm / 2) ** 2 * self.length_mm / 1000
        return self.length_mm * self.width_mm * self.height_mm / 1000

    @property
    def net_volume_cm3(self) -> float:
        return self.volume_cm3 if self.volume_cm3 is not None else self.envelope_cm3

    @property
    def area_cm2(self) -> float:
        if self.surface_area_cm2 is not None:
            return self.surface_area_cm2
        if self.process == Process.TURNING:
            radius = self.width_mm / 2
            return (2 * pi * radius * (radius + self.length_mm)) / 100
        a, b, c = self.length_mm, self.width_mm, self.height_mm
        return 2 * (a * b + b * c + a * c) / 100

    @model_validator(mode="after")
    def check_geometry(self):
        if not self.name.strip():
            raise ValueError("Part name must contain text")
        if self.net_volume_cm3 > self.envelope_cm3 * (1 + 1e-9):
            raise ValueError("Finished volume exceeds the part envelope")
        if self.max_wall_mm < self.wall_mm:
            raise ValueError("Maximum wall must be at least the minimum wall")
        if len(set(self.secondary)) != len(self.secondary):
            raise ValueError("Select each finishing operation only once")
        return self


class Finding(BaseModel):
    rule: str
    severity: str
    message: str
    suggestion: str


class Estimate(BaseModel):
    part: Part
    costs: dict[str, float]
    assumptions: list[str]
    mass_kg: float
    cycle_min: float
    rate_source: str
    rate_date: str

    @property
    def unit_cost(self) -> float:
        return sum(self.costs.values())

    @property
    def batch_cost(self) -> float:
        return self.unit_cost * self.part.quantity

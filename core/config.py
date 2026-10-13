from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models import Process

ROOT = Path(__file__).resolve().parents[1]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Fraction = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MaterialPriceReference(ConfigModel):
    kind: Literal["public_listing_estimate"]
    supplier: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    checked_on: date
    listed_price_kg: Positive
    minimum_order_kg: Positive | None = None
    stock_form: str
    tax_basis: str
    note: str


class Material(ConfigModel):
    label: str
    density_kg_cm3: Positive
    price_kg: Positive
    mrr_cm3_min: Positive
    min_wall_mm: Positive
    processes: list[Process]
    price_reference: MaterialPriceReference | None = None


class Machine(ConfigModel):
    hour_rate: Positive
    setup_hours: Nonnegative
    programming: Nonnegative


class Machining(ConfigModel):
    stock_factor: Annotated[float, Field(ge=1, allow_inf_nan=False)]
    scrap_allowance: Nonnegative
    noncutting_factor: Nonnegative
    handling_min: Nonnegative
    tooling_fraction: Nonnegative
    milling: Machine
    turning: Machine


class Sheet(ConfigModel):
    utilisation: Fraction
    laser_hour_rate: Positive
    laser_speed_mm_min: Positive
    speed_reference_thickness_mm: Positive
    pierce_seconds: Nonnegative
    bend_cost: Nonnegative
    setup_hours: Nonnegative
    programming: Nonnegative
    tooling_per_batch: Nonnegative


class CastingProcess(ConfigModel):
    yield_fraction: Fraction = Field(alias="yield")
    tooling_per_batch: Nonnegative
    setup_per_batch: Nonnegative
    conversion_per_kg: Nonnegative
    fettling_per_kg: Nonnegative
    cycle_min: Positive


class Casting(ConfigModel):
    sand: CastingProcess
    die: CastingProcess


class Finish(ConfigModel):
    label: str
    basis: Literal["dm2", "kg"]
    rate: Nonnegative
    minimum_lot: Nonnegative
    materials: list[str]


class Inspection(ConfigModel):
    hour_rate: Nonnegative
    minutes_per_part: Nonnegative


class Metadata(ConfigModel):
    currency: Literal["INR"]
    status: Literal["illustrative", "quoted"]
    source: str = Field(min_length=1)
    date: date | None

    @model_validator(mode="after")
    def require_quote_provenance(self):
        if self.status == "quoted" and (self.date is None or "placeholder" in self.source.lower()):
            raise ValueError("Quoted rates require a source and quote date")
        return self


class Rates(ConfigModel):
    metadata: Metadata
    materials: dict[str, Material] = Field(min_length=1)
    machining: Machining
    sheet: Sheet
    casting: Casting
    inspection: Inspection
    finishing: dict[str, Finish]

    @model_validator(mode="after")
    def check_material_references(self):
        for finish in self.finishing.values():
            if not set(finish.materials).issubset(self.materials):
                raise ValueError("Finishing rate references an unknown material")
        return self


def load_rates(path: Path | None = None) -> Rates:
    with (path or ROOT / "config" / "rates.yaml").open(encoding="utf-8") as stream:
        try:
            return Rates.model_validate(yaml.safe_load(stream))
        except yaml.YAMLError as exc:
            raise ValueError("Rate card contains invalid YAML") from exc

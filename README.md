# DFM checker and should-cost estimator

Python calculation engine and Streamlit worksheet for early manufacturing estimates in INR.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m streamlit run app.py
```

The Streamlit worksheet supports milling, turning, sheet metal, sand casting and die casting.
Material prices in `config/rates.yaml` are Indian public-listing budget estimates,
checked on November 2026. Machine and finishing rates remain illustrative.
These are not vendor quotes. Dimensions use mm,
volume uses cm3, mass uses kg, and all costs use INR.

## Cost basis

Material uses stock volume, density, price per kg and a scrap allowance. Machine cost
uses removed volume divided by an effective removal rate, plus non-cutting and handling
time. Setup and programming are amortised across the batch. Tooling is a fraction of
machine cost. Finishing respects minimum lot charges.

Overhead applies to direct costs; the margin input is a markup on cost plus overhead.
Sheet metal uses the flat blank, thickness-adjusted laser speed, pierces and bend charges.
Casting uses metal yield, weight-based conversion and batch-amortised pattern or die cost.
Process comparisons need an engineering review: a different process may require a different
geometry, material grade, stock shape or secondary operation.

## Manufacturability screening

`config/dfm_thresholds.yaml` controls wall, radius, pocket, drilling, tolerance,
bend-clearance, draft and finish checks. Defaults are heuristics for review with a
shop, not handbook-certified limits. The reference links explain the risks; they
do not validate every numerical default. A clean screening result is not a DFM approval.

PDF exports include cost, findings, assumptions, geometry and a rate/threshold snapshot.
They use INR text so the currency renders with standard PDF fonts.

## Workflow

The worksheet opens with **Common part presets**. Choose a part, change its basic
dimensions, material and batch quantity. Geometry, DFM screening, should-cost and
exports update when you press Enter or leave a field. Invalid geometry clears the
estimate and downloads until corrected. The schematic follows the current dimensions;
it is a plan/section aid, not a production drawing or generated CAD model.

The 13 templates cover spacers/bushes, plain and stepped shafts, machined rings,
drilled circular flanges, four-hole mounting plates, solid and pocketed blocks,
flat panels, L-brackets, U-channels, sand-cast housings and die-cast trays.
These are common engineering shapes, with no claim about market popularity or
compliance with a particular dimensional standard. Standard stamped washers should
be priced from a catalogue rather than treated as custom turned rings.

Volume, exposed area, stock envelope, holes, pocket features and bend count are
derived from the preset dimensions. **Finish and costing assumptions** exposes
secondary operations, tolerance, finish, overhead and markup. Bent-sheet presets
use outside leg dimensions, 90-degree bends and an editable K-factor to calculate
the developed blank using [bend deduction](https://help.solidworks.com/2022/english/SolidWorks/sldworks/c_Bend_Allowance_and_Bend_Deduction.htm).
Calibrate it to the material and tooling. Cast templates omit draft and fillets
from nominal geometry; post-machining, ribs, bosses and other excluded features
are stated in each template. PDF and audit JSON record the template version,
input dimensions and assumptions alongside the derived geometry.

For a different shape or a STEP file, choose **Custom / STEP**.
Choose a starting example, process and material, edit the part form, then calculate.
Inspect the cost table, DFM findings and batch-size chart. PDF, cost CSV and audit JSON
downloads refer to the last submitted snapshot. Form edits need a new calculation.
Changing example, process or material clears the previous estimate.
An alternative material/process table compares the same submitted envelope and volume.
Unsupported material, geometry and finishing combinations show a validation message.

## STEP import

In **Custom / STEP**, open **Import a STEP solid**, choose a `.step` or `.stp` file, then click
**Read and fill geometry**. Review the filled fields and calculate the estimate.
`examples/step_block.step` is a generated 100 x 60 x 20 mm solid for trying the importer.

The Open CASCADE reader measures a single closed solid's global XYZ bounding box,
volume and surface area, converting declared file units to mm. Volume and area are
converted to cm3 and cm2. Files without declared length units are rejected. The original
filename, SHA-256, unit names and measurements appear in
the audit JSON and PDF; manual overrides remain visible as the submitted part inputs.
Re-reading a file fills the geometry again. Replacing or removing it clears the old result.

Milling and casting use X/Y/Z as length/width/height. Turning requires a spindle axis:
length follows that axis and the initial diameter is the transverse bounding-box
diagonal, a conservative envelope. Review and replace it with the actual stock diameter.
Sheet metal requires confirmation that the STEP represents a developed flat blank,
with thickness along Z. The importer does not unfold folded parts.

Holes, minimum walls, corner radii, draft, tolerances, finish, and secondary operations
remain manual. Assemblies, multiple solids, open surfaces and non-Part-21 formats are
rejected. Files are limited to 20 MiB, bounds to 0.01 through 10,000 mm, and reading to
30 seconds in a separate process. Rotation relative to the global axes can enlarge the
box. Uploaded bytes stay in the app session; parser temporary files are removed afterward.
Processing uses the app server, without an external CAD service. Process isolation
limits parser hangs/crashes; it is not an OS security sandbox.

## Indian material budget rates

| Material | INR/kg used | Listing basis |
|---|---:|---|
| Aluminium 6061 | 400 | [Sachin Steel Centre](https://www.sachinsteelcentre.in/aluminium-plate-and-sheet.html), 399/kg plate, rounded |
| Mild steel | 65 | [Ganpati Steel](https://www.ganpatisteel.com/ms-plate.html), plate |
| Stainless 304 | 245 | [Narendra Metal](https://www.narendrametalindia.com/stainless-steel-plate.html), plate |
| Brass | 600 | [Sona Metals](https://sonametals.in/product/brass-round-rod/), 599/kg rod, rounded |
| Aluminium A356 | 405 | [Ocean Asiatic](https://www.oceanasiatic.co.in/aluminum-ingots.html), alloy ingot |
| Aluminium ADC12 | 240 | [Ocean Asiatic](https://www.oceanasiatic.co.in/aluminum-ingots.html), alloy ingot |

Lookup date is not the supplier's price-effective date: these listings are undated,
indicative and may be stale. GST and freight are not stated consistently; the model
treats these as pre-tax budget rates and excludes GST/freight. Confirm that basis when
buying. Plate prices are proxies for other stock forms, and listing minimum quantities
are recorded but not charged as a minimum purchase. Grade, temper, quantity and cut-size
premiums can change the actual price. Source details are stored per material and exported
with each report. Machine, tooling, setup and finishing charges still need local calibration.

## Check the calculations

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
```

Three illustrative parts in `examples/` have independent component calculations in
`examples/hand_calculations.csv`. Tests compare every component with these values.
The milling example uses 138 cm3 stock, 78 cm3 removal and a 5.68 minute cycle.
The turning example uses cylindrical stock of 36.1283155 cm3. The sheet example
uses a 12 cm3 blank, 75% nesting utilisation, 320 mm cut and two bends.
Vendor quote validation is pending. To calibrate this model, collect two or three shop
quotes for the same drawing revision, material, batch, tolerance and finish. Record the
quote date, location, tax basis and included operations. Compare the direct costs before
changing overhead or markup. No accuracy claim is made against real quotes.

## Command line

```powershell
.venv\Scripts\python -m core examples/milled_bracket.json --pdf output/bracket.pdf
.venv\Scripts\python -m core examples/milled_bracket.json --step examples/step_block.step
```

The command prints a JSON audit with the submitted geometry, costs, rates and thresholds.
Use `--rates path/to/rates.yaml` and `--thresholds path/to/thresholds.yaml` for alternate
cards. JSON input supports multiple hole groups, each with diameter, depth and count.
The worksheet currently accepts one group of identical holes.
For STEP turning use `--axis X`, `Y` or `Z`; for sheet metal add `--flat-blank` only
when the file is the developed blank. The JSON file still supplies process, grade,
quantity and all manufacturing features.

Rate-card validation rejects negative rates and invalid utilisation/yield fractions.
Mark a card `quoted` only after recording a real source and an ISO quote date.
GitHub Actions is configured to run lint and tests on Python 3.11 and 3.13 after pushing.
Local verification used Windows and Python 3.13; the remote workflow has not run yet.

## Before using an estimate for sourcing

Confirm the material budget prices and replace machine, finishing and tooling placeholders
with dated vendor data.
Review DFM thresholds with a machinist or foundry engineer. Confirm stock form, fixture
count, production yield and any post-machining that this simple model excludes. Casting
and machining estimates describe different process plans even when their envelopes match.

The app has no account system or database. STEP files are uploaded to the running app
server for processing. Estimates live in the current
Streamlit session; download the audit JSON if you need a permanent record. Generated
reports, the supplied planning brief and local development/design guides are ignored by
Git. The project README, source, configuration, examples and tests are tracked.

For Streamlit Community Cloud, use `app.py` as the entry point and `requirements.txt`
for dependencies. A GitHub remote and hosting account are needed to publish the app.

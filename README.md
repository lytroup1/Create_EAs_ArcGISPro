# Create EAs ArcGIS Pro Tool

This project generates candidate census Enumeration Areas from building points and dwelling counts. Candidate EAs are review proposals for a future official geography; the tool never overwrites official boundaries.

## Current implementation

The ArcGIS Pro Python toolbox reads building points, dwelling counts, administrative polygons, roads, and rivers. It builds a proximity graph, blocks major-road and river crossings, applies medium/minor road penalties, grows deterministic candidate EAs, and writes polygon and table outputs. Candidate polygons form a complete, non-overlapping partition of each administrative area. A raster cost allocation makes polygon boundaries prefer the supplied road network. Building count and dwelling count remain distinct dimensions, while dwelling count controls the EA thresholds.

The baseline treats each building as indivisible so all dwellings in a building remain with one enumerator. Administrative boundaries and hard barriers reject merges. Distance and shared-boundary values influence candidate selection. Every candidate outside the requested dwelling range receives a status or review note.

## Example output map

![Example candidate Enumeration Area output map showing residences, roads, and EA boundaries](docs/Screenshot%202026-08-31%20131735.png)

This annotated example shows residences as magenta symbols, candidate EA boundaries in yellow, minor roads in blue, and a major road in orange. Symbology is illustrative and can be configured in ArcGIS Pro.

## ArcGIS Pro toolbox

The final `.pyt` file is uploaded directly into ArcGIS Pro and runs inside the ArcGIS Pro Python environment. It imports the reusable logic from `src/create_eas`; there is no separate application connection or service. ArcPy is provided by ArcGIS Pro and is intentionally not listed as a pip dependency. Polygon partitioning requires the ArcGIS Spatial Analyst extension.

See the [Create EAs tool reference](docs/create_eas.md) for usage, parameters, output fields, environments, licensing, and a Python example.

Run tests from an ArcGIS Pro Python Command Prompt or another Python environment with the source directory available:

```text
set PYTHONPATH=src
python -m unittest discover -s tests -v
```

The current workspace has no Python interpreter on `PATH`, so tests must be run from an ArcGIS Pro Python Command Prompt or another environment that provides Python.

## Known limitations

The current baseline does not yet implement split/merge maintenance, full lineage, all optional QA fields, or a fully configurable barrier-class mapping. Polygon boundaries are raster-derived at the Boundary Alignment Resolution, which defaults to 5 meters. Smaller cells can improve road alignment but increase runtime and temporary storage. Resolution is reduced automatically within an administrative unit when buildings assigned to different candidate EAs would otherwise occupy the same source cell. These polygons remain review geometry rather than an official boundary replacement.

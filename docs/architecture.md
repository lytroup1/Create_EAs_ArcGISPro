# Architecture

The `.pyt` file is the ArcGIS Pro tool entry point and runs inside the ArcGIS Pro Python environment. It will be a thin toolbox layer around reusable processing modules. ArcPy will handle feature-class I/O, spatial validation, geometry construction, and geodatabase outputs. Pure Python records and algorithms will handle configuration validation, scoring, graph assignment, diagnostics, and unit tests.

Building points are the atomic assignment records. Each carries a dwelling count and is assigned to exactly one candidate EA. Administrative polygons are binding constraints. Roads and rivers become classified graph constraints or penalties after spatial preprocessing.

The authoritative relationship is the building-to-EA assignment table. Candidate polygons, summaries, effort metrics, and review reports are derived outputs.

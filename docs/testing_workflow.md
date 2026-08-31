# Testing Workflow

Milestone 1 uses pure Python `unittest` tests and a synthetic adjacency graph. It verifies threshold validation, hard-barrier rejection, administrative-boundary rejection, shared-boundary preference, target preference, threshold statuses, and repeatable candidate formation.

Run:

```text
set PYTHONPATH=src
python -m unittest discover -s tests -v
```

The disposable ArcGIS Pro integration test builds a synthetic geodatabase fixture and inspects assignment completeness, positive candidate geometry, summary agreement, exact administrative-area coverage, absence of polygon overlap, and containment of each assigned building by its matching candidate polygon.

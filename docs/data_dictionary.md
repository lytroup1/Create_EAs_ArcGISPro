# Data Dictionary

## Planned inputs

- **Buildings**: point feature layer with one point per building.
- **DwellingCount**: nonnegative number of dwelling units in the building.
- **Administrative boundaries**: nonoverlapping polygon features with a user-selected administrative ID field.
- **Roads**: optional features with a user-selected classification field containing major, medium, or minor categories.
- **Rivers**: optional hard-barrier features.

## Core records

- **BuildingID**: stable source or derived building identifier.
- **AdminID**: binding administrative identifier.
- **DwellingCount**: threshold workload carried by the building.
- **EAID**: candidate Enumeration Area identifier.
- **ThresholdStatus**: `UNDERSIZED`, `WITHIN_RANGE`, `OVERSIZED`, `REVIEW_REQUIRED`, or `INVALID`.
- **ReviewStatus**: candidate lifecycle state such as `PROPOSED` or `REVIEW_REQUIRED`.
- **ReviewNotes**: explainable exceptions and ambiguity notes.

A permanent UnitID is not part of the current design. Any internal graph key is transient and does not replace BuildingID.

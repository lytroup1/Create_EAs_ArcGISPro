# Create Candidate EAs (PreEA)

## Summary

Creates candidate census Enumeration Areas (EAs) by grouping building points according to dwelling workload, proximity, administrative boundaries, roads, and rivers. The tool produces a complete, non-overlapping polygon partition of each administrative unit.

Candidate EAs are review proposals. The tool does not modify official EA boundaries or designate its output as an official geography.

## Example output

![Example candidate Enumeration Area output map showing residences, roads, and EA boundaries](Screenshot%202026-08-31%20131735.png)

The annotated map shows residences as magenta symbols, candidate EA boundaries in yellow, minor roads in blue, and a major road in orange. The image demonstrates one possible ArcGIS Pro map presentation; the tool creates the output datasets but does not prescribe this symbology.

## Usage

- The **Buildings** input must contain one point per building and a numeric dwelling-count field. Decimal dwelling values are rounded to the nearest integer. Null values are treated as zero; negative values are not valid.
- Building points must use a projected coordinate system with linear units. Output polygons use the building coordinate system. Administrative polygons are projected to that coordinate system during processing.
- The **Administrative ID Field** should contain a unique, nonempty identifier for each administrative unit. Administrative polygons should not overlap. Each administrative unit must receive at least one building; otherwise, a complete partition cannot be created.
- Buildings are assigned to administrative units using a closest spatial match. A building outside all administrative polygons can therefore be associated with the nearest polygon.
- The tool evaluates up to 12 neighboring buildings within the **Initial Building Clustering Distance**. A larger distance can connect dispersed buildings but can also increase processing time and allow less compact candidates.
- Candidate growth is deterministic. Repeating a run with the same inputs and parameters produces the same building assignments.
- The minimum, target, and maximum values describe dwelling workload. The target guides candidate growth. A candidate cannot accept a merge that would exceed the maximum, although a single indivisible building can itself exceed the maximum and will be flagged for review.
- Scoring weights are normalized before use, so their relative proportions matter rather than their absolute values. For example, `2, 1, 1` has the same effect as `0.5, 0.25, 0.25`.
- Rivers are hard grouping barriers. Building connections that cross a river are rejected.
- Major roads are hard grouping barriers. Medium and minor roads add distance penalties to grouping. All supplied roads also increase raster traversal cost so polygon boundaries tend to follow the road network.
- Road classes are matched without regard to letter case. Recognized classes are shown in the [Road classification](#road-classification) section. Unrecognized or null classes are treated as minor for polygon allocation and do not add a grouping penalty.
- Roads influence boundaries but are not absolute polygon barriers. This allows the output polygons to cover the entire administrative area even when an EA must cross a road.
- **Boundary Alignment Resolution** is the preferred raster cell size used for boundary allocation. The default is 5 meters. Smaller values generally improve spatial detail but increase processing time and temporary storage.
- If buildings assigned to different EAs occupy the same source cell, the tool automatically halves the cell size until each source can be represented. Spatially coincident buildings assigned to different EAs cannot be partitioned and cause an error.
- Existing outputs with the selected prefix are deleted and replaced. The tool prevents an output from replacing one of its input datasets.
- Temporary datasets are written to the ArcGIS scratch geodatabase when one is available; otherwise, they are written to the output geodatabase and removed after processing.

## Parameters

| Dialog label | Python name | Explanation | Data type |
| --- | --- | --- | --- |
| Administrative Boundary | `administrative_boundary` | Polygon features defining the study area and administrative units. Every unit must receive at least one building. | Feature Layer |
| Administrative ID Field | `administrative_id_field` | Short, long, or text field that uniquely identifies each administrative unit. | Field |
| Buildings | `buildings` | Point features representing buildings to assign to candidate EAs. | Feature Layer |
| Dwelling Count Field | `dwelling_count_field` | Short, long, or double field containing the dwelling workload for each building. | Field |
| Roads (Optional) | `roads` | Polyline features used as grouping constraints and weighted influences on polygon boundaries. | Feature Layer |
| Road Classification Field (Optional) | `road_classification_field` | Short, long, or text field containing road classes. If omitted, all roads are treated as unclassified. | Field |
| Rivers (Optional) | `rivers` | Polyline features treated as hard barriers when grouping buildings. | Feature Layer |
| Minimum Dwellings per EA | `minimum_dwellings` | Preferred minimum workload. Candidates below this value receive an `UNDERSIZED` status. The default is `0`. | Long |
| Target Dwellings per EA | `target_dwellings` | Desired workload used to score candidate growth. The default is `100`. | Long |
| Maximum Dwellings per EA | `maximum_dwellings` | Preferred maximum workload. Merges above this value are rejected. An indivisible building above this value is retained and flagged. The default is `120`. | Long |
| Initial Building Clustering Distance | `clustering_distance` | Maximum neighbor search distance in meters. The default is `1000`. | Double |
| Boundary Alignment Resolution (Meters) | `boundary_cell_size` | Preferred allocation raster cell size in meters. The default is `5`. Smaller values can improve boundary detail at the cost of runtime and storage. | Double |
| Dwelling Balance Weight | `dwelling_weight` | Relative importance of matching the target dwelling workload. The default is `0.5`. | Double |
| Building Balance Weight | `building_weight` | Relative importance of balancing building counts. The default is `0.25`. | Double |
| Distance Weight | `distance_weight` | Relative importance of shorter building connections. The default is `0.25`. | Double |
| Output Geodatabase | `output_gdb` | Existing file geodatabase where all output datasets will be written. | Workspace |
| Output Name Prefix | `output_prefix` | Prefix used to construct output dataset names. The default is `CandidateEA`. Invalid geodatabase name characters are replaced. | String |
| Diagnostic Markdown File (Optional) | `diagnostic_file` | Markdown report containing run counts, thresholds, output paths, and candidate status details. | File |
| Candidate EA Polygons | `candidate_eas` | Derived candidate polygon feature class. | Feature Class |
| Building Assignments | `building_assignments` | Derived copy of the building points with assignment fields. | Feature Class |
| EA Summary | `ea_summary` | Derived table containing one record per candidate EA. | Table |

The threshold values must satisfy:

$$
0 \leq \text{minimum} \leq \text{target} \leq \text{maximum}
$$

All scoring weights must be nonnegative, and at least one weight must be greater than zero.

## Derived outputs

If the output prefix is `CandidateEA`, the following datasets are created:

| Output | Dataset name | Description |
| --- | --- | --- |
| Candidate EA Polygons | `CandidateEA_EAs` | Multipart polygon feature class forming a complete, non-overlapping partition of each administrative unit. |
| Building Assignments | `CandidateEA_Buildings` | Copy of the source building points with candidate assignment attributes. Original input fields are retained. |
| EA Summary | `CandidateEA_Summary` | Stand-alone table with workload and review information for each candidate EA. |

## Output fields

### Candidate EA Polygons

| Field | Type | Description |
| --- | --- | --- |
| `EAID` | Text | Run-specific candidate identifier such as `EA_00001`. |
| `AdminID` | Text | Administrative identifier inherited from the assigned buildings. |
| `DwellingCount` | Long | Total dwellings assigned to the candidate. |
| `BuildingCount` | Long | Number of buildings assigned to the candidate. |
| `TargetDwell` | Long | Target dwelling parameter used for the run. |
| `MinimumDwell` | Long | Minimum dwelling parameter used for the run. |
| `MaximumDwell` | Long | Maximum dwelling parameter used for the run. |
| `TargetDev` | Double | Signed difference between candidate dwellings and target dwellings. |
| `AbsTargetDev` | Double | Absolute difference from the target. |
| `PctTargetDev` | Double | Absolute target deviation as a percentage of the target. |
| `AreaSqKm` | Double | Geodesic candidate area in square kilometers. |
| `ThresholdStatus` | Text | `UNDERSIZED`, `WITHIN_RANGE`, or `OVERSIZED`. |
| `ReviewStatus` | Text | `PROPOSED` or `REVIEW_REQUIRED` in the current implementation. |
| `ReviewNotes` | Text | Explanation of a condition requiring review. |

### Building Assignments

The output retains the source building attributes and adds or updates these fields:

| Field | Type | Description |
| --- | --- | --- |
| `BuildingID` | Text | Generated building identifier based on the copied source object ID. |
| `EAID` | Text | Candidate EA assigned to the building. |
| `AdminID` | Text | Administrative unit assigned during spatial processing. |
| `DwellingCount` | Long | Rounded dwelling workload used by the tool. |
| `ReviewNotes` | Text | Building-level assignment note when applicable. |

### EA Summary

| Field | Type | Description |
| --- | --- | --- |
| `EAID` | Text | Candidate EA identifier. |
| `AdminID` | Text | Administrative identifier. |
| `BuildingCount` | Long | Number of assigned buildings. |
| `DwellingCount` | Long | Total assigned dwellings. |
| `ThresholdStatus` | Text | Candidate workload status. |
| `ReviewStatus` | Text | Candidate review status. |
| `ReviewNotes` | Text | Explanation of conditions requiring review. |

## Road classification

| Classification values | Grouping behavior | Boundary allocation cost |
| --- | --- | ---: |
| `major`, `motorway`, `trunk`, `primary` | Hard barrier; crossing merges are rejected. | 10,000 |
| `medium`, `secondary`, `tertiary` | Adds a 100-meter-equivalent grouping penalty. | 1,000 |
| `minor`, `residential`, `local` | Adds a 10-meter-equivalent grouping penalty. | 100 |
| Other, null, or unclassified | No grouping penalty. | 100 |

Nonroad raster cells have a cost of `1`. The allocation costs are relative impedance values, not distances or travel times.

## Environments

The tool manages the environments required by its internal geoprocessing operations.

| Environment | Behavior |
| --- | --- |
| Scratch Workspace | Honored through `arcpy.env.scratchGDB` for intermediate feature classes, tables, and rasters. |
| Output Coordinate System | Determined by the Buildings input. Administrative geometry is projected to this coordinate system. |
| Cell Size | Controlled by **Boundary Alignment Resolution**, with automatic reduction when source cells collide. A global Cell Size environment is not used for allocation. |
| Processing Extent | Set separately to each administrative unit during allocation. |
| Parallel Processing Factor | Set to `100%` during distance allocation. Actual core use is determined by Spatial Analyst and dataset size. |
| Overwrite Output | Existing tool outputs with the selected prefix are deleted and replaced regardless of this environment. Inputs are protected from output-name collisions. |

## Licensing information

| ArcGIS Pro license | Requirement |
| --- | --- |
| Basic | Spatial Analyst extension required |
| Standard | Spatial Analyst extension required |
| Advanced | Spatial Analyst extension required |

The tool must run in an ArcGIS Pro Python environment that provides ArcPy.

## Python syntax

After importing the Python toolbox, call the tool through its `preea` alias:

```python
arcpy.preea.CreateCandidateEAs(
    administrative_boundary,
    administrative_id_field,
    buildings,
    dwelling_count_field,
    roads,
    road_classification_field,
    rivers,
    minimum_dwellings,
    target_dwellings,
    maximum_dwellings,
    clustering_distance,
    boundary_cell_size,
    dwelling_weight,
    building_weight,
    distance_weight,
    output_gdb,
    output_prefix,
    diagnostic_file,
)
```

### Code sample

The following stand-alone example creates candidate EAs using roads and rivers:

```python
import arcpy

arcpy.ImportToolbox(r"C:\PreEA\toolbox\preea.pyt", "preea")

result = arcpy.preea.CreateCandidateEAs(
    r"C:\Data\Census.gdb\AdministrativeAreas",
    "AdminID",
    r"C:\Data\Census.gdb\Buildings",
    "Dwellings",
    r"C:\Data\Reference.gdb\Roads",
    "RoadClass",
    r"C:\Data\Reference.gdb\Rivers",
    80,
    100,
    120,
    1000,
    5,
    0.50,
    0.25,
    0.25,
    r"C:\Data\Results.gdb",
    "CandidateEA",
    r"C:\Data\candidate_ea_report.md",
)

candidate_eas = result.getOutput("candidate_eas")
building_assignments = result.getOutput("building_assignments")
ea_summary = result.getOutput("ea_summary")
```

## How the tool works

1. Copies the building points and assigns each point to an administrative unit.
2. Uses **Generate Near Table** to find up to 12 neighbors per building within the clustering distance.
3. Classifies neighbor connections that cross roads or rivers.
4. Grows candidate EAs from deterministic seeds using dwelling balance, building balance, and distance scores.
5. Converts assigned building points to collision-free integer source rasters.
6. Uses **Distance Allocation** with a road-weighted cost surface to partition each administrative unit.
7. Converts allocation zones to polygons and clips them to the exact administrative geometry.
8. Writes polygon, building-assignment, summary, and optional diagnostic outputs.

Building assignments are authoritative. Candidate polygons and summaries are derived from those assignments.

## Messages and common errors

The tool reports elapsed time for loading buildings, generating neighbors, building graph edges, growing candidates, writing outputs, and the complete run. It also reports the allocation cell resolution used for each administrative unit.

| Message or condition | Meaning and action |
| --- | --- |
| `Every administrative unit must contain at least one assigned building` | One or more administrative polygons did not receive a building. Review the building coverage and administrative IDs. |
| `Building points must use a projected coordinate system` | Project the Buildings input to an appropriate local projected coordinate system before running the tool. |
| `Source raster ... contains ... EA values; expected ...` | Candidate sources were not represented correctly in the raster. Review coincident points and use a smaller boundary resolution. |
| `Buildings assigned to different candidate EAs are spatially coincident` | Two coincident points belong to different candidates and cannot both seed a non-overlapping raster partition. Correct or consolidate the points. |
| `Creating complete road-influenced EA boundaries requires the ArcGIS Spatial Analyst extension` | Enable or license Spatial Analyst before running the tool. |
| `The selected output would overwrite an input dataset` | Change the output geodatabase or prefix so no generated output has the same path as an input. |
| `Scoring weights must be numeric` | Enter a number in each scoring weight field and refresh the toolbox if ArcGIS Pro is showing a cached parameter layout. |

## Limitations

- Outputs are candidate review geometry, not official EA boundaries.
- Buildings are indivisible; dwellings within one building cannot be assigned to different candidates.
- Polygon boundaries are raster-derived and may not coincide exactly with road centerlines or cadastral boundaries.
- Roads guide polygon allocation but do not prevent all crossings.
- Road-class terms and costs are fixed in the current implementation.
- Administrative units without assigned buildings cannot be represented.
- Split and merge maintenance, lineage tracking, and acceptance workflow are not implemented.
- Candidate identifiers are generated for each run and are not permanent identifiers.

## Related topics

- [Methodology](methodology.md)
- [Data dictionary](data_dictionary.md)
- [Testing workflow](testing_workflow.md)
- [Generate Near Table (ArcGIS Pro)](https://pro.arcgis.com/en/pro-app/latest/tool-reference/analysis/generate-near-table.htm)
- [Distance Allocation (ArcGIS Pro)](https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/distance-allocation.htm)
- [ArcGIS Pro geoprocessing tool reference](https://pro.arcgis.com/en/pro-app/latest/tool-reference/main/arcgis-pro-tool-reference.htm)
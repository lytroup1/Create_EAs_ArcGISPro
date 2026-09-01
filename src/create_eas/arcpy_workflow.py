"""ArcPy execution workflow for the Create EAs tool."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from math import sqrt
from time import perf_counter
import os

import arcpy

from .models import Building, Edge, EATargets, ScoreWeights
from .region_grow import grow_candidate_eas
from .scoring import threshold_status


OUTPUT_FIELDS = [
    ("EAID", "TEXT", 64),
    ("AdminID", "TEXT", 128),
    ("DwellingCount", "LONG", None),
    ("BuildingCount", "LONG", None),
    ("TargetDwell", "LONG", None),
    ("MinimumDwell", "LONG", None),
    ("MaximumDwell", "LONG", None),
    ("TargetDev", "DOUBLE", None),
    ("AbsTargetDev", "DOUBLE", None),
    ("PctTargetDev", "DOUBLE", None),
    ("AreaSqKm", "DOUBLE", None),
    ("ThresholdStatus", "TEXT", 32),
    ("ReviewStatus", "TEXT", 32),
    ("ReviewNotes", "TEXT", 512),
]

WORKFLOW_REVISION = "2026-08-27-road-alignment-5m"


def run_candidate_eas(
    *,
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
    diagnostic_file=None,
    messages=None,
):
    """Read ArcGIS layers, form candidate EAs, and write review outputs."""
    log = messages or _ArcPyMessages()
    targets = EATargets(minimum_dwellings, target_dwellings, maximum_dwellings)
    weights = ScoreWeights(dwelling_weight, building_weight, distance_weight)
    targets.validate()
    weights.validate()
    if clustering_distance <= 0:
        raise ValueError("Initial building clustering distance must be greater than zero.")
    if boundary_cell_size <= 0:
        raise ValueError("Boundary alignment resolution must be greater than zero.")

    output_gdb = os.path.abspath(output_gdb)
    if not arcpy.Exists(output_gdb):
        raise ValueError("The output geodatabase does not exist.")
    _validate_output_collisions(
        output_gdb,
        output_prefix,
        [administrative_boundary, buildings, roads, rivers],
    )
    scratch = arcpy.env.scratchGDB or output_gdb
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    workflow_started = perf_counter()
    temp_names = []
    try:
        log.message("Reading and assigning buildings to administrative areas...")
        stage_started = perf_counter()
        prepared_buildings = _prepare_buildings(buildings, scratch, run_id)
        joined = _spatially_assign_admins(prepared_buildings, administrative_boundary, scratch, run_id)
        temp_names.extend([prepared_buildings, joined])
        building_records, oid_map = _read_buildings(joined, dwelling_count_field, administrative_id_field)
        if not building_records:
            raise ValueError("The buildings input contains no usable point features.")
        log.message(
            f"Loaded {len(building_records):,} building points in "
            f"{perf_counter() - stage_started:.1f} seconds."
        )

        log.message("Building a proximity graph...")
        stage_started = perf_counter()
        near_table = os.path.join(scratch, f"createEAs_near_{run_id}")
        distance_method = (
            "GEODESIC"
            if arcpy.Describe(joined).spatialReference.type == "Geographic"
            else "PLANAR"
        )
        arcpy.analysis.GenerateNearTable(
            joined,
            joined,
            near_table,
            f"{clustering_distance} Meters",
            "NO_LOCATION",
            "NO_ANGLE",
            "ALL",
            12,
            distance_method,
            "Meters",
        )
        temp_names.append(near_table)
        near_count = int(arcpy.management.GetCount(near_table)[0])
        log.message(
            f"Generated {near_count:,} directed neighbor records "
            f"(maximum 12 per building) in {perf_counter() - stage_started:.1f} seconds."
        )
        stage_started = perf_counter()
        edges = _read_edges(
            near_table,
            oid_map,
            roads,
            road_classification_field,
            rivers,
            scratch,
            run_id,
            arcpy.Describe(joined).spatialReference,
        )
        log.message(
            f"Built {len(edges):,} candidate neighbor edges in "
            f"{perf_counter() - stage_started:.1f} seconds."
        )

        log.message("Growing contiguous candidate EAs...")
        stage_started = perf_counter()
        candidates, decisions = grow_candidate_eas(
            building_records,
            edges,
            targets,
            weights,
        )
        log.message(
            f"Formed {len(candidates):,} candidate EA assignments in "
            f"{perf_counter() - stage_started:.1f} seconds."
        )
        membership = {
            building_id: candidate.ea_id
            for candidate in candidates
            for building_id in candidate.building_ids
        }
        if set(membership) != {building.building_id for building in building_records}:
            raise RuntimeError("Candidate EA generation did not assign every building exactly once.")

        log.message("Writing building assignments and candidate EA polygons...")
        stage_started = perf_counter()
        output_paths = _write_outputs(
            output_gdb,
            output_prefix,
            administrative_boundary,
            administrative_id_field,
            prepared_buildings,
            building_records,
            membership,
            candidates,
            targets,
            run_id,
            boundary_cell_size,
            roads,
            road_classification_field,
            scratch,
        )
        log.message(f"Wrote candidate outputs in {perf_counter() - stage_started:.1f} seconds.")
        _write_report(
            diagnostic_file,
            run_id,
            len(building_records),
            candidates,
            decisions,
            targets,
            output_paths,
        )
        log.message(
            f"Created {len(candidates):,} candidate EAs in "
            f"{perf_counter() - workflow_started:.1f} seconds total."
        )
        return output_paths
    finally:
        for temporary in temp_names:
            if arcpy.Exists(temporary):
                arcpy.management.Delete(temporary)


def _prepare_buildings(buildings, scratch, run_id):
    output = os.path.join(scratch, f"createEAs_source_{run_id}")
    arcpy.management.CopyFeatures(buildings, output)
    arcpy.management.AddField(output, "CreateEAsOID", "LONG")
    with arcpy.da.UpdateCursor(output, ["OID@", "CreateEAsOID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    return output


def _spatially_assign_admins(buildings, administrative_boundary, scratch, run_id):
    output = os.path.join(scratch, f"createEAs_admin_{run_id}")
    arcpy.analysis.SpatialJoin(
        buildings,
        administrative_boundary,
        output,
        "JOIN_ONE_TO_ONE",
        "KEEP_ALL",
        "",
        "CLOSEST",
    )
    return output


def _validate_output_collisions(output_gdb, prefix, inputs):
    safe_prefix = arcpy.ValidateTableName(prefix, output_gdb)
    output_paths = {
        os.path.normcase(os.path.abspath(os.path.join(output_gdb, name)))
        for name in (
            f"{safe_prefix}_Buildings",
            f"{safe_prefix}_EAs",
            f"{safe_prefix}_Summary",
        )
    }
    for dataset in inputs:
        if not dataset:
            continue
        input_path = os.path.normcase(os.path.abspath(arcpy.Describe(dataset).catalogPath))
        if input_path in output_paths:
            raise ValueError("The selected output would overwrite an input dataset.")


def _read_buildings(joined, dwelling_field, administrative_id_field):
    fields = {field.name.lower(): field.name for field in arcpy.ListFields(joined)}
    dwelling_name = fields.get(dwelling_field.lower())
    admin_name = fields.get(administrative_id_field.lower())
    if dwelling_name is None:
        raise ValueError(f"Dwelling count field '{dwelling_field}' was not preserved by Spatial Join.")
    if admin_name is None:
        raise ValueError(f"Administrative ID field '{administrative_id_field}' was not preserved by Spatial Join.")
    join_count = fields.get("join_count")
    target_fid = fields.get("target_fid")
    source_id = fields.get("createeasoid")
    records = []
    oid_map = {}
    cursor_fields = ["OID@", "SHAPE@XY", dwelling_name, admin_name]
    if source_id:
        cursor_fields.append(source_id)
    if target_fid:
        cursor_fields.append(target_fid)
    if join_count:
        cursor_fields.append(join_count)
    with arcpy.da.SearchCursor(joined, cursor_fields) as cursor:
        for row in cursor:
            object_id, xy, dwellings, admin_id = row[:4]
            offset = 4
            source_oid = row[offset] if source_id else None
            offset += 1 if source_id else 0
            if source_oid is None:
                source_oid = row[offset] if target_fid else object_id
            offset += 1 if target_fid else 0
            match_count_index = offset
            match_count = row[match_count_index] if join_count else 1
            if xy is None:
                continue
            note = ""
            if admin_id is None or (isinstance(admin_id, str) and not admin_id.strip()):
                admin_id = "UNASSIGNED"
                note = "Building did not intersect an administrative polygon."
            elif match_count and match_count > 1:
                note = "Building intersects multiple administrative polygons; first match retained."
            try:
                dwelling_value = int(round(float(dwellings or 0)))
            except (TypeError, ValueError) as error:
                raise ValueError(f"Building OID {object_id} has a nonnumeric dwelling count.") from error
            building_id = f"B_{source_oid:09d}"
            records.append(Building(building_id, str(admin_id), dwelling_value, xy[0], xy[1]))
            oid_map[object_id] = (building_id, str(admin_id), note, xy)
    return records, oid_map


def _read_edges(near_table, oid_map, roads, road_classification_field, rivers, scratch, run_id, spatial_reference):
    pairs = {}
    with arcpy.da.SearchCursor(near_table, ["IN_FID", "NEAR_FID", "NEAR_DIST"]) as cursor:
        for from_oid, to_oid, distance in cursor:
            if from_oid == to_oid or from_oid not in oid_map or to_oid not in oid_map:
                continue
            key = tuple(sorted((from_oid, to_oid)))
            if key not in pairs or distance < pairs[key]:
                pairs[key] = distance
    edge_fc = os.path.join(scratch, f"createEAs_edges_{run_id}")
    arcpy.management.CreateFeatureclass(scratch, os.path.basename(edge_fc), "POLYLINE", spatial_reference=spatial_reference)
    arcpy.management.AddField(edge_fc, "EDGE_KEY", "TEXT", field_length=64)
    arcpy.management.AddField(edge_fc, "DIST_M", "DOUBLE")
    points = {oid: data[3] for oid, data in oid_map.items()}
    with arcpy.da.InsertCursor(edge_fc, ["SHAPE@", "EDGE_KEY", "DIST_M"]) as cursor:
        for (from_oid, to_oid), distance in pairs.items():
            first = points.get(from_oid)
            second = points.get(to_oid)
            if not first or not second:
                continue
            line = arcpy.Polyline(arcpy.Array([arcpy.Point(*first), arcpy.Point(*second)]), spatial_reference)
            cursor.insertRow([line, f"{from_oid}:{to_oid}", distance])
    river_edges = _intersecting_edges(edge_fc, rivers, None) if rivers else set()
    if rivers:
        arcpy.AddMessage(f"Found {len(river_edges):,} neighbor edges crossing rivers.")
    road_classes = {}
    if roads and road_classification_field:
        road_classes = _intersecting_edges(edge_fc, roads, road_classification_field)
        arcpy.AddMessage(f"Found {len(road_classes):,} neighbor edges crossing classified roads.")
    elif roads:
        unclassified_crossings = _intersecting_edges(edge_fc, roads, None)
        road_classes = {key: "unclassified" for key in unclassified_crossings}
        arcpy.AddMessage(f"Found {len(road_classes):,} neighbor edges crossing unclassified roads.")
    edges = []
    for (from_oid, to_oid), distance in pairs.items():
        if from_oid not in oid_map or to_oid not in oid_map:
            continue
        key = f"{from_oid}:{to_oid}"
        road_class = str(road_classes.get(key, "unclassified" if roads else "")).lower()
        edges.append(
            Edge(
                oid_map[from_oid][0],
                oid_map[to_oid][0],
                0.0,
                float(distance) + _road_penalty(road_class),
                key in river_edges or road_class in {"major", "motorway", "trunk", "primary"},
            )
        )
    arcpy.management.Delete(edge_fc)
    return edges


def _intersecting_edges(edge_fc, barrier_fc, class_field):
    barrier_fields = ["SHAPE@"]
    if class_field:
        barrier_fields.append(class_field)
    barriers = []
    with arcpy.da.SearchCursor(barrier_fc, barrier_fields) as cursor:
        for row in cursor:
            if row[0] is not None:
                barriers.append((row[0], row[1] if class_field else True))
    if not barriers:
        return {} if class_field else set()
    grid, origin_x, origin_y, cell_size = _build_barrier_grid(barriers)
    result = {}
    with arcpy.da.SearchCursor(edge_fc, ["EDGE_KEY", "SHAPE@"]) as cursor:
        for edge_key, edge_geometry in cursor:
            candidate_indexes = _grid_candidates(
                edge_geometry.extent, grid, origin_x, origin_y, cell_size
            )
            for barrier_index in candidate_indexes:
                barrier_geometry, barrier_class = barriers[barrier_index]
                if edge_geometry.disjoint(barrier_geometry):
                    continue
                if class_field:
                    previous = result.get(edge_key)
                    if previous is None or _road_severity(barrier_class) > _road_severity(previous):
                        result[edge_key] = barrier_class
                else:
                    result[edge_key] = True
                    break
    return result if class_field else set(result)


def _build_barrier_grid(barriers):
    x_min = min(item[0].extent.XMin for item in barriers)
    y_min = min(item[0].extent.YMin for item in barriers)
    x_max = max(item[0].extent.XMax for item in barriers)
    y_max = max(item[0].extent.YMax for item in barriers)
    span = max(x_max - x_min, y_max - y_min, 1.0)
    cell_size = span / max(sqrt(len(barriers)), 1.0)
    grid = defaultdict(set)
    for index, (geometry, _) in enumerate(barriers):
        for cell in _extent_cells(geometry.extent, x_min, y_min, cell_size):
            grid[cell].add(index)
    return grid, x_min, y_min, cell_size


def _grid_candidates(extent, grid, origin_x, origin_y, cell_size):
    candidates = set()
    for cell in _extent_cells(extent, origin_x, origin_y, cell_size):
        candidates.update(grid.get(cell, ()))
    return candidates


def _extent_cells(extent, origin_x, origin_y, cell_size):
    first_x = int((extent.XMin - origin_x) // cell_size)
    last_x = int((extent.XMax - origin_x) // cell_size)
    first_y = int((extent.YMin - origin_y) // cell_size)
    last_y = int((extent.YMax - origin_y) // cell_size)
    for x_index in range(first_x, last_x + 1):
        for y_index in range(first_y, last_y + 1):
            yield x_index, y_index


def _road_penalty(road_class):
    if road_class in {"medium", "secondary", "tertiary"}:
        return 100.0
    if road_class in {"minor", "residential", "local"}:
        return 10.0
    return 0.0


def _road_severity(road_class):
    value = str(road_class or "").lower()
    if value in {"major", "motorway", "trunk", "primary"}:
        return 3
    if value in {"medium", "secondary", "tertiary"}:
        return 2
    return 1


def _write_outputs(output_gdb, prefix, administrative_boundary, administrative_id_field, buildings, building_records, membership, candidates, targets, run_id, boundary_cell_size, roads, road_classification_field, scratch):
    safe_prefix = arcpy.ValidateTableName(prefix, output_gdb)
    assignments = os.path.join(output_gdb, f"{safe_prefix}_Buildings")
    ea_polygons = os.path.join(output_gdb, f"{safe_prefix}_EAs")
    summary = os.path.join(output_gdb, f"{safe_prefix}_Summary")
    for output in (assignments, ea_polygons, summary):
        if arcpy.Exists(output):
            arcpy.management.Delete(output)

    arcpy.AddMessage("Copying building assignments...")
    arcpy.management.CopyFeatures(buildings, assignments)
    arcpy.AddMessage("Adding building assignment fields...")
    assignment_field_names = {field.name.lower() for field in arcpy.ListFields(assignments)}
    for field_name, field_type, field_length in (("BuildingID", "TEXT", 64), ("EAID", "TEXT", 64), ("AdminID", "TEXT", 128), ("DwellingCount", "LONG", None), ("ReviewNotes", "TEXT", 512), ("EAValue", "LONG", None)):
        if field_name.lower() not in assignment_field_names:
            kwargs = {"field_length": field_length} if field_length else {}
            arcpy.management.AddField(assignments, field_name, field_type, **kwargs)
            assignment_field_names.add(field_name.lower())
    building_by_id = {record.building_id: record for record in building_records}
    ea_value_by_id = {candidate.ea_id: index for index, candidate in enumerate(candidates, 1)}
    arcpy.AddMessage("Writing building-to-EA membership...")
    with arcpy.da.UpdateCursor(assignments, ["CreateEAsOID", "BuildingID", "EAID", "AdminID", "DwellingCount", "ReviewNotes", "EAValue"]) as cursor:
        for row in cursor:
            building_id = row[1] or f"B_{row[0]:09d}"
            record = building_by_id.get(building_id)
            if record is None:
                record = building_by_id.get(f"B_{row[0]:09d}")
            if record is None:
                continue
            row[1] = record.building_id
            row[2] = membership[record.building_id]
            row[3] = record.admin_id
            row[4] = record.dwelling_count
            row[5] = ""
            row[6] = ea_value_by_id[row[2]]
            cursor.updateRow(row)
    arcpy.AddMessage("Building assignments written.")

    arcpy.AddMessage("Constructing candidate EA review polygons...")
    spatial_reference = arcpy.Describe(assignments).spatialReference
    if spatial_reference.type != "Projected" or not spatial_reference.metersPerUnit:
        raise ValueError(
            "Building points must use a projected coordinate system with linear units for polygon generation."
        )
    admin_geometries = {}
    with arcpy.da.SearchCursor(administrative_boundary, [administrative_id_field, "SHAPE@"]) as cursor:
        for admin_id, geometry in cursor:
            key = str(admin_id)
            projected = geometry.projectAs(spatial_reference)
            admin_geometries[key] = (
                projected if key not in admin_geometries else admin_geometries[key].union(projected)
            )
    arcpy.AddMessage(f"Loaded {len(admin_geometries):,} administrative clipping geometries.")
    partition_geometries = _create_partition_geometries(
        assignments,
        candidates,
        ea_value_by_id,
        admin_geometries,
        roads,
        road_classification_field,
        boundary_cell_size,
        spatial_reference,
        scratch,
        run_id,
    )
    arcpy.management.DeleteField(assignments, "EAValue")
    arcpy.management.CreateFeatureclass(
        output_gdb,
        os.path.basename(ea_polygons),
        "POLYGON",
        spatial_reference=spatial_reference,
    )
    arcpy.management.AddField(ea_polygons, "EAID", "TEXT", field_length=64)
    arcpy.AddMessage("Candidate EA polygon feature class created.")
    with arcpy.da.InsertCursor(ea_polygons, ["SHAPE@", "EAID"]) as cursor:
        for candidate in candidates:
            cursor.insertRow([partition_geometries[candidate.ea_id], candidate.ea_id])
    for field_name, field_type, field_length in OUTPUT_FIELDS[1:]:
        if field_name.lower() not in {field.name.lower() for field in arcpy.ListFields(ea_polygons)}:
            kwargs = {"field_length": field_length} if field_length else {}
            arcpy.management.AddField(ea_polygons, field_name, field_type, **kwargs)
    candidate_by_id = {candidate.ea_id: candidate for candidate in candidates}
    with arcpy.da.UpdateCursor(ea_polygons, [field[0] for field in OUTPUT_FIELDS] + ["SHAPE@"]) as cursor:
        for row in cursor:
            candidate = candidate_by_id.get(row[0])
            if candidate is None:
                continue
            row[1] = candidate.admin_id
            row[2] = candidate.dwelling_count
            row[3] = candidate.building_count
            row[4:7] = [targets.target_dwellings, targets.minimum_dwellings, targets.maximum_dwellings]
            deviation = candidate.dwelling_count - targets.target_dwellings
            row[7:10] = [deviation, abs(deviation), 100.0 * abs(deviation) / targets.target_dwellings]
            row[10] = row[14].getArea("GEODESIC", "SQUAREKILOMETERS")
            row[11] = candidate.threshold_status.value
            row[12] = candidate.review_status.value
            row[13] = "; ".join(candidate.review_notes)
            cursor.updateRow(row)

    arcpy.AddMessage(
        "Candidate polygons form a non-overlapping partition of each administrative area; "
        "roads influence allocation boundaries where supplied."
    )

    arcpy.AddMessage("Writing candidate EA summary...")
    arcpy.management.CreateTable(output_gdb, os.path.basename(summary))
    for field_name, field_type, field_length in (("EAID", "TEXT", 64), ("AdminID", "TEXT", 128), ("BuildingCount", "LONG", None), ("DwellingCount", "LONG", None), ("ThresholdStatus", "TEXT", 32), ("ReviewStatus", "TEXT", 32), ("ReviewNotes", "TEXT", 512)):
        kwargs = {"field_length": field_length} if field_length else {}
        arcpy.management.AddField(summary, field_name, field_type, **kwargs)
    with arcpy.da.InsertCursor(summary, ["EAID", "AdminID", "BuildingCount", "DwellingCount", "ThresholdStatus", "ReviewStatus", "ReviewNotes"]) as cursor:
        for candidate in candidates:
            cursor.insertRow([candidate.ea_id, candidate.admin_id, candidate.building_count, candidate.dwelling_count, candidate.threshold_status.value, candidate.review_status.value, "; ".join(candidate.review_notes)])
    return {"ea_polygons": ea_polygons, "building_assignments": assignments, "summary": summary}


def _create_partition_geometries(assignments, candidates, ea_value_by_id, admin_geometries, roads, road_classification_field, boundary_cell_size, spatial_reference, scratch, run_id):
    extension_status = arcpy.CheckExtension("Spatial")
    if extension_status not in {"Available", "CheckedOut"}:
        raise RuntimeError(
            "Creating complete road-influenced EA boundaries requires the ArcGIS Spatial Analyst extension."
        )
    candidates_by_admin = defaultdict(list)
    for candidate in candidates:
        candidates_by_admin[candidate.admin_id].append(candidate)
    missing_admins = sorted(set(admin_geometries) - set(candidates_by_admin))
    if missing_admins:
        raise ValueError(
            "Every administrative unit must contain at least one assigned building to create a complete "
            f"EA partition. Units without buildings: {', '.join(missing_admins[:10])}"
        )

    preferred_cell_size_meters = boundary_cell_size
    preferred_cell_size = preferred_cell_size_meters / spatial_reference.metersPerUnit
    road_cost_features = None
    assignment_layer = None
    temporary_paths = []
    partition_geometries = {}
    extension_checked_out_here = extension_status == "Available"
    if extension_checked_out_here:
        arcpy.CheckOutExtension("Spatial")
    try:
        if roads:
            road_cost_features = os.path.join(scratch, f"createEAs_road_cost_{run_id}")
            arcpy.management.CopyFeatures(roads, road_cost_features)
            temporary_paths.append(road_cost_features)
            arcpy.management.AddField(road_cost_features, "CreateEAsCost", "LONG")
            fields = {field.name.lower(): field.name for field in arcpy.ListFields(road_cost_features)}
            class_name = fields.get((road_classification_field or "").lower())
            cursor_fields = ["CreateEAsCost"] + ([class_name] if class_name else [])
            with arcpy.da.UpdateCursor(road_cost_features, cursor_fields) as cursor:
                for row in cursor:
                    row[0] = _boundary_road_cost(row[1] if class_name else None)
                    cursor.updateRow(row)

        value_to_ea = {value: ea_id for ea_id, value in ea_value_by_id.items()}
        assignment_layer = f"createEAs_assignment_layer_{run_id}"
        arcpy.management.MakeFeatureLayer(assignments, assignment_layer)
        for admin_index, (admin_id, admin_geometry) in enumerate(admin_geometries.items(), 1):
            admin_token = f"{run_id}_{admin_index}"
            admin_fc = os.path.join(scratch, f"createEAs_admin_clip_{admin_token}")
            allocation_raster = os.path.join(scratch, f"createEAs_allocation_{admin_token}")
            source_raster = os.path.join(scratch, f"createEAs_sources_{admin_token}")
            allocation_polygons = os.path.join(scratch, f"createEAs_zones_{admin_token}")
            clipped_polygons = os.path.join(scratch, f"createEAs_clipped_{admin_token}")
            admin_temporaries = [admin_fc, source_raster, allocation_raster, allocation_polygons, clipped_polygons]
            temporary_paths.extend(admin_temporaries)
            arcpy.management.CopyFeatures([admin_geometry], admin_fc)
            admin_field = arcpy.AddFieldDelimiters(assignments, "AdminID")
            escaped_admin_id = admin_id.replace("'", "''")
            arcpy.management.SelectLayerByAttribute(
                assignment_layer,
                "NEW_SELECTION",
                f"{admin_field} = '{escaped_admin_id}'",
            )
            cell_size = _collision_free_cell_size(
                assignment_layer,
                admin_geometry.extent,
                preferred_cell_size,
            )
            cell_size_meters = cell_size * spatial_reference.metersPerUnit
            arcpy.AddMessage(
                f"Allocating {admin_id} EA boundaries at {cell_size_meters:g}-meter cell resolution."
            )
            cost_surface = None
            road_raster = None
            with arcpy.EnvManager(
                extent=admin_geometry.extent,
                cellSize=cell_size,
                outputCoordinateSystem=spatial_reference,
                parallelProcessingFactor="100%",
            ):
                arcpy.conversion.PointToRaster(
                    assignment_layer,
                    "EAValue",
                    source_raster,
                    "MOST_FREQUENT",
                    None,
                    cell_size,
                )
                source_zone_count = int(arcpy.management.GetCount(source_raster)[0])
                expected_zone_count = len(candidates_by_admin[admin_id])
                if source_zone_count != expected_zone_count:
                    raise RuntimeError(
                        f"Source raster for administrative unit {admin_id} contains "
                        f"{source_zone_count:,} EA values; expected {expected_zone_count:,}."
                    )
                if road_cost_features:
                    road_raster = os.path.join(scratch, f"createEAs_roads_{admin_token}")
                    temporary_paths.append(road_raster)
                    arcpy.conversion.PolylineToRaster(
                        road_cost_features,
                        "CreateEAsCost",
                        road_raster,
                        "MAXIMUM_LENGTH",
                        "CreateEAsCost",
                        cell_size,
                    )
                    cost_surface = arcpy.sa.Con(
                        arcpy.sa.IsNull(arcpy.Raster(road_raster)),
                        1,
                        arcpy.Raster(road_raster),
                    )
                allocation = arcpy.sa.DistanceAllocation(
                    in_source_data=source_raster,
                    in_cost_raster=cost_surface,
                    distance_method="PLANAR",
                    source_field="Value",
                )
                allocation.save(allocation_raster)
                arcpy.conversion.RasterToPolygon(
                    allocation_raster,
                    allocation_polygons,
                    "SIMPLIFY",
                    "Value",
                    "MULTIPLE_OUTER_PART",
                )
            arcpy.analysis.PairwiseClip(allocation_polygons, admin_fc, clipped_polygons)
            fields = {field.name.lower(): field.name for field in arcpy.ListFields(clipped_polygons)}
            zone_value_field = next(
                (fields[name] for name in ("gridcode", "grid_code", "value") if name in fields),
                None,
            )
            if zone_value_field is None:
                raise RuntimeError("Allocated EA polygons do not contain a raster zone value field.")
            with arcpy.da.SearchCursor(clipped_polygons, [zone_value_field, "SHAPE@"]) as cursor:
                for grid_code, geometry in cursor:
                    ea_id = value_to_ea[int(grid_code)]
                    partition_geometries[ea_id] = (
                        geometry
                        if ea_id not in partition_geometries
                        else partition_geometries[ea_id].union(geometry)
                    )
    finally:
        if assignment_layer and arcpy.Exists(assignment_layer):
            arcpy.management.Delete(assignment_layer)
        for temporary in temporary_paths:
            if arcpy.Exists(temporary):
                arcpy.management.Delete(temporary)
        if extension_checked_out_here:
            arcpy.CheckInExtension("Spatial")

    missing_candidates = sorted(set(ea_value_by_id) - set(partition_geometries))
    if missing_candidates:
        raise RuntimeError(
            "Boundary allocation did not produce polygons for candidate EAs: "
            + ", ".join(missing_candidates[:10])
        )
    return partition_geometries


def _collision_free_cell_size(assignment_layer, extent, preferred_cell_size):
    cell_size = preferred_cell_size
    while True:
        occupied_cells = {}
        collision = False
        with arcpy.da.SearchCursor(assignment_layer, ["SHAPE@XY", "EAValue"]) as cursor:
            for xy, ea_value in cursor:
                cell = (
                    int((xy[0] - extent.XMin) // cell_size),
                    int((xy[1] - extent.YMin) // cell_size),
                )
                existing_value = occupied_cells.setdefault(cell, ea_value)
                if existing_value != ea_value:
                    collision = True
                    break
        if not collision:
            return cell_size
        cell_size /= 2.0
        if cell_size < 0.01:
            raise RuntimeError(
                "Buildings assigned to different candidate EAs are spatially coincident; "
                "a non-overlapping polygon partition cannot contain both assignments."
            )


def _boundary_road_cost(road_class):
    severity = _road_severity(road_class)
    if severity == 3:
        return 10000
    if severity == 2:
        return 1000
    return 100


def _write_report(path, run_id, building_count, candidates, decisions, targets, output_paths):
    if not path:
        return
    lines = [
        "# Candidate EA Processing Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Buildings assigned: {building_count}",
        f"- Candidate EAs: {len(candidates)}",
        f"- Accepted/rejected merge evaluations: {len(decisions)}",
        f"- Dwelling thresholds: {targets.minimum_dwellings} / {targets.target_dwellings} / {targets.maximum_dwellings}",
        "",
        "## Outputs",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in output_paths.items())
    lines.extend(["", "## Candidate status", ""])
    for candidate in candidates:
        note = "; ".join(candidate.review_notes) or "None"
        lines.append(f"- `{candidate.ea_id}`: {candidate.dwelling_count} dwellings, {candidate.building_count} buildings, `{candidate.threshold_status.value}`, review: `{candidate.review_status.value}`. Notes: {note}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class _ArcPyMessages:
    def message(self, text):
        arcpy.AddMessage(text)

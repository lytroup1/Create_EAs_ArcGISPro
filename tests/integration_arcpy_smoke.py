"""Disposable ArcPy smoke test for the complete candidate EA workflow."""

import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import arcpy

from create_eas.arcpy_workflow import run_candidate_eas


def main():
    root = tempfile.mkdtemp(prefix="create_eas_smoke_")
    try:
        geodatabase = arcpy.management.CreateFileGDB(root, "smoke.gdb")[0]
        spatial_reference = arcpy.SpatialReference(3857)
        admin = arcpy.management.CreateFeatureclass(
            geodatabase, "admin", "POLYGON", spatial_reference=spatial_reference
        )[0]
        arcpy.management.AddField(admin, "AdminName", "TEXT")
        ring = arcpy.Array(
            [
                arcpy.Point(0, 0),
                arcpy.Point(5000, 0),
                arcpy.Point(5000, 5000),
                arcpy.Point(0, 5000),
                arcpy.Point(0, 0),
            ]
        )
        with arcpy.da.InsertCursor(admin, ["SHAPE@", "AdminName"]) as cursor:
            cursor.insertRow([arcpy.Polygon(ring, spatial_reference), "A"])

        buildings = arcpy.management.CreateFeatureclass(
            geodatabase, "buildings", "POINT", spatial_reference=spatial_reference
        )[0]
        arcpy.management.AddField(buildings, "NumUnits", "LONG")
        with arcpy.da.InsertCursor(buildings, ["SHAPE@XY", "NumUnits"]) as cursor:
            for index in range(30):
                cursor.insertRow(
                    [((index % 10) * 150 + 500, (index // 10) * 250 + 500), 10]
                )

        roads = arcpy.management.CreateFeatureclass(
            geodatabase, "roads", "POLYLINE", spatial_reference=spatial_reference
        )[0]
        arcpy.management.AddField(roads, "MajorMinor", "TEXT")
        with arcpy.da.InsertCursor(roads, ["SHAPE@", "MajorMinor"]) as cursor:
            cursor.insertRow(
                [
                    arcpy.Polyline(
                        arcpy.Array([arcpy.Point(1150, 0), arcpy.Point(1150, 5000)]),
                        spatial_reference,
                    ),
                    "major",
                ]
            )

        rivers = arcpy.management.CreateFeatureclass(
            geodatabase, "rivers", "POLYLINE", spatial_reference=spatial_reference
        )[0]
        with arcpy.da.InsertCursor(rivers, ["SHAPE@"]) as cursor:
            cursor.insertRow(
                [
                    arcpy.Polyline(
                        arcpy.Array([arcpy.Point(0, 1250), arcpy.Point(5000, 1250)]),
                        spatial_reference,
                    )
                ]
            )

        outputs = run_candidate_eas(
            administrative_boundary=admin,
            administrative_id_field="AdminName",
            buildings=buildings,
            dwelling_count_field="NumUnits",
            roads=roads,
            road_classification_field="MajorMinor",
            rivers=rivers,
            minimum_dwellings=50,
            target_dwellings=100,
            maximum_dwellings=120,
            clustering_distance=500,
            boundary_cell_size=5,
            dwelling_weight=0.5,
            building_weight=0.25,
            distance_weight=0.25,
            output_gdb=geodatabase,
            output_prefix="SmokeEA",
        )
        counts = {
            name: int(arcpy.management.GetCount(path)[0])
            for name, path in outputs.items()
        }
        assert counts["ea_polygons"] > 0
        assert counts["building_assignments"] == 30
        assert counts["summary"] == counts["ea_polygons"]
        with arcpy.da.SearchCursor(admin, ["SHAPE@"]) as cursor:
            admin_geometry = next(cursor)[0]
        ea_geometries = {}
        with arcpy.da.SearchCursor(outputs["ea_polygons"], ["EAID", "SHAPE@"]) as cursor:
            for ea_id, geometry in cursor:
                ea_geometries[ea_id] = geometry
        partition_geometry = None
        total_ea_area = 0.0
        for geometry in ea_geometries.values():
            total_ea_area += geometry.area
            partition_geometry = geometry if partition_geometry is None else partition_geometry.union(geometry)
        area_tolerance = max(admin_geometry.area * 0.000001, 1.0)
        assert abs(partition_geometry.area - admin_geometry.area) <= area_tolerance
        assert abs(total_ea_area - partition_geometry.area) <= area_tolerance
        with arcpy.da.SearchCursor(outputs["building_assignments"], ["EAID", "SHAPE@"]) as cursor:
            for ea_id, geometry in cursor:
                assert ea_geometries[ea_id].contains(geometry)
        print("ARCPY_SMOKE_OK", counts)
    finally:
        arcpy.ClearWorkspaceCache_management()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()

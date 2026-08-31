"""ArcGIS Pro Python toolbox for candidate Enumeration Areas."""

import importlib
import importlib.util
import os
import sys

import arcpy


_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


class Toolbox:
    def __init__(self):
        self.label = "PreEA"
        self.alias = "preea"
        self.tools = [CreateCandidateEAs]


class CreateCandidateEAs:
    def __init__(self):
        self.label = "Create Candidate EAs"
        self.description = (
            "Create complete, non-overlapping candidate enumeration areas from building points "
            "and dwelling counts. Roads influence where boundaries fall, and all results remain "
            "review proposals rather than final enumeration areas."
        )
        self.category = "PreEA"
        self.canRunInBackground = False

    def getParameterInfo(self):
        parameters = [
            _feature_layer("Administrative Boundary", "administrative_boundary", "Polygon", "Required Inputs"),
            _feature_layer("Buildings", "buildings", "Point", "Required Inputs"),
        ]
        admin_field = arcpy.Parameter(
            displayName="Administrative ID Field",
            name="administrative_id_field",
            datatype="Field",
            parameterType="Required",
            direction="Input",
        )
        admin_field.parameterDependencies = ["administrative_boundary"]
        admin_field.filter.list = ["Short", "Long", "Text"]
        admin_field.category = "Required Inputs"
        dwelling_field = arcpy.Parameter(
            displayName="Dwelling Count Field",
            name="dwelling_count_field",
            datatype="Field",
            parameterType="Required",
            direction="Input",
        )
        dwelling_field.parameterDependencies = ["buildings"]
        dwelling_field.filter.list = ["Short", "Long", "Double"]
        dwelling_field.category = "Required Inputs"
        parameters[1:1] = [admin_field]
        parameters.insert(3, dwelling_field)

        parameters.extend(
            [
                _feature_layer("Roads", "roads", "Polyline", "Boundary Constraints", "Optional"),
                _field_parameter(
                    "Road Classification Field",
                    "road_classification_field",
                    "roads",
                    "Boundary Constraints",
                ),
                _feature_layer("Rivers", "rivers", "Polyline", "Boundary Constraints", "Optional"),
            ]
        )
        for label, name, default in (
            ("Minimum Dwellings per EA", "minimum_dwellings", 0),
            ("Target Dwellings per EA", "target_dwellings", 100),
            ("Maximum Dwellings per EA", "maximum_dwellings", 120),
        ):
            parameters.append(_value_parameter(label, name, "Long", default, "EA Workload Thresholds"))
        parameters.append(
            _value_parameter(
                "Initial Building Clustering Distance",
                "clustering_distance",
                "Double",
                1000,
                "Micro-Unit Settings",
            )
        )
        parameters.append(
            _value_parameter(
                "Boundary Alignment Resolution (Meters)",
                "boundary_cell_size",
                "Double",
                5,
                "Boundary Constraints",
            )
        )
        for label, name, default in (
            ("Dwelling Balance Weight", "dwelling_weight", 0.5),
            ("Building Balance Weight", "building_weight", 0.25),
            ("Distance Weight", "distance_weight", 0.25),
        ):
            parameters.append(_value_parameter(label, name, "Double", default, "Advanced Scoring"))
        output_gdb = _value_parameter(
            "Output Geodatabase", "output_gdb", "Workspace", None, "Outputs", "Required", "Input"
        )
        output_gdb.filter.list = ["Local Database"]
        parameters.append(output_gdb)
        parameters.append(
            _value_parameter("Output Name Prefix", "output_prefix", "String", "CandidateEA", "Outputs")
        )
        diagnostic = _value_parameter(
            "Diagnostic Markdown File", "diagnostic_file", "File", None, "Outputs", "Optional", "Output"
        )
        diagnostic.filter.list = ["md"]
        parameters.append(diagnostic)
        parameters.append(
            _value_parameter(
                "Candidate EA Polygons", "candidate_eas", "DEFeatureClass", None, "Outputs", "Derived", "Output"
            )
        )
        parameters.append(
            _value_parameter(
                "Building Assignments",
                "building_assignments",
                "DEFeatureClass",
                None,
                "Outputs",
                "Derived",
                "Output",
            )
        )
        parameters.append(
            _value_parameter("EA Summary", "ea_summary", "DETable", None, "Outputs", "Derived", "Output")
        )
        return parameters

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        parameter_by_name = _parameters_by_name(parameters)
        for name, message in (
            ("administrative_boundary", "Administrative Boundary is required."),
            ("administrative_id_field", "Administrative ID Field is required."),
            ("buildings", "Buildings is required."),
            ("dwelling_count_field", "Dwelling Count Field is required."),
        ):
            parameter = parameter_by_name[name]
            if not parameter.valueAsText:
                parameter.setErrorMessage(message)
        _validate_threshold_parameters(parameters)
        _validate_weight_parameters(parameters)
        boundary_cell_size = parameter_by_name.get("boundary_cell_size")
        if boundary_cell_size is not None:
            try:
                if float(boundary_cell_size.value) <= 0:
                    boundary_cell_size.setErrorMessage(
                        "Boundary alignment resolution must be greater than zero."
                    )
            except (TypeError, ValueError):
                boundary_cell_size.setErrorMessage(
                    "Boundary alignment resolution must be numeric."
                )

    def execute(self, parameters, messages):
        parameter_by_name = _parameters_by_name(parameters)
        _ensure_core_package()
        importlib.invalidate_caches()
        workflow = importlib.import_module("preea.arcpy_workflow")
        workflow = importlib.reload(workflow)
        arcpy.AddMessage(f"Loaded PreEA workflow revision {workflow.WORKFLOW_REVISION}.")

        _validate_feature_inputs(
            parameter_by_name["administrative_boundary"].valueAsText,
            parameter_by_name["administrative_id_field"].valueAsText,
            parameter_by_name["buildings"].valueAsText,
            parameter_by_name["dwelling_count_field"].valueAsText,
        )
        outputs = workflow.run_candidate_eas(
            administrative_boundary=parameter_by_name["administrative_boundary"].valueAsText,
            administrative_id_field=parameter_by_name["administrative_id_field"].valueAsText,
            buildings=parameter_by_name["buildings"].valueAsText,
            dwelling_count_field=parameter_by_name["dwelling_count_field"].valueAsText,
            roads=parameter_by_name["roads"].valueAsText,
            road_classification_field=parameter_by_name["road_classification_field"].valueAsText,
            rivers=parameter_by_name["rivers"].valueAsText,
            minimum_dwellings=int(parameter_by_name["minimum_dwellings"].value),
            target_dwellings=int(parameter_by_name["target_dwellings"].value),
            maximum_dwellings=int(parameter_by_name["maximum_dwellings"].value),
            clustering_distance=float(parameter_by_name["clustering_distance"].value),
            boundary_cell_size=float(
                parameter_by_name["boundary_cell_size"].value
                if "boundary_cell_size" in parameter_by_name
                else 5
            ),
            dwelling_weight=float(parameter_by_name["dwelling_weight"].value),
            building_weight=float(parameter_by_name["building_weight"].value),
            distance_weight=float(parameter_by_name["distance_weight"].value),
            output_gdb=parameter_by_name["output_gdb"].valueAsText,
            output_prefix=parameter_by_name["output_prefix"].valueAsText,
            diagnostic_file=parameter_by_name["diagnostic_file"].valueAsText,
        )
        arcpy.SetParameterAsText(
            _parameter_index(parameters, "candidate_eas"), outputs["ea_polygons"]
        )
        arcpy.SetParameterAsText(
            _parameter_index(parameters, "building_assignments"), outputs["building_assignments"]
        )
        arcpy.SetParameterAsText(
            _parameter_index(parameters, "ea_summary"), outputs["summary"]
        )


def _feature_layer(label, name, geometry_type, category, parameter_type="Required"):
    parameter = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype="GPFeatureLayer",
        parameterType=parameter_type,
        direction="Input",
    )
    parameter.filter.list = [geometry_type]
    parameter.category = category
    return parameter


def _field_parameter(label, name, dependency, category):
    parameter = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype="Field",
        parameterType="Optional",
        direction="Input",
    )
    parameter.parameterDependencies = [dependency]
    parameter.filter.list = ["Short", "Long", "Text"]
    parameter.category = category
    return parameter


def _value_parameter(
    label,
    name,
    data_type,
    default,
    category,
    parameter_type="Required",
    direction="Input",
):
    geoprocessing_types = {
        "Long": "GPLong",
        "Double": "GPDouble",
        "Workspace": "DEWorkspace",
        "String": "GPString",
        "File": "DEFile",
    }
    parameter = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype=geoprocessing_types.get(data_type, data_type),
        parameterType=parameter_type,
        direction=direction,
    )
    if default is not None:
        parameter.value = default
    parameter.category = category
    return parameter


def _parameters_by_name(parameters):
    return {parameter.name: parameter for parameter in parameters}


def _parameter_index(parameters, name):
    return next(index for index, parameter in enumerate(parameters) if parameter.name == name)


def _ensure_core_package():
    package_path = os.path.join(_SRC, "preea")
    init_path = os.path.join(package_path, "__init__.py")
    if not os.path.isfile(init_path):
        raise RuntimeError(
            "The PreEA core package was not found. Keep the toolbox folder and src\\preea folder together. "
            f"Expected: {package_path}"
        )
    package = sys.modules.get("preea")
    if package is not None:
        return
    spec = importlib.util.spec_from_file_location(
        "preea",
        init_path,
        submodule_search_locations=[package_path],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load the PreEA core package from {package_path}.")
    package = importlib.util.module_from_spec(spec)
    sys.modules["preea"] = package
    spec.loader.exec_module(package)


def _validate_threshold_parameters(parameters):
    parameter_by_name = _parameters_by_name(parameters)
    minimum_parameter = parameter_by_name["minimum_dwellings"]
    target_parameter = parameter_by_name["target_dwellings"]
    maximum_parameter = parameter_by_name["maximum_dwellings"]
    try:
        minimum = int(minimum_parameter.value)
        target = int(target_parameter.value)
        maximum = int(maximum_parameter.value)
    except (TypeError, ValueError):
        target_parameter.setErrorMessage(
            "Minimum, target, and maximum dwellings must be whole numbers."
        )
        return
    if minimum < 0:
        minimum_parameter.setErrorMessage("Minimum dwellings per EA cannot be negative.")
    if target < 1:
        target_parameter.setErrorMessage("Target dwellings per EA must be greater than zero.")
    if maximum < 1:
        maximum_parameter.setErrorMessage("Maximum dwellings per EA must be greater than zero.")
    if minimum > target:
        minimum_parameter.setErrorMessage(
            "Minimum dwellings per EA cannot be greater than the target."
        )
    if target > maximum:
        target_parameter.setErrorMessage(
            "Target dwellings per EA cannot be greater than the maximum."
        )


def _validate_weight_parameters(parameters):
    parameter_by_name = _parameters_by_name(parameters)
    weight_parameters = [
        parameter_by_name[name]
        for name in ("dwelling_weight", "building_weight", "distance_weight")
    ]
    weights = []
    for parameter in weight_parameters:
        try:
            weights.append(float(parameter.value))
        except (TypeError, ValueError):
            parameter.setErrorMessage("Scoring weights must be numeric.")
            return
    if any(weight < 0 for weight in weights):
        weight_parameters[0].setErrorMessage("Scoring weights cannot be negative.")
    elif sum(weights) == 0:
        weight_parameters[0].setErrorMessage(
            "At least one scoring weight must be greater than zero."
        )


def _validate_feature_inputs(admin_layer, admin_field, building_layer, dwelling_field):
    if not arcpy.Exists(admin_layer) or not arcpy.Exists(building_layer):
        raise ValueError("Administrative Boundary and Buildings must be existing datasets.")
    if arcpy.Describe(admin_layer).shapeType.lower() != "polygon":
        raise ValueError("Administrative boundary features must be polygons.")
    if arcpy.Describe(building_layer).shapeType.lower() != "point":
        raise ValueError("The buildings input must contain point features.")
    if admin_field not in {field.name for field in arcpy.ListFields(admin_layer)}:
        raise ValueError("The selected administrative ID field does not exist.")
    if dwelling_field not in {field.name for field in arcpy.ListFields(building_layer)}:
        raise ValueError("The selected dwelling count field does not exist.")

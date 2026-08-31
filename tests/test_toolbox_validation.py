import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import types
import unittest


class FakeParameter:
    def __init__(self, name, value=None):
        self.name = name
        self.value = value
        self.valueAsText = None if value is None else str(value)
        self.errors = []

    def setErrorMessage(self, message):
        self.errors.append(message)


def _load_toolbox():
    sys.modules.setdefault("arcpy", types.ModuleType("arcpy"))
    toolbox_path = Path(__file__).parents[1] / "toolbox" / "preea.pyt"
    loader = importlib.machinery.SourceFileLoader("preea_toolbox_test", str(toolbox_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _cached_schema_parameters():
    values = (
        ("administrative_boundary", "admin"),
        ("administrative_id_field", "AdminID"),
        ("buildings", "buildings"),
        ("dwelling_count_field", "Dwellings"),
        ("roads", None),
        ("road_classification_field", None),
        ("rivers", None),
        ("minimum_dwellings", 0),
        ("target_dwellings", 100),
        ("maximum_dwellings", 120),
        ("clustering_distance", 1000),
        ("dwelling_weight", 0.5),
        ("building_weight", 0.25),
        ("distance_weight", 0.25),
        ("output_gdb", "output.gdb"),
        ("output_prefix", "CandidateEA"),
        ("diagnostic_file", None),
        ("candidate_eas", None),
        ("building_assignments", None),
        ("ea_summary", None),
    )
    return [FakeParameter(name, value) for name, value in values]


class ToolboxValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toolbox = _load_toolbox()

    def test_cached_schema_does_not_treat_output_path_as_weight(self):
        parameters = _cached_schema_parameters()

        self.toolbox._validate_weight_parameters(parameters)

        self.assertFalse(any(parameter.errors for parameter in parameters))

    def test_invalid_building_weight_is_reported_on_building_weight(self):
        parameters = _cached_schema_parameters()
        parameter_by_name = {parameter.name: parameter for parameter in parameters}
        parameter_by_name["building_weight"].value = "not numeric"

        self.toolbox._validate_weight_parameters(parameters)

        self.assertEqual(
            parameter_by_name["building_weight"].errors,
            ["Scoring weights must be numeric."],
        )
        self.assertFalse(parameter_by_name["dwelling_weight"].errors)


if __name__ == "__main__":
    unittest.main()
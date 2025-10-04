import time
from pathlib import Path
from typing import List

import pytest

from cldk import CLDK
from cldk.analysis import AnalysisLevel

from hamster.code_analysis.common import CommonAnalysis
from hamster.code_analysis.focal_class_method.focal_class_method import FocalClassMethod
from hamster.code_analysis.model.models import FocalClass

BASE_DIR = Path(__file__).resolve().parent
PROJECT_PATH_RELATIVE = "resources/spring-petclinic"
ANALYSIS_JSON_PATH_RELATIVE = "resources/output/spring-petclinic"
PROJECT_PATH = str(BASE_DIR / PROJECT_PATH_RELATIVE)
ANALYSIS_JSON_PATH = str(BASE_DIR / ANALYSIS_JSON_PATH_RELATIVE)
DATASET_NAME = "spring-petclinic"


@pytest.fixture(scope="module")
def analysis():
    return CLDK(language="java").analysis(
        project_path=PROJECT_PATH,
        analysis_level=AnalysisLevel.symbol_table,
        analysis_json_path=ANALYSIS_JSON_PATH,
        eager=False,
    )


@pytest.fixture
def time_tracker(request):
    start_time = time.time()
    yield
    duration = time.time() - start_time
    print(f"\nTest {request.node.nodeid} took {duration:.4f} seconds.")


def get_focal_class_names(classes: List[FocalClass]) -> List[str]:
    names: List[str] = []
    for cls in classes:
        names.append(cls.focal_class)
    return names


def test_focal_classes_fix(analysis, time_tracker):
    _, all_application_classes = CommonAnalysis(analysis).get_test_methods_classes_and_application_classes()
    qualified_class_name = "org.springframework.samples.petclinic.owner.PetTypeFormatterTests"
    method_signature = "shouldParse()"

    focal_classes, _, _, _ = FocalClassMethod(
        analysis=analysis,
        application_classes=all_application_classes,
    ).identify_focal_class_and_ui_api_test(qualified_class_name, method_signature, {})

    assert get_focal_class_names(focal_classes) == [
        "org.springframework.samples.petclinic.owner.PetTypeRepository",
        "org.springframework.samples.petclinic.owner.PetTypeFormatter",
    ]

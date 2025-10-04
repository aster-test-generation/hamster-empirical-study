import time
from pathlib import Path
from types import SimpleNamespace
from typing import List

import pytest

from cldk import CLDK
from cldk.analysis import AnalysisLevel

from hamster.code_analysis.common import CommonAnalysis
from hamster.code_analysis.focal_class_method.focal_class_method import FocalClassMethod
from hamster.code_analysis.model.models import (
    FocalClass,
    MockingFramework,
    TestingFramework,
)
from hamster.code_analysis.test_statistics import (
    CallAndAssertionSequenceDetailsInfo,
    ProjectAnalysisInfo,
    SetupAnalysisInfo,
    TestClassAnalysisInfo,
    TestMethodAnalysisInfo,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_PATH_RELATIVE = "resources/spring-petclinic"
ANALYSIS_JSON_PATH_RELATIVE = "resources/output/spring-petclinic"
PROJECT_PATH = str(BASE_DIR / PROJECT_PATH_RELATIVE)
ANALYSIS_JSON_PATH = str(BASE_DIR / ANALYSIS_JSON_PATH_RELATIVE)
DATASET_NAME = "spring-petclinic"


@pytest.fixture
def analysis_data(request):
    start_time = time.time()
    analysis = CLDK(language="java").analysis(
        project_path=PROJECT_PATH,
        analysis_level=AnalysisLevel.symbol_table,
        analysis_json_path=ANALYSIS_JSON_PATH,
        eager=False,
    )
    dataset_name = DATASET_NAME

    common_analysis = CommonAnalysis(analysis)
    test_class_methods, application_class = (
        common_analysis.get_test_methods_classes_and_application_classes()
    )

    yield SimpleNamespace(
        analysis=analysis,
        dataset_name=dataset_name,
        test_class_methods=test_class_methods,
        application_class=application_class,
    )

    duration = time.time() - start_time
    print(f"\nTest {request.node.nodeid} took {duration:.4f} seconds.")


def test_hamster(analysis_data):
    project_analysis = ProjectAnalysisInfo(
        analysis=analysis_data.analysis, dataset_name=analysis_data.dataset_name
    ).gather_project_analysis_info()

    for test_class_analysis in project_analysis.test_class_analyses:
        assert (
            TestingFramework.JUNIT5 in test_class_analysis.testing_frameworks
            or TestingFramework.MOCKITO in test_class_analysis.testing_frameworks
        )
        assert len(test_class_analysis.testing_frameworks) > 0

        if (
            test_class_analysis.qualified_class_name
            == "org.springframework.samples.petclinic.PostgresIntegrationTests"
        ):
            assert (
                TestingFramework.SPRING_TEST in test_class_analysis.testing_frameworks
            )
            assert test_class_analysis.setup_analyses is not None

    assert project_analysis is not None


def test_setup_analysis(analysis_data):
    qualified_class_name = (
        "org.springframework.samples.petclinic.owner.OwnerControllerTests"
    )
    class_analysis = TestClassAnalysisInfo(
        analysis=analysis_data.analysis,
        dataset_name=analysis_data.dataset_name,
        application_classes=analysis_data.application_class,
    ).get_test_class_analysis(
        qualified_class_name=qualified_class_name,
        test_methods=analysis_data.test_class_methods[qualified_class_name],
    )
    assert len(class_analysis.setup_analyses) >= 1
    assert (
        MockingFramework.MOCKITO
        in class_analysis.setup_analyses[0].mocking_frameworks_used
    )
    assert (
        MockingFramework.SPRING_TEST
        in class_analysis.setup_analyses[0].mocking_frameworks_used
    )


def test_method_analysis(analysis_data):
    qualified_class_name = (
        "org.springframework.samples.petclinic.service.ClinicServiceTests"
    )
    method_signature = "shouldInsertOwner()"
    testing_frameworks = CommonAnalysis(
        analysis_data.analysis
    ).get_testing_frameworks_for_class(qualified_class_name=qualified_class_name)
    setup_methods = SetupAnalysisInfo(analysis_data.analysis).get_setup_methods(
        qualified_class_name=qualified_class_name,
    )
    method_analysis = TestMethodAnalysisInfo(
        analysis=analysis_data.analysis,
        dataset_name=analysis_data.dataset_name,
        application_classes=analysis_data.application_class,
    ).get_test_method_analysis_info(
        testing_frameworks=testing_frameworks,
        qualified_class_name=qualified_class_name,
        method_signature=method_signature,
        setup_methods=setup_methods,
    )
    assert method_analysis is not None
    assert len(method_analysis.call_assertion_sequences) == 2


def test_all_call_and_assertion_sequences(analysis_data):
    """Quick test to see if call and assertion info can be generated for all test methods in the project."""

    call_and_assertion_info = CallAndAssertionSequenceDetailsInfo(
        analysis_data.analysis, analysis_data.dataset_name
    )
    for qualified_class_name in analysis_data.test_class_methods:
        testing_frameworks = CommonAnalysis(
            analysis_data.analysis
        ).get_testing_frameworks_for_class(qualified_class_name=qualified_class_name)
        for method_signature in analysis_data.test_class_methods[qualified_class_name]:
            print(
                f"Attempting for method {method_signature} with qualified class {qualified_class_name}"
            )
            result = (
                call_and_assertion_info.get_call_and_assertion_sequence_details_info(
                    qualified_class_name=qualified_class_name,
                    method_signature=method_signature,
                    testing_frameworks=testing_frameworks,
                )
            )
            assert result is not None


def test_focal_classes(analysis_data):
    _, all_application_classes = CommonAnalysis(
        analysis_data.analysis
    ).get_test_methods_classes_and_application_classes()

    qualified_class_name = "org.springframework.samples.petclinic.model.ValidatorTests"
    method_signature = "shouldNotValidateWhenFirstNameEmpty()"
    focal_classes, _, _, _ = FocalClassMethod(
        analysis_data.analysis
    ).identify_focal_class_and_ui_api_test(
        qualified_class_name,
        method_signature,
        {},
    )
    assert get_focal_class_names(focal_classes) == [
        "org.springframework.samples.petclinic.model.Person",
    ]

    qualified_class_name = "org.springframework.samples.petclinic.vet.VetTests"
    method_signature = "testSerialization()"
    focal_classes, _, _, _ = FocalClassMethod(
        analysis_data.analysis
    ).identify_focal_class_and_ui_api_test(
        qualified_class_name,
        method_signature,
        {},
    )
    assert get_focal_class_names(focal_classes) == [
        "org.springframework.samples.petclinic.vet.Vet",
    ]

    qualified_class_name = (
        "org.springframework.samples.petclinic.owner.PetValidatorTests"
    )
    method_signature = "testValidate()"
    FocalClassMethod(analysis_data.analysis).identify_focal_class_and_ui_api_test(
        qualified_class_name,
        method_signature,
        {qualified_class_name: ["setUp()"]},
    )

    qualified_class_name = (
        "org.springframework.samples.petclinic.service.ClinicServiceTests"
    )
    method_signature = "shouldInsertPetIntoDatabaseAndGenerateId()"
    focal_classes, _, _, _ = FocalClassMethod(
        analysis=analysis_data.analysis,
        application_classes=all_application_classes,
    ).identify_focal_class_and_ui_api_test(
        qualified_class_name,
        method_signature,
        {},
    )
    assert get_focal_class_names(focal_classes) == [
        "org.springframework.samples.petclinic.owner.OwnerRepository",
    ]


def get_focal_class_names(classes: List[FocalClass]) -> List[str]:
    focal_class_names = []
    for cls in classes:
        focal_class_names.append(cls.focal_class)
    return focal_class_names

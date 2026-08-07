from pathlib import Path
from zipfile import ZipFile
import io

from emulti_pipeline.demo import (
    DEMO_RUN_ID,
    build_demo_archive,
    clean_feature_name,
    load_confusion_matrix,
    load_demo_bundle,
    marker_comparison,
    validate_demo_root,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = PROJECT_ROOT / "demo_artifacts" / DEMO_RUN_ID


def test_preloaded_demo_contains_required_artifacts() -> None:
    assert validate_demo_root(RUN_ROOT) == []


def test_demo_bundle_and_profile_marker_comparison() -> None:
    bundle = load_demo_bundle(RUN_ROOT)
    assert len(bundle["profiles"]) == 800
    assert len(bundle["classification"]) == 160

    patient_id = str(bundle["classification"].iloc[0]["ID do perfil sintético"])
    comparison = marker_comparison(bundle["profiles"], bundle["extracted"], patient_id)
    assert len(comparison) == 10
    assert set(comparison["Concordância"]).issubset({"Sim", "Não"})


def test_confusion_matrix_has_priority_labels() -> None:
    matrix = load_confusion_matrix(
        RUN_ROOT,
        "03_operacional_marcadores_extraidos",
        "xgboost",
    )
    assert matrix.shape == (4, 4)
    assert list(matrix.index) == ["Baixa", "Moderada", "Alta", "Urgente"]
    assert list(matrix.columns) == ["Baixa", "Moderada", "Alta", "Urgente"]


def test_feature_names_are_presentable() -> None:
    assert clean_feature_name("numeric__phq9_total") == "PHQ-9 total"
    assert (
        clean_feature_name("numeric__marker_risco_violencia_present")
        == "Risco de violência — presença"
    )


def test_download_archive_excludes_model_binaries() -> None:
    archive_bytes = build_demo_archive(RUN_ROOT)
    with ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
    assert names
    assert any(name.endswith("report.md") for name in names)
    assert not any(name.endswith(".joblib") for name in names)

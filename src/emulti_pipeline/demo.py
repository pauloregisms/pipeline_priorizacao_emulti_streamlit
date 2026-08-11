"""Leitura segura dos artefatos congelados usados na demonstração Streamlit."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


DEMO_RUN_ID = "experimento_gemini31flash_lite"
PRIORITY_LABELS = ["Baixa", "Moderada", "Alta", "Urgente"]

DATASET_LABELS = {
    "01_estruturados_escores": "Estruturados + escores",
    "02_limite_superior_marcadores_origem": "Limite superior: marcadores de origem",
    "03_operacional_marcadores_extraidos": "Operacional: marcadores extraídos",
}

MODEL_LABELS = {
    "rule_baseline": "Regra de referência",
    "ordinal_logit": "Regressão logística ordinal",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}

MARKER_LABELS = {
    "ideacao_suicida": "Ideação suicida",
    "planejamento_suicida": "Planejamento suicida",
    "autoagressao_iminente": "Autoagressão iminente",
    "risco_violencia": "Risco de violência",
    "sintomas_psicoticos": "Sintomas psicóticos",
    "uso_problematico_substancias": "Uso problemático de substâncias",
    "internacao_previa": "Internação prévia",
    "agravamento_recente": "Agravamento recente",
    "suporte_social_baixo": "Suporte social baixo",
    "comprometimento_funcional": "Comprometimento funcional",
}

REQUIRED_ARTIFACTS = (
    "run_metadata.json",
    "environment.json",
    "resolved_config.yaml",
    "01_profiles/profiles.csv",
    "02_psychometrics/psychometrics.csv",
    "03_quality_control/quality_summary.json",
    "04_narratives/narratives_index.csv",
    "05_priority/prioridade_referencia.csv",
    "05_priority/priority_metadata.json",
    "06_extraction/marcadores_extraidos.csv",
    "06_extraction/extraction_manifest.json",
    "08_extraction_validation/validation_summary.json",
    "10_modeling/modeling_summary.csv",
    "11_explanations/explanation_summary.json",
    "13_report/report.md",
    "14_priority_view/classification_queue.csv",
    "14_priority_view/prediction_traceability.csv",
    "14_priority_view/priority_view_manifest.json",
)

ARCHIVE_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".html", ".yaml", ".yml"}


def validate_demo_root(root: Path) -> list[str]:
    """Retorna a lista de artefatos obrigatórios ausentes."""

    return [relative for relative in REQUIRED_ARTIFACTS if not (root / relative).is_file()]


def read_json(path: Path) -> dict[str, Any]:
    """Lê um objeto JSON UTF-8."""

    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Era esperado um objeto JSON em {path}")
    return value


def load_demo_bundle(root: Path) -> dict[str, Any]:
    """Carrega os artefatos centrais usados pelas telas da demonstração."""

    missing = validate_demo_root(root)
    if missing:
        raise FileNotFoundError("Artefatos obrigatórios ausentes: " + ", ".join(missing))

    return {
        "profiles": pd.read_csv(root / "01_profiles/profiles.csv"),
        "psychometrics": pd.read_csv(root / "02_psychometrics/psychometrics.csv"),
        "quality": read_json(root / "03_quality_control/quality_summary.json"),
        "narratives": pd.read_csv(root / "04_narratives/narratives_index.csv"),
        "priority": pd.read_csv(root / "05_priority/prioridade_referencia.csv"),
        "priority_metadata": read_json(root / "05_priority/priority_metadata.json"),
        "extracted": pd.read_csv(root / "06_extraction/marcadores_extraidos.csv"),
        "extraction_manifest": read_json(root / "06_extraction/extraction_manifest.json"),
        "validation": read_json(root / "08_extraction_validation/validation_summary.json"),
        "modeling_summary": pd.read_csv(root / "10_modeling/modeling_summary.csv"),
        "explanation_summary": read_json(root / "11_explanations/explanation_summary.json"),
        "classification": pd.read_csv(root / "14_priority_view/classification_queue.csv"),
        "traceability": pd.read_csv(root / "14_priority_view/prediction_traceability.csv"),
        "priority_view_manifest": read_json(root / "14_priority_view/priority_view_manifest.json"),
        "run_metadata": read_json(root / "run_metadata.json"),
        "environment": read_json(root / "environment.json"),
        "report": (root / "13_report/report.md").read_text(encoding="utf-8"),
        "config": (root / "resolved_config.yaml").read_text(encoding="utf-8"),
    }


def _boolean_value(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes"}
    return bool(value)


def _marker_status(row: pd.Series, prefix: str) -> str:
    present = _boolean_value(row.get(f"{prefix}_present"))
    negated = _boolean_value(row.get(f"{prefix}_negated"))
    remote = _boolean_value(row.get(f"{prefix}_remote_present"))
    if present and not negated:
        return "Presente"
    if negated:
        return "Negado"
    if remote:
        return "Antecedente remoto"
    return "Não mencionado"


def marker_comparison(
    profiles: pd.DataFrame,
    extracted: pd.DataFrame,
    patient_id: str,
) -> pd.DataFrame:
    """Compara marcadores de origem e extraídos para um perfil sintético."""

    profile_match = profiles.loc[profiles["patient_id"] == patient_id]
    extracted_match = extracted.loc[extracted["patient_id"] == patient_id]
    if profile_match.empty or extracted_match.empty:
        raise KeyError(f"Perfil sintético não encontrado: {patient_id}")

    origin = profile_match.iloc[0]
    result = extracted_match.iloc[0]
    rows: list[dict[str, Any]] = []
    for marker, label in MARKER_LABELS.items():
        origin_prefix = f"marcadores_origem_{marker}"
        extracted_prefix = f"marcadores_extraidos_{marker}"
        origin_status = _marker_status(origin, origin_prefix)
        extracted_status = _marker_status(result, extracted_prefix)
        rows.append(
            {
                "Marcador": label,
                "Origem sintética": origin_status,
                "Extraído da narrativa": extracted_status,
                "Concordância": "Sim" if origin_status == extracted_status else "Não",
                "Temporalidade extraída": result.get(
                    f"{extracted_prefix}_temporality", "não especificada"
                ),
                "Severidade extraída": result.get(
                    f"{extracted_prefix}_severity", "não especificada"
                ),
                "Certeza extraída": result.get(
                    f"{extracted_prefix}_certainty", "não especificada"
                ),
                "Experienciador": result.get(
                    f"{extracted_prefix}_experiencer", "não especificado"
                ),
                "Evidência textual": result.get(f"{extracted_prefix}_evidence", ""),
            }
        )
    return pd.DataFrame(rows)


def clean_feature_name(feature: str) -> str:
    """Converte o nome técnico de uma variável em rótulo legível."""

    cleaned = feature
    for prefix in ("numeric__", "categorical__"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]

    replacements = {
        "phq9_total": "PHQ-9 total",
        "gad7_total": "GAD-7 total",
        "idate_estado_total": "IDATE-Estado total",
        "social_vulnerability": "Vulnerabilidade social",
        "income_normalized": "Renda normalizada",
        "age_years": "Idade",
    }
    if cleaned in replacements:
        return replacements[cleaned]

    for marker, label in MARKER_LABELS.items():
        if marker in cleaned:
            qualifier = cleaned.split(marker, maxsplit=1)[-1].strip("_")
            qualifier_label = {
                "present": "presença",
                "negated": "negação",
                "remote_present": "antecedente remoto",
                "severity_code": "código de severidade",
            }.get(qualifier, qualifier.replace("_", " "))
            return f"{label} — {qualifier_label}"

    return cleaned.replace("_", " ").strip().capitalize()


def load_confusion_matrix(root: Path, dataset: str, model: str) -> pd.DataFrame:
    path = root / "10_modeling" / dataset / model / "final_test_confusion_matrix.csv"
    matrix = pd.read_csv(path, index_col=0)
    matrix.index = PRIORITY_LABELS[: len(matrix.index)]
    matrix.columns = PRIORITY_LABELS[: len(matrix.columns)]
    matrix.index.name = "Referência sintética"
    matrix.columns.name = "Previsão"
    return matrix


def list_demo_artifacts(root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append(
            {
                "Artefato": path.relative_to(root).as_posix(),
                "Tipo": path.suffix.lower().lstrip(".") or "arquivo",
                "Tamanho (KB)": round(path.stat().st_size / 1024, 1),
            }
        )
    return pd.DataFrame(rows)


def build_demo_archive(root: Path) -> bytes:
    """Empacota artefatos legíveis, excluindo binários de modelos."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path.suffix.lower() not in ARCHIVE_SUFFIXES:
                continue
            relative = path.relative_to(root)
            archive.write(path, arcname=(Path(DEMO_RUN_ID) / relative).as_posix())
    return buffer.getvalue()

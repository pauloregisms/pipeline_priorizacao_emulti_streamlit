"""Contrato único para marcadores clínicos de origem e extraídos.

O módulo mantém a mesma representação semântica nos dois lados da narrativa.
Isso permite comparar preservação de informação sem oferecer mais atributos ao
conjunto extraído do que ao conjunto de origem.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


MARKER_NAMES: tuple[str, ...] = (
    "ideacao_suicida",
    "planejamento_suicida",
    "autoagressao_iminente",
    "risco_violencia",
    "sintomas_psicoticos",
    "uso_problematico_substancias",
    "internacao_previa",
    "agravamento_recente",
    "suporte_social_baixo",
    "comprometimento_funcional",
)

MARKER_FEATURE_FIELDS: tuple[str, ...] = (
    "present",
    "negated",
    "remote_present",
    "temporality",
    "severity",
    "severity_code",
    "certainty",
    "experiencer",
)

MARKER_ALL_FIELDS: tuple[str, ...] = (*MARKER_FEATURE_FIELDS, "evidence")

TEMPORALITY_VALUES = frozenset({"atual", "remoto", "nao_especificado"})
SEVERITY_VALUES = frozenset(
    {"ausente", "leve", "moderado", "alto", "importante", "nao_especificado"}
)
CERTAINTY_VALUES = frozenset({"afirmado", "incerto"})
EXPERIENCER_VALUES = frozenset({"paciente", "terceiro"})


def marker_column(prefix: str, marker: str, field: str) -> str:
    """Retorna o nome canônico de uma coluna de marcador."""
    return f"{prefix}{marker}_{field}"


def marker_feature_columns(prefix: str) -> list[str]:
    """Lista colunas modeláveis em ordem estável."""
    return [
        marker_column(prefix, marker, field)
        for marker in MARKER_NAMES
        for field in MARKER_FEATURE_FIELDS
    ]


def marker_all_columns(prefix: str) -> list[str]:
    """Lista todas as colunas, incluindo evidência textual não modelável."""
    return [
        marker_column(prefix, marker, field)
        for marker in MARKER_NAMES
        for field in MARKER_ALL_FIELDS
    ]


def normalize_marker(marker: str, value: Mapping[str, Any]) -> dict[str, Any]:
    """Valida e normaliza um marcador para o contrato fechado do pipeline."""
    if marker not in MARKER_NAMES:
        raise ValueError(f"Marcador fora da ontologia: {marker!r}.")
    if not isinstance(value, Mapping):
        legacy_value = int(value)
        severity_code = legacy_value if marker == "comprometimento_funcional" else int(legacy_value > 0)
        severity = {0: "ausente", 1: "leve", 2: "moderado", 3: "importante"}[severity_code]
        value = {
            "present": int(legacy_value > 0),
            "severity_code": severity_code,
            "severity": severity,
        }
    present = int(bool(value.get("present", 0)))
    negated = int(bool(value.get("negated", 0)))
    remote_present = int(bool(value.get("remote_present", 0)))
    if present and negated:
        raise ValueError(f"Marcador {marker!r} não pode estar presente e negado simultaneamente.")

    temporality = str(value.get("temporality", "nao_especificado"))
    severity = str(value.get("severity", "ausente"))
    certainty = str(value.get("certainty", "afirmado"))
    experiencer = str(value.get("experiencer", "paciente"))
    severity_code = int(value.get("severity_code", 0))
    if temporality not in TEMPORALITY_VALUES:
        raise ValueError(f"Temporalidade inválida em {marker!r}: {temporality!r}.")
    if severity not in SEVERITY_VALUES:
        raise ValueError(f"Severidade inválida em {marker!r}: {severity!r}.")
    if certainty not in CERTAINTY_VALUES:
        raise ValueError(f"Certeza inválida em {marker!r}: {certainty!r}.")
    if experiencer not in EXPERIENCER_VALUES:
        raise ValueError(f"Experienciador inválido em {marker!r}: {experiencer!r}.")
    if severity_code not in {0, 1, 2, 3}:
        raise ValueError(f"Código de severidade inválido em {marker!r}: {severity_code!r}.")

    return {
        "present": present,
        "negated": negated,
        "remote_present": remote_present,
        "temporality": temporality,
        "severity": severity,
        "severity_code": severity_code,
        "certainty": certainty,
        "experiencer": experiencer,
        "evidence": str(value.get("evidence", "")).strip(),
    }


def flatten_markers(markers: Mapping[str, Mapping[str, Any]], prefix: str) -> dict[str, Any]:
    """Converte marcadores aninhados em colunas tabulares canônicas."""
    flattened: dict[str, Any] = {}
    for marker in MARKER_NAMES:
        normalized = normalize_marker(marker, markers.get(marker, {}))
        for field, value in normalized.items():
            flattened[marker_column(prefix, marker, field)] = value
    return flattened


def markers_from_row(row: Mapping[str, Any] | pd.Series, prefix: str) -> dict[str, dict[str, Any]]:
    """Reconstrói o contrato aninhado a partir de uma linha tabular."""
    result: dict[str, dict[str, Any]] = {}
    for marker in MARKER_NAMES:
        values: dict[str, Any] = {}
        for field in MARKER_ALL_FIELDS:
            column = marker_column(prefix, marker, field)
            if column in row and not pd.isna(row[column]):
                values[field] = row[column]
        result[marker] = normalize_marker(marker, values)
    return result


def marker_is_active(
    frame: pd.DataFrame,
    prefix: str,
    marker: str,
    *,
    require_current: bool = False,
) -> pd.Series:
    """Indica marcador afirmado do paciente e, quando exigido, atual."""
    def series(field: str, default: object) -> pd.Series:
        column = marker_column(prefix, marker, field)
        return frame[column] if column in frame else pd.Series(default, index=frame.index)

    present = pd.to_numeric(
        series("present", 0), errors="coerce"
    ).fillna(0).astype(int)
    negated = pd.to_numeric(
        series("negated", 0), errors="coerce"
    ).fillna(0).astype(int)
    certainty = series("certainty", "afirmado").fillna("afirmado")
    experiencer = series("experiencer", "paciente").fillna("paciente")
    active = (present == 1) & (negated == 0) & (certainty == "afirmado") & (experiencer == "paciente")
    if require_current:
        temporality = series("temporality", "nao_especificado").fillna("nao_especificado")
        active &= temporality == "atual"
    return active

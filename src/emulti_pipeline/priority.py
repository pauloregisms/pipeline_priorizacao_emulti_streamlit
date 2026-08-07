"""Matriz única e versionada de prioridade de referência simulada."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .markers import marker_column, marker_is_active

PRIORITY_ORDER = ["baixa", "moderada", "alta", "urgente"]
PRIORITY_TO_CODE = {label: index for index, label in enumerate(PRIORITY_ORDER)}


def _required_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Colunas necessárias ausentes para regra de prioridade: {missing}")


def _marker(frame: pd.DataFrame, prefix: str, name: str, *, current: bool = True) -> pd.Series:
    return marker_is_active(frame, prefix, name, require_current=current).astype(int)


def _functional_severity(frame: pd.DataFrame, prefix: str) -> pd.Series:
    column = marker_column(prefix, "comprometimento_funcional", "severity_code")
    severity = pd.to_numeric(frame[column], errors="coerce").fillna(0) if column in frame else pd.Series(0, index=frame.index)
    return severity.astype(int) * _marker(frame, prefix, "comprometimento_funcional")


def apply_priority_matrix(
    frame: pd.DataFrame,
    rules: dict[str, Any],
    marker_prefix: str,
    *,
    seed: int | None = None,
) -> pd.DataFrame:
    """Aplica exatamente a mesma matriz a marcadores de origem ou extraídos."""
    _required_columns(frame, ["phq9_total", "gad7_total", "idate_estado_total", "social_vulnerability"])
    phq = pd.to_numeric(frame["phq9_total"], errors="coerce").fillna(0)
    gad = pd.to_numeric(frame["gad7_total"], errors="coerce").fillna(0)
    stai = pd.to_numeric(frame["idate_estado_total"], errors="coerce").fillna(0)
    vulnerability = pd.to_numeric(frame["social_vulnerability"], errors="coerce").fillna(0)
    functional = _functional_severity(frame, marker_prefix)

    urgent = (
        ((_marker(frame, marker_prefix, "ideacao_suicida") == 1) & (_marker(frame, marker_prefix, "planejamento_suicida") == 1))
        | (_marker(frame, marker_prefix, "autoagressao_iminente") == 1)
        | (_marker(frame, marker_prefix, "risco_violencia") == 1)
        | ((_marker(frame, marker_prefix, "sintomas_psicoticos") == 1) & (functional >= 3))
    )
    high_evidence = (
        (phq >= float(rules["phq_high"])).astype(int)
        + (gad >= float(rules["gad_high"])).astype(int)
        + (stai >= float(rules["stai_high"])).astype(int)
        + (functional >= 2).astype(int)
        + _marker(frame, marker_prefix, "uso_problematico_substancias")
        + _marker(frame, marker_prefix, "agravamento_recente")
        + (vulnerability >= float(rules["vulnerability_high"])).astype(int)
        + _marker(frame, marker_prefix, "suporte_social_baixo")
    )
    moderate_evidence = (
        (phq >= float(rules["phq_moderate"])).astype(int)
        + (gad >= float(rules["gad_moderate"])).astype(int)
        + (stai >= float(rules["stai_moderate"])).astype(int)
        + (functional >= 1).astype(int)
        + _marker(frame, marker_prefix, "agravamento_recente")
        + _marker(frame, marker_prefix, "suporte_social_baixo")
    )
    score = float(rules["high_evidence_weight"]) * high_evidence + float(rules["moderate_evidence_weight"]) * moderate_evidence
    noise = float(rules.get("nonurgent_label_noise", 0.0))
    if noise:
        if seed is None:
            raise ValueError("Uma semente explícita é obrigatória quando nonurgent_label_noise > 0.")
        score = score + np.random.default_rng(seed).normal(0, noise, len(frame))
    labels = np.where(
        score >= float(rules["high_priority_cutoff"]),
        "alta",
        np.where(score >= float(rules["moderate_priority_cutoff"]), "moderada", "baixa"),
    )
    labels = np.where(urgent, "urgente", labels)
    return pd.DataFrame(
        {
            "priority_label": labels,
            "priority_code": [PRIORITY_TO_CODE[label] for label in labels],
            "urgent_rule_triggered": urgent.astype(int),
            "priority_high_evidence": high_evidence.astype(int),
            "priority_moderate_evidence": moderate_evidence.astype(int),
            "priority_score": np.asarray(score, dtype=float),
        },
        index=frame.index,
    )


def assign_reference_priority(
    profiles: pd.DataFrame,
    psychometrics: pd.DataFrame,
    config: dict[str, Any],
    seed: int,
) -> pd.DataFrame:
    """Cria a referência simulada com marcadores qualificados de origem."""
    merged = profiles.merge(psychometrics, on="patient_id", validate="one_to_one")
    result = apply_priority_matrix(
        merged,
        config["priority_rules"],
        "marcadores_origem_",
        seed=seed + 3000,
    )
    return pd.DataFrame(
        {
            "patient_id": merged["patient_id"],
            "prioridade_referencia": result["priority_label"],
            "prioridade_referencia_codigo": result["priority_code"],
            "urgent_rule_triggered": result["urgent_rule_triggered"],
            "priority_high_evidence": result["priority_high_evidence"],
            "priority_moderate_evidence": result["priority_moderate_evidence"],
            "priority_score": result["priority_score"],
        }
    )


def rule_baseline_from_available_features(frame: pd.DataFrame, config: dict[str, Any]) -> np.ndarray:
    """Aplica a matriz protocolada às informações disponíveis, sem probabilidades artificiais."""
    if any(column.startswith("marcadores_extraidos_") for column in frame):
        prefix = "marcadores_extraidos_"
    elif any(column.startswith("marcadores_origem_") for column in frame):
        prefix = "marcadores_origem_"
    elif any(column.startswith("marker_") for column in frame):
        prefix = "marker_"
    else:
        prefix = "marcadores_indisponiveis_"
    return apply_priority_matrix(frame, config["priority_rules"], prefix)["priority_label"].to_numpy()

"""Construção dos conjuntos analíticos previstos na metodologia."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .markers import MARKER_FEATURE_FIELDS, MARKER_NAMES, marker_column


def build_analytical_sets(
    profiles: pd.DataFrame,
    psychometrics: pd.DataFrame,
    priority: pd.DataFrame,
    extracted: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Cria os três conjuntos: dados_estruturados + indicadores_psicometricos, dados_estruturados + indicadores_psicometricos + marcadores_origem e dados_estruturados + indicadores_psicometricos + marcadores_extraidos.

    A gravidade latente e qualquer coluna de auditoria do gerador são retiradas antes
    da modelagem, porque não estariam disponíveis no cenário conceitual de encaminhamento.
    """
    merged = profiles.merge(psychometrics, on="patient_id", how="inner", validate="one_to_one")
    merged = merged.merge(priority, on="patient_id", how="inner", validate="one_to_one")
    merged = merged.merge(extracted, on="patient_id", how="inner", validate="one_to_one")

    # X: atributos estruturados, sem marcadores_origem e sem variável de auditoria de gravidade latente.
    profile_cols = [
        c for c in profiles.columns
        if c not in {"patient_id", "seed", "gravidade_latente_auditoria"} and not c.startswith("marcadores_origem_")
    ]
    # S: totais; itens podem ser usados em análise de sensibilidade, mas o cenário-base
    # mantém escores resumidos para reduzir dimensionalidade e tornar o fluxo interpretável.
    score_cols = ["phq9_total", "gad7_total", "idate_estado_total"]
    target_cols = ["patient_id", "prioridade_referencia", "prioridade_referencia_codigo", "urgent_rule_triggered"]
    origin_columns = [
        marker_column("marcadores_origem_", marker, field)
        for marker in MARKER_NAMES
        for field in MARKER_FEATURE_FIELDS
    ]
    extracted_columns = [
        marker_column("marcadores_extraidos_", marker, field)
        for marker in MARKER_NAMES
        for field in MARKER_FEATURE_FIELDS
    ]
    missing_origin = sorted(set(origin_columns) - set(merged.columns))
    missing_extracted = sorted(set(extracted_columns) - set(merged.columns))
    if missing_origin or missing_extracted:
        raise ValueError(
            "Os conjuntos de marcadores não respeitam o contrato simétrico. "
            f"Origem ausente: {missing_origin}; extraído ausente: {missing_extracted}"
        )
    canonical_columns = [f"marker_{marker}_{field}" for marker in MARKER_NAMES for field in MARKER_FEATURE_FIELDS]

    base = merged[target_cols + profile_cols + score_cols].copy()
    upper_bound = merged[target_cols + profile_cols + score_cols + origin_columns].copy()
    operational = merged[target_cols + profile_cols + score_cols + extracted_columns].copy()
    upper_bound = upper_bound.rename(columns=dict(zip(origin_columns, canonical_columns)))
    operational = operational.rename(columns=dict(zip(extracted_columns, canonical_columns)))

    # Opção de estresse: inserir ausência em dados observáveis; nunca em prioridade_referencia.
    from .quality import apply_missingness_scenario

    protected = target_cols
    seed = int(config["simulation"]["base_seed"])
    base = apply_missingness_scenario(base, config, seed, protected)
    upper_bound = apply_missingness_scenario(upper_bound, config, seed, protected)
    operational = apply_missingness_scenario(operational, config, seed, protected)

    return {
        "01_estruturados_escores": base,
        "02_limite_superior_marcadores_origem": upper_bound,
        "03_operacional_marcadores_extraidos": operational,
    }

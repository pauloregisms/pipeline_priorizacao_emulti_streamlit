"""Verificações de plausibilidade, consistência e rastreabilidade da base sintética."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def cronbach_alpha(items: pd.DataFrame) -> float:
    """Calcula alfa de Cronbach para inspeção descritiva da consistência interna."""
    values = items.to_numpy(dtype=float)
    if values.shape[1] < 2:
        return float("nan")
    item_variances = values.var(axis=0, ddof=1)
    total_variance = values.sum(axis=1).var(ddof=1)
    if total_variance <= 0:
        return float("nan")
    n_items = values.shape[1]
    return float(n_items / (n_items - 1) * (1 - item_variances.sum() / total_variance))


def validate_profile_ranges(profiles: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Gera uma tabela de checagens estruturais dos perfis sintéticos."""
    simulations = config["simulation"]
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, details: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "details": details})

    add_check(
        "idade_dentro_do_intervalo",
        profiles["age_years"].between(simulations["adult_age_min"], simulations["adult_age_max"]).all(),
        f"Intervalo esperado: {simulations['adult_age_min']}--{simulations['adult_age_max']}",
    )
    add_check(
        "vulnerabilidade_entre_0_e_1",
        profiles["social_vulnerability"].between(0, 1).all(),
        "O índice de vulnerabilidade deve estar normalizado.",
    )
    add_check(
        "planejamento_requer_ideacao",
        ((profiles["marcadores_origem_planejamento_suicida"] <= profiles["marcadores_origem_ideacao_suicida"]).all()),
        "Não deve existir planejamento sem ideação no cenário-base.",
    )
    add_check(
        "autoagressao_requer_planejamento",
        ((profiles["marcadores_origem_autoagressao_iminente"] <= profiles["marcadores_origem_planejamento_suicida"]).all()),
        "Não deve existir autoagressão iminente sem planejamento no cenário-base.",
    )
    add_check(
        "identificadores_unicos",
        profiles["patient_id"].is_unique,
        "Cada indivíduo sintético deve possuir identificador único.",
    )
    return pd.DataFrame(checks), {"n_records": int(len(profiles)), "n_failed": int((~pd.DataFrame(checks)["passed"]).sum())}


def validate_psychometrics(psychometrics: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verifica faixas, somas e consistência interna de escalas simuladas."""
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, details: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "details": details})

    phq_cols = [column for column in psychometrics if column.startswith("phq9_item_")]
    gad_cols = [column for column in psychometrics if column.startswith("gad7_item_")]
    stai_scored_cols = [column for column in psychometrics if column.startswith("idate_estado_item_") and column.endswith("_score")]

    add_check("phq9_itens_0_3", psychometrics[phq_cols].apply(lambda s: s.between(0, 3).all()).all(), "Itens PHQ-9 devem variar de 0 a 3.")
    add_check("gad7_itens_0_3", psychometrics[gad_cols].apply(lambda s: s.between(0, 3).all()).all(), "Itens GAD-7 devem variar de 0 a 3.")
    add_check("idate_itens_1_4", psychometrics[stai_scored_cols].apply(lambda s: s.between(1, 4).all()).all(), "Itens pontuados do IDATE devem variar de 1 a 4.")
    add_check("phq9_total_0_27", psychometrics["phq9_total"].between(0, 27).all(), "Total PHQ-9 deve variar de 0 a 27.")
    add_check("gad7_total_0_21", psychometrics["gad7_total"].between(0, 21).all(), "Total GAD-7 deve variar de 0 a 21.")
    add_check("idate_total_20_80", psychometrics["idate_estado_total"].between(20, 80).all(), "Total IDATE-Estado deve variar de 20 a 80.")
    add_check("phq9_total_corresponde_a_soma", (psychometrics[phq_cols].sum(axis=1) == psychometrics["phq9_total"]).all(), "Total deve ser derivado dos itens.")
    add_check("gad7_total_corresponde_a_soma", (psychometrics[gad_cols].sum(axis=1) == psychometrics["gad7_total"]).all(), "Total deve ser derivado dos itens.")
    add_check("idate_total_corresponde_a_soma", (psychometrics[stai_scored_cols].sum(axis=1) == psychometrics["idate_estado_total"]).all(), "Total deve ser derivado dos itens pontuados.")

    summary = {
        "cronbach_alpha": {
            "phq9": cronbach_alpha(psychometrics[phq_cols]),
            "gad7": cronbach_alpha(psychometrics[gad_cols]),
            "idate_estado": cronbach_alpha(psychometrics[stai_scored_cols]),
        },
        "correlations": psychometrics[["phq9_total", "gad7_total", "idate_estado_total"]].corr().round(4).to_dict(),
        "n_failed": int((~pd.DataFrame(checks)["passed"]).sum()),
    }
    return pd.DataFrame(checks), summary


def apply_missingness_scenario(frame: pd.DataFrame, config: dict[str, Any], seed: int, protected_columns: list[str]) -> pd.DataFrame:
    """Introduz valores ausentes somente em cenários de robustez pré-especificados.

    Colunas protegidas, como identificador e rótulo de referência, nunca sofrem alteração.
    """
    rate = float(config["simulation"].get("missingness_rate", 0.0))
    if rate <= 0:
        return frame.copy()
    rng = np.random.default_rng(seed + 5000)
    result = frame.copy()
    candidates = [column for column in result.columns if column not in protected_columns]
    for column in candidates:
        # Não adicionar ausência em variáveis textuais longas; o cenário se concentra
        # em entradas tabulares observáveis do classificador.
        if result[column].dtype == object and column not in {"gender_category", "education"}:
            continue
        mask = rng.random(len(result)) < rate
        result.loc[mask, column] = np.nan
    return result

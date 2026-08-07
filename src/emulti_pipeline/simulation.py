"""Geração probabilística dos perfis e dos instrumentos psicométricos.

O módulo implementa o mecanismo estrutural da prova de conceito. Os parâmetros do
arquivo de configuração são deliberadamente separados do código para que possam ser
substituídos por evidência de literatura ou consenso de especialistas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .markers import MARKER_NAMES, flatten_markers
from .utils import sigmoid

MARKERS = list(MARKER_NAMES)


@dataclass(frozen=True)
class SimulationResult:
    """Resultado de uma etapa de simulação com dados e metadados."""

    data: pd.DataFrame
    metadata: dict[str, Any]


def _sample_categories(
    rng: np.random.Generator,
    probabilities: dict[str, float],
    n_records: int,
) -> np.ndarray:
    labels = list(probabilities.keys())
    probs = np.asarray(list(probabilities.values()), dtype=float)
    probs = probs / probs.sum()
    return rng.choice(labels, size=n_records, p=probs)


def _normalize_01(values: np.ndarray) -> np.ndarray:
    minimum = np.nanmin(values)
    maximum = np.nanmax(values)
    if maximum - minimum < 1e-12:
        return np.full_like(values, 0.5, dtype=float)
    return (values - minimum) / (maximum - minimum)


def _bernoulli_from_logit(
    rng: np.random.Generator,
    linear_predictor: np.ndarray,
) -> np.ndarray:
    return rng.binomial(1, sigmoid(linear_predictor)).astype(int)


def generate_profiles(config: dict[str, Any], seed: int) -> SimulationResult:
    """Gera atributos estruturados, gravidade latente e marcadores de origem.

    A gravidade latente ``gravidade_latente_auditoria`` é preservada apenas para auditoria do gerador.
    Ela não será incluída nos conjuntos analíticos destinados aos classificadores.
    """
    simulation = config["simulation"]
    population = config["population"]
    vulnerability_cfg = config["vulnerability"]
    n_records = int(simulation["n_records"])
    rng = np.random.default_rng(seed)

    patient_id = [f"SYN-{seed}-{index:06d}" for index in range(1, n_records + 1)]
    age = np.clip(rng.normal(loc=42, scale=14, size=n_records), simulation["adult_age_min"], simulation["adult_age_max"])
    age = np.rint(age).astype(int)
    gender = _sample_categories(rng, population["gender_probabilities"], n_records)
    education = _sample_categories(rng, population["education_probabilities"], n_records)
    income = rng.lognormal(
        mean=float(population["income_lognormal_meanlog"]),
        sigma=float(population["income_lognormal_sigma"]),
        size=n_records,
    )

    # Os determinantes sociais abaixo são gerados antes da gravidade latente,
    # pois integram o índice de vulnerabilidade estrutural do cenário.
    education_low = (education == "fundamental_ou_menos").astype(int)
    age_centered = (age - np.mean(age)) / np.std(age)
    food_insecurity = _bernoulli_from_logit(rng, -0.85 + 0.65 * education_low - 0.12 * age_centered)
    poor_housing = _bernoulli_from_logit(rng, -1.10 + 0.55 * education_low + 0.80 * food_insecurity)
    income_normalized = _normalize_01(income)

    weights_cfg = vulnerability_cfg["weights"]
    weights = np.asarray(
        [
            weights_cfg["renda_baixa"],
            weights_cfg["escolaridade_baixa"],
            weights_cfg["inseguranca_alimentar"],
            weights_cfg["moradia_precaria"],
        ],
        dtype=float,
    )
    if np.any(weights < 0) or not np.isclose(weights.sum(), 1.0):
        raise ValueError("Os pesos de vulnerabilidade devem ser não negativos e somar 1.")

    vulnerability = (
        weights[0] * (1 - income_normalized)
        + weights[1] * education_low
        + weights[2] * food_insecurity
        + weights[3] * poor_housing
    )
    vulnerability = np.clip(vulnerability, 0, 1)

    # A gravidade latente é um construto latente do gerador. O termo aleatório evita relação
    # perfeitamente determinística entre vulnerabilidade e sofrimento psíquico.
    gravidade_latente = np.clip(rng.normal(0, 1, n_records) + 0.75 * (vulnerability - vulnerability.mean()), -3.5, 3.5)

    # Condições clínicas e utilização de serviços, todas condicionais aos dados estruturados, à vulnerabilidade social e à gravidade latente.
    mental_health_history = _bernoulli_from_logit(rng, -0.45 + 0.50 * vulnerability + 0.85 * gravidade_latente)
    chronic_condition = _bernoulli_from_logit(rng, -0.40 + 0.42 * (age > 50).astype(int) + 0.18 * vulnerability)
    recent_service_contact = _bernoulli_from_logit(rng, -0.20 + 0.40 * mental_health_history + 0.50 * gravidade_latente)
    previous_admission = _bernoulli_from_logit(rng, -2.55 + 0.85 * mental_health_history + 0.60 * gravidade_latente)
    substance_use = _bernoulli_from_logit(rng, -2.05 + 0.35 * vulnerability + 0.55 * gravidade_latente)

    # Marcadores clínicos de origem marcadores_origem. A lógica de dependência cria combinações
    # plausíveis; por exemplo, planejamento é gerado apenas se existe ideação atual.
    suicidal_ideation = _bernoulli_from_logit(rng, -3.65 + 1.55 * gravidade_latente + 0.25 * vulnerability)
    suicide_planning = np.where(
        suicidal_ideation == 1,
        _bernoulli_from_logit(rng, -1.65 + 0.85 * gravidade_latente),
        0,
    )
    imminent_self_harm = np.where(
        suicide_planning == 1,
        _bernoulli_from_logit(rng, -2.10 + 0.90 * gravidade_latente),
        0,
    )
    violence_risk = _bernoulli_from_logit(rng, -4.30 + 1.15 * gravidade_latente + 0.30 * substance_use)
    psychotic_symptoms = _bernoulli_from_logit(rng, -4.10 + 1.30 * gravidade_latente)
    recent_worsening = _bernoulli_from_logit(rng, -1.55 + 0.90 * gravidade_latente + 0.20 * vulnerability)
    low_social_support = _bernoulli_from_logit(rng, -0.75 + 1.00 * vulnerability)

    # Comprometimento funcional é ordinal: 0=ausente, 1=leve, 2=moderado, 3=importante.
    functional_signal = 0.85 * gravidade_latente + 0.35 * vulnerability + rng.normal(0, 0.70, n_records)
    functional_impairment = np.digitize(functional_signal, bins=[-0.65, 0.25, 1.15], right=False).astype(int)

    raw_markers = {
        "ideacao_suicida": suicidal_ideation,
        "planejamento_suicida": suicide_planning,
        "autoagressao_iminente": imminent_self_harm,
        "risco_violencia": violence_risk,
        "sintomas_psicoticos": psychotic_symptoms,
        "uso_problematico_substancias": substance_use,
        "internacao_previa": previous_admission,
        "agravamento_recente": recent_worsening,
        "suporte_social_baixo": low_social_support,
        "comprometimento_funcional": (functional_impairment > 0).astype(int),
    }
    severity_codes = {
        "ideacao_suicida": 2 * suicidal_ideation,
        "planejamento_suicida": 3 * suicide_planning,
        "autoagressao_iminente": 3 * imminent_self_harm,
        "risco_violencia": 3 * violence_risk,
        "sintomas_psicoticos": np.where(psychotic_symptoms == 1, np.where(functional_impairment >= 3, 3, 2), 0),
        "uso_problematico_substancias": 2 * substance_use,
        "internacao_previa": previous_admission,
        "agravamento_recente": 2 * recent_worsening,
        "suporte_social_baixo": low_social_support,
        "comprometimento_funcional": functional_impairment,
    }

    # Os marcadores de origem usam o mesmo contrato dos marcadores extraídos. A
    # negação indica menção negativa explícita; ausência sem negação continua sendo
    # uma possibilidade distinta. Algumas menções são remotas, incertas ou referentes
    # a terceiros para testar qualificadores textuais sem convertê-los em atalhos de prioridade.
    qualified_rows: list[dict[str, dict[str, Any]]] = []
    for row_index in range(n_records):
        marker_row: dict[str, dict[str, Any]] = {}
        for marker in MARKER_NAMES:
            present = int(raw_markers[marker][row_index])
            negated = int(present == 0 and rng.random() < 0.70)
            remote_present = int(marker == "internacao_previa" and present == 1)
            if marker == "ideacao_suicida" and present == 0 and rng.random() < 0.08:
                remote_present = 1
                negated = 1
            if marker == "internacao_previa":
                temporality = "remoto" if (present or negated) else "nao_especificado"
            elif present or negated:
                temporality = "atual"
            else:
                temporality = "nao_especificado"
            certainty = "incerto" if present and marker not in {"planejamento_suicida", "autoagressao_iminente", "risco_violencia"} and rng.random() < 0.05 else "afirmado"
            experiencer = "terceiro" if present and marker in {"sintomas_psicoticos", "uso_problematico_substancias"} and rng.random() < 0.03 else "paciente"
            severity_code = int(severity_codes[marker][row_index])
            if severity_code == 0:
                severity = "ausente"
            elif severity_code == 1:
                severity = "leve"
            elif severity_code == 2:
                severity = "moderado"
            elif marker == "comprometimento_funcional":
                severity = "importante"
            else:
                severity = "alto"
            marker_row[marker] = {
                "present": present,
                "negated": negated,
                "remote_present": remote_present,
                "temporality": temporality,
                "severity": severity,
                "severity_code": severity_code,
                "certainty": certainty,
                "experiencer": experiencer,
                "evidence": "",
            }
        qualified_rows.append(marker_row)

    qualified_columns: dict[str, list[Any]] = {}
    for marker_row in qualified_rows:
        flattened = flatten_markers(marker_row, "marcadores_origem_")
        for column, value in flattened.items():
            qualified_columns.setdefault(column, []).append(value)

    profiles = pd.DataFrame(
        {
            "patient_id": patient_id,
            "seed": seed,
            "age_years": age,
            "gender_category": gender,
            "education": education,
            "income_brl": np.round(income, 2),
            "income_normalized": np.round(income_normalized, 6),
            "food_insecurity": food_insecurity,
            "poor_housing": poor_housing,
            "social_vulnerability": np.round(vulnerability, 6),
            "gravidade_latente_auditoria": np.round(gravidade_latente, 6),
            "mental_health_history": mental_health_history,
            "chronic_condition": chronic_condition,
            "recent_service_contact": recent_service_contact,
            "marcadores_origem_internacao_previa": previous_admission,
            "marcadores_origem_uso_problematico_substancias": substance_use,
            "marcadores_origem_ideacao_suicida": suicidal_ideation,
            "marcadores_origem_planejamento_suicida": suicide_planning,
            "marcadores_origem_autoagressao_iminente": imminent_self_harm,
            "marcadores_origem_risco_violencia": violence_risk,
            "marcadores_origem_sintomas_psicoticos": psychotic_symptoms,
            "marcadores_origem_agravamento_recente": recent_worsening,
            "marcadores_origem_suporte_social_baixo": low_social_support,
            "marcadores_origem_comprometimento_funcional": functional_impairment,
            **qualified_columns,
        }
    )

    # Metadados permitem registrar os parâmetros e a semântica das codificações.
    metadata = {
        "seed": seed,
        "n_records": n_records,
        "marker_semantics": {
            "schema": "marker-schema-v2",
            "fields": ["present", "negated", "remote_present", "temporality", "severity", "severity_code", "certainty", "experiencer"],
            "legacy_aliases": "marcadores_origem_<marcador> preservado temporariamente como alias de presença/severidade",
        },
        "warning": "Parâmetros ilustrativos; calibrar antes do experimento definitivo.",
    }
    return SimulationResult(profiles, metadata)


def _sample_ordinal_items(
    rng: np.random.Generator,
    latent_signal: np.ndarray,
    n_items: int,
    thresholds: list[float],
    discrimination: float,
    direction: float = 1.0,
) -> np.ndarray:
    """Gera respostas ordinais com um modelo graduado simplificado.

    O código não pretende estimar parâmetros psicométricos reais. Ele produz itens
    coerentes com um traço latente e permite calcular totais somente depois da
    geração das respostas.
    """
    n = latent_signal.shape[0]
    n_categories = len(thresholds) + 1
    responses = np.zeros((n, n_items), dtype=int)
    base_thresholds = np.asarray(thresholds, dtype=float)

    for item_index in range(n_items):
        item_difficulty = rng.normal(0, 0.20)
        signal = direction * discrimination * latent_signal + rng.normal(0, 0.35, n) - item_difficulty
        cumulative = sigmoid(signal[:, None] - base_thresholds[None, :])
        # P(Y=0)=1-P(Y>=1); P(Y=c)=P(Y>=c)-P(Y>=c+1); P(Y=max)=P(Y>=max)
        probabilities = np.empty((n, n_categories), dtype=float)
        probabilities[:, 0] = 1 - cumulative[:, 0]
        for category in range(1, n_categories - 1):
            probabilities[:, category] = cumulative[:, category - 1] - cumulative[:, category]
        probabilities[:, -1] = cumulative[:, -1]
        probabilities = np.clip(probabilities, 1e-8, None)
        probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
        random_values = rng.random(n)
        responses[:, item_index] = (random_values[:, None] > np.cumsum(probabilities, axis=1)).sum(axis=1)
    return responses


def simulate_psychometrics(
    profiles: pd.DataFrame,
    config: dict[str, Any],
    seed: int,
) -> SimulationResult:
    """Simula PHQ-9, GAD-7 e IDATE-Estado item a item.

    Os itens do IDATE são identificados apenas por número, sem reproduzir texto do
    instrumento. Os itens definidos como reversos têm sua pontuação invertida antes
    do cálculo do total, preservando a faixa 20--80.
    """
    rng = np.random.default_rng(seed + 1000)
    settings = config["psychometrics"]
    n = len(profiles)
    u = profiles["gravidade_latente_auditoria"].to_numpy(dtype=float)
    v = profiles["social_vulnerability"].to_numpy(dtype=float)
    service = profiles["recent_service_contact"].to_numpy(dtype=float)
    marker_effect = (
        0.55 * profiles["marcadores_origem_agravamento_recente"].to_numpy(dtype=float)
        + 0.60 * profiles["marcadores_origem_uso_problematico_substancias"].to_numpy(dtype=float)
        + 0.45 * (profiles["marcadores_origem_comprometimento_funcional"].to_numpy(dtype=float) >= 2)
    )

    # O sinal latente é compartilhado parcialmente entre as escalas para criar
    # associações plausíveis, mas cada instrumento recebe perturbação específica.
    depression_signal = u + 0.35 * v + 0.18 * service + marker_effect + rng.normal(0, 0.25, n)
    anxiety_signal = 0.85 * u + 0.25 * v + 0.10 * service + 0.50 * marker_effect + rng.normal(0, 0.30, n)

    phq_cfg = settings["phq9"]
    gad_cfg = settings["gad7"]
    stai_cfg = settings["state_anxiety"]

    phq_items = _sample_ordinal_items(
        rng,
        depression_signal,
        int(phq_cfg["n_items"]),
        list(phq_cfg["thresholds"]),
        float(phq_cfg["discrimination"]),
    )
    gad_items = _sample_ordinal_items(
        rng,
        anxiety_signal,
        int(gad_cfg["n_items"]),
        list(gad_cfg["thresholds"]),
        float(gad_cfg["discrimination"]),
    )

    # IDATE: gera respostas brutas 1..4. Para itens reversos, maior ansiedade
    # produz respostas menores na forma bruta; a pontuação é invertida depois.
    stai_n_items = int(stai_cfg["n_items"])
    reverse_indices = {int(index) - 1 for index in stai_cfg["reverse_scored_items"]}
    stai_raw = np.zeros((n, stai_n_items), dtype=int)
    for item_index in range(stai_n_items):
        direction = -1.0 if item_index in reverse_indices else 1.0
        item_zero_based = _sample_ordinal_items(
            rng,
            anxiety_signal,
            1,
            list(stai_cfg["thresholds"]),
            float(stai_cfg["discrimination"]),
            direction=direction,
        )[:, 0]
        stai_raw[:, item_index] = item_zero_based + 1  # transforma 0..3 em 1..4

    stai_scored = stai_raw.copy()
    for item_index in reverse_indices:
        stai_scored[:, item_index] = 5 - stai_scored[:, item_index]

    output: dict[str, Any] = {"patient_id": profiles["patient_id"].to_numpy()}
    for item_index in range(phq_items.shape[1]):
        output[f"phq9_item_{item_index + 1:02d}"] = phq_items[:, item_index]
    for item_index in range(gad_items.shape[1]):
        output[f"gad7_item_{item_index + 1:02d}"] = gad_items[:, item_index]
    for item_index in range(stai_raw.shape[1]):
        output[f"idate_estado_item_{item_index + 1:02d}_raw"] = stai_raw[:, item_index]
        output[f"idate_estado_item_{item_index + 1:02d}_score"] = stai_scored[:, item_index]

    output["phq9_total"] = phq_items.sum(axis=1)
    output["gad7_total"] = gad_items.sum(axis=1)
    output["idate_estado_total"] = stai_scored.sum(axis=1)
    output["phq9_band"] = pd.cut(
        output["phq9_total"], bins=[-1, 4, 9, 14, 19, 27], labels=["minimo", "leve", "moderado", "moderadamente_grave", "grave"]
    ).astype(str)
    output["gad7_band"] = pd.cut(
        output["gad7_total"], bins=[-1, 4, 9, 14, 21], labels=["minimo", "leve", "moderado", "grave"]
    ).astype(str)

    psychometrics = pd.DataFrame(output)
    metadata = {
        "seed": seed + 1000,
        "idate_reverse_items": sorted(index + 1 for index in reverse_indices),
        "score_ranges": {"phq9_total": [0, 27], "gad7_total": [0, 21], "idate_estado_total": [20, 80]},
    }
    return SimulationResult(psychometrics, metadata)

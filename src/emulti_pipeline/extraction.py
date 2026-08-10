"""Extração independente de marcadores e fábrica de provedores de PLN."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .markers import (
    MARKER_ALL_FIELDS,
    MARKER_NAMES,
    flatten_markers,
    marker_column,
    normalize_marker,
)


MARKER_ONTOLOGY: dict[str, dict[str, list[str]]] = {
    "ideacao_suicida": {
        "positive_patterns": [r"pensamentos de morte", r"ideação suicida", r"ideacao suicida"],
        "negative_patterns": [r"nega ideação suicida", r"nega ideacao suicida", r"sem ideação", r"sem ideacao"],
    },
    "planejamento_suicida": {
        "positive_patterns": [r"planejamento de autoagressão", r"planejamento de autoagressao", r"planejamento suicida"],
        "negative_patterns": [r"sem planejamento", r"nega planejamento"],
    },
    "autoagressao_iminente": {
        "positive_patterns": [r"risco iminente de autoagressão", r"risco iminente de autoagressao", r"autoagressão iminente", r"autoagressao iminente"],
        "negative_patterns": [r"nega (?:risco iminente de )?autoagress", r"sem risco iminente"],
    },
    "risco_violencia": {
        "positive_patterns": [r"risco de comportamento agressivo", r"risco de violência", r"risco de violencia"],
        "negative_patterns": [r"nega risco de violência", r"nega risco de violencia"],
    },
    "sintomas_psicoticos": {
        "positive_patterns": [r"percepção alterada da realidade", r"percepcao alterada da realidade", r"ideias de referência", r"ideias de referencia", r"sintomas psicóticos", r"sintomas psicoticos"],
        "negative_patterns": [r"nega sintomas psicóticos", r"nega sintomas psicoticos"],
    },
    "uso_problematico_substancias": {
        "positive_patterns": [r"uso de álcool ou outras substâncias com prejuízo", r"uso de alcool ou outras substancias com prejuizo", r"uso problemático de substâncias", r"uso problematico de substancias"],
        "negative_patterns": [r"nega uso problemático", r"nega uso problematico"],
    },
    "internacao_previa": {
        "positive_patterns": [r"internação prévia", r"internacao previa"],
        "negative_patterns": [r"nega internação prévia", r"nega internacao previa"],
    },
    "agravamento_recente": {
        "positive_patterns": [r"piora recente", r"agravamento recente", r"piora dos sintomas nas últimas semanas", r"piora dos sintomas nas ultimas semanas"],
        "negative_patterns": [r"sem (?:piora|agravamento) recente", r"nega (?:piora|agravamento) recente"],
    },
    "suporte_social_baixo": {
        "positive_patterns": [r"rede de apoio limitada", r"suporte social limitado"],
        "negative_patterns": [r"rede de apoio disponível", r"rede de apoio disponivel"],
    },
    "comprometimento_funcional": {
        "positive_patterns": [r"dificuldade leve para manter", r"dificuldade moderada para manter", r"importante comprometimento para atividades"],
        "negative_patterns": [r"funcionalidade preservada"],
    },
}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n", text.lower()) if part.strip()]


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) is not None for pattern in patterns)


def _temporal_label(sentence: str) -> str:
    if re.search(r"há dois anos|ha dois anos|prévia|previa|remoto|passado|anterior", sentence):
        return "remoto"
    if re.search(r"atual|atualmente|no momento|nesta semana|recent[e]?|últimas semanas|ultimas semanas", sentence):
        return "atual"
    return "nao_especificado"


def _severity_label(marker: str, sentence: str, present: int) -> tuple[str, int]:
    if not present:
        return "ausente", 0
    if marker == "comprometimento_funcional":
        if "importante comprometimento" in sentence:
            return "importante", 3
        if "dificuldade moderada" in sentence:
            return "moderado", 2
        if "dificuldade leve" in sentence:
            return "leve", 1
    if re.search(r"iminente|intenso|importante|grave", sentence):
        return "alto", 3
    if re.search(r"moderad", sentence):
        return "moderado", 2
    if re.search(r"leve", sentence):
        return "leve", 1
    return "leve", 1


def _certainty_label(sentence: str) -> str:
    return "incerto" if re.search(r"possivelmente|pode|suspeita|incerto", sentence) else "afirmado"


def _experiencer_label(sentence: str) -> str:
    return "terceiro" if re.search(r"mãe|mae|pai|um familiar|familiar apresenta|família apresenta", sentence) else "paciente"


@dataclass
class RuleBasedClinicalExtractor:
    """Linha de base auditável por dicionário, negação e qualificadores."""

    ontology_version: str = "ontology_v1"
    extractor_id: str = "rule-dictionary-qualified-v1"
    flip_rate: float = 0.0
    seed: int = 0

    def extract(self, narrative_frame: pd.DataFrame, *, seed_offset: int = 0) -> pd.DataFrame:
        required = {"patient_id", "narrativa_clinica"}
        missing = required - set(narrative_frame.columns)
        if missing:
            raise ValueError(f"Narrativas sem colunas necessárias: {sorted(missing)}")
        rng = np.random.default_rng(self.seed + seed_offset)
        rows: list[dict[str, Any]] = []

        for _, record in narrative_frame.iterrows():
            sentence_list = _sentences(str(record["narrativa_clinica"]))
            markers: dict[str, dict[str, Any]] = {}
            for marker, specification in MARKER_ONTOLOGY.items():
                positives = [s for s in sentence_list if _contains_any(s, specification["positive_patterns"]) and not _contains_any(s, specification["negative_patterns"])]
                negatives = [s for s in sentence_list if _contains_any(s, specification["negative_patterns"])]
                positive_current = next((s for s in positives if _temporal_label(s) != "remoto"), None)
                positive_remote = next((s for s in positives if _temporal_label(s) == "remoto"), None)
                negative_current = next((s for s in negatives if _temporal_label(s) != "remoto"), None)

                if positive_current is not None:
                    present, negated = 1, 0
                    evidence = positive_current
                    temporality = _temporal_label(positive_current)
                elif negative_current is not None:
                    present, negated = 0, 1
                    evidence = negative_current
                    temporality = _temporal_label(negative_current)
                elif positive_remote is not None:
                    present, negated = 1, 0
                    evidence = positive_remote
                    temporality = "remoto"
                else:
                    present, negated = 0, 0
                    evidence = ""
                    temporality = "nao_especificado"

                if self.flip_rate > 0 and rng.random() < self.flip_rate:
                    present = 1 - present
                    negated = 0 if present else negated
                severity, severity_code = _severity_label(marker, evidence, present)
                values = {
                    "present": present,
                    "negated": negated,
                    "remote_present": int(positive_remote is not None),
                    "temporality": temporality,
                    "severity": severity,
                    "severity_code": severity_code,
                    "certainty": _certainty_label(evidence),
                    "experiencer": _experiencer_label(evidence),
                    "evidence": " | ".join(filter(None, [evidence, positive_remote if positive_remote != evidence else None])),
                }
                markers[marker] = normalize_marker(marker, values)

            rows.append(
                {
                    "patient_id": record["patient_id"],
                    "extractor_id": self.extractor_id,
                    "ontology_version": self.ontology_version,
                    "extraction_status": "success",
                    "retry_count": 0,
                    **flatten_markers(markers, "marcadores_extraidos_"),
                }
            )
        return pd.DataFrame(rows)


def create_clinical_extractor(extraction_config: Mapping[str, Any], *, seed: int = 0):
    """Instancia extrator local ou por LLM conforme o YAML."""
    provider = str(extraction_config.get("provider", "rules")).strip().lower()
    if provider == "rules":
        return RuleBasedClinicalExtractor(
            ontology_version=str(extraction_config.get("ontology_version", "ontology_v2")),
            extractor_id=str(extraction_config.get("extractor_id", "rule-dictionary-qualified-v2")),
            flip_rate=float(extraction_config.get("flip_rate", 0.0)),
            seed=seed,
        )
    if provider == "llm":
        from .extraction_providers.llm import LLMClinicalExtractor

        llm_config = extraction_config.get("llm", {})
        if not isinstance(llm_config, Mapping):
            raise ValueError("O bloco extraction.llm deve ser um dicionário YAML.")
        temperature = llm_config.get("temperature", 0.0)
        return LLMClinicalExtractor(
            llm_configuration=llm_config,
            extractor_id=str(
                llm_config.get(
                    "extractor_id",
                    extraction_config.get("extractor_id", "llm-extractor-v1"),
                )
            ),
            ontology_version=str(extraction_config.get("ontology_version", "ontology_v2")),
            prompt_version=str(extraction_config.get("prompt_version", "extracao_marcadores_v1")),
            temperature=None if temperature is None else float(temperature),
            max_output_tokens=int(llm_config.get("max_output_tokens", 2200)),
            max_retries=int(extraction_config.get("max_retries", 2)),
            retry_backoff_seconds=float(llm_config.get("retry_backoff_seconds", 2.0)),
            base_seed=seed,
        )
    raise ValueError(f"Provedor de extração desconhecido: {provider!r}. Use 'rules' ou 'llm'.")


def extraction_reference_table(profiles: pd.DataFrame) -> pd.DataFrame:
    """Seleciona os marcadores de origem no mesmo esquema semântico do extrator."""
    result = pd.DataFrame({"patient_id": profiles["patient_id"]})
    for marker in MARKER_NAMES:
        for field in MARKER_ALL_FIELDS:
            source = marker_column("marcadores_origem_", marker, field)
            target = marker_column("marcadores_origem_", marker, field)
            if source in profiles:
                result[target] = profiles[source]
            elif field == "present" and f"marcadores_origem_{marker}" in profiles:
                result[target] = (pd.to_numeric(profiles[f"marcadores_origem_{marker}"], errors="coerce").fillna(0) > 0).astype(int)
            elif field in {"negated", "remote_present", "severity_code"}:
                result[target] = 0
            elif field == "evidence":
                result[target] = ""
            elif field == "temporality":
                result[target] = "nao_especificado"
            elif field == "severity":
                result[target] = "ausente"
            elif field == "certainty":
                result[target] = "afirmado"
            elif field == "experiencer":
                result[target] = "paciente"
    return result

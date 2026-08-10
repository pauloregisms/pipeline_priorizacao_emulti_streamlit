"""Extrator clínico por LLM independente de fornecedor."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import pandas as pd

from ..llm import StructuredLLMClient
from ..markers import (
    CERTAINTY_VALUES,
    EXPERIENCER_VALUES,
    MARKER_NAMES,
    SEVERITY_VALUES,
    TEMPORALITY_VALUES,
    flatten_markers,
    normalize_marker,
)
from ..utils import json_hash


_MARKER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "present": {"type": "integer", "enum": [0, 1]},
        "negated": {"type": "integer", "enum": [0, 1]},
        "remote_present": {"type": "integer", "enum": [0, 1]},
        "temporality": {"type": "string", "enum": sorted(TEMPORALITY_VALUES)},
        "severity": {"type": "string", "enum": sorted(SEVERITY_VALUES)},
        "severity_code": {"type": "integer", "enum": [0, 1, 2, 3]},
        "certainty": {"type": "string", "enum": sorted(CERTAINTY_VALUES)},
        "experiencer": {"type": "string", "enum": sorted(EXPERIENCER_VALUES)},
        "evidence": {"type": "string"},
    },
    "required": [
        "present",
        "negated",
        "remote_present",
        "temporality",
        "severity",
        "severity_code",
        "certainty",
        "experiencer",
        "evidence",
    ],
    "additionalProperties": False,
}

EXTRACTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "markers": {
            "type": "object",
            "properties": {marker: _MARKER_SCHEMA for marker in MARKER_NAMES},
            "required": list(MARKER_NAMES),
            "additionalProperties": False,
        }
    },
    "required": ["markers"],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTION = """Você extrai informações exclusivamente de uma narrativa clínica sintética.
Não use conhecimento externo, não complete lacunas e não infira prioridade, diagnóstico ou conduta.
Para cada marcador da ontologia, registre presença, negação, temporalidade, severidade, certeza,
experienciador e o menor trecho literal que sustenta a saída. Se não houver evidência, use present=0,
negated=0, remote_present=0, temporality=nao_especificado, severity=ausente, severity_code=0,
certainty=afirmado, experiencer=paciente e evidence vazio. Retorne somente o JSON solicitado."""


class LLMClinicalExtractor:
    """Extrai marcadores usando apenas a narrativa e o LLM declarado no YAML."""

    def __init__(
        self,
        *,
        llm_configuration: Mapping[str, Any],
        extractor_id: str,
        ontology_version: str,
        prompt_version: str,
        temperature: float | None = 0.0,
        max_output_tokens: int = 2200,
        max_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        base_seed: int = 0,
        llm_client: StructuredLLMClient | None = None,
        completion_callable: Callable[..., Any] | None = None,
        api_key: str | None = None,
    ) -> None:
        if not extractor_id.strip():
            raise ValueError("extractor_id não pode ser vazio.")
        self.extractor_id = extractor_id
        self.ontology_version = ontology_version
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.max_output_tokens = int(max_output_tokens)
        self.max_retries = int(max_retries)
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self.base_seed = int(base_seed)
        self.audit_records: list[dict[str, Any]] = []
        self._llm = llm_client or StructuredLLMClient(
            llm_configuration,
            completion_callable=completion_callable,
            api_key=api_key,
        )
        self.model_id = self._llm.model_id
        self.backend = self._llm.backend

    @staticmethod
    def _prompt(narrative: str) -> str:
        return (
            "Extraia a ontologia fechada abaixo da narrativa sintética.\n"
            f"Marcadores: {', '.join(MARKER_NAMES)}.\n"
            "Narrativa (única fonte permitida):\n"
            f"{narrative}"
        )

    def _extract_one(self, patient_id: str, narrative: str, seed: int) -> dict[str, Any]:
        prompt = self._prompt(narrative)
        prompt_hash = json_hash(
            {
                "system_instruction": SYSTEM_INSTRUCTION,
                "prompt": prompt,
                "response_schema": EXTRACTION_RESPONSE_SCHEMA,
                "prompt_version": self.prompt_version,
            }
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            request_timestamp = datetime.now(timezone.utc).isoformat()
            try:
                result = self._llm.generate_json(
                    system_instruction=SYSTEM_INSTRUCTION,
                    prompt=prompt,
                    response_schema=EXTRACTION_RESPONSE_SCHEMA,
                    schema_name="emulti_extraction",
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    seed=seed,
                )
                markers = result.data.get("markers")
                if not isinstance(markers, Mapping):
                    raise ValueError("Resposta de extração sem objeto markers.")
                normalized = {
                    marker: normalize_marker(marker, markers.get(marker, {}))
                    for marker in MARKER_NAMES
                }
                record = {
                    "patient_id": patient_id,
                    "extractor_id": self.extractor_id,
                    "ontology_version": self.ontology_version,
                    "extraction_status": "success",
                    "retry_count": attempt,
                    "backend": result.backend,
                    "model_id": result.model_id,
                    "response_model": result.response_model,
                    "finish_reason": result.finish_reason,
                    "prompt_version": self.prompt_version,
                    "prompt_hash": prompt_hash,
                    "raw_response_hash": json_hash(result.raw_text),
                    "request_timestamp_utc": request_timestamp,
                    **flatten_markers(normalized, "marcadores_extraidos_"),
                }
                self.audit_records.append(
                    {
                        "patient_id": patient_id,
                        "status": "success",
                        "retry_count": attempt,
                        "backend": result.backend,
                        "model_id": result.model_id,
                        "prompt_hash": prompt_hash,
                        "raw_response_hash": json_hash(result.raw_text),
                        "raw_response": result.raw_text,
                        "usage": result.usage,
                    }
                )
                return record
            except Exception as error:  # noqa: BLE001
                last_error = error
                if attempt < self.max_retries and self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))

        error_type = type(last_error).__name__ if last_error else "UnknownError"
        self.audit_records.append(
            {
                "patient_id": patient_id,
                "status": "failed",
                "retry_count": self.max_retries,
                "backend": self.backend,
                "model_id": self.model_id,
                "prompt_hash": prompt_hash,
                "error_type": error_type,
            }
        )
        empty = {marker: {} for marker in MARKER_NAMES}
        return {
            "patient_id": patient_id,
            "extractor_id": self.extractor_id,
            "ontology_version": self.ontology_version,
            "extraction_status": "failed",
            "retry_count": self.max_retries,
            "backend": self.backend,
            "model_id": self.model_id,
            "response_model": None,
            "finish_reason": None,
            "prompt_version": self.prompt_version,
            "prompt_hash": prompt_hash,
            "raw_response_hash": "",
            "request_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **flatten_markers(empty, "marcadores_extraidos_"),
        }

    def extract(self, narrative_frame: pd.DataFrame, *, seed_offset: int = 0) -> pd.DataFrame:
        required = {"patient_id", "narrativa_clinica"}
        missing = required - set(narrative_frame.columns)
        if missing:
            raise ValueError(f"Narrativas sem colunas necessárias: {sorted(missing)}")
        self.audit_records = []
        rows = []
        for index, record in narrative_frame.reset_index(drop=True).iterrows():
            rows.append(
                self._extract_one(
                    str(record["patient_id"]),
                    str(record["narrativa_clinica"]),
                    self.base_seed + seed_offset + int(index),
                )
            )
        return pd.DataFrame(rows)

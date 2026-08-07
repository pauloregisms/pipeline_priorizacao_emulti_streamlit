"""Extrator Gemini independente, limitado exclusivamente ao texto da narrativa."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

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
}

EXTRACTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "markers": {
            "type": "object",
            "properties": {marker: _MARKER_SCHEMA for marker in MARKER_NAMES},
            "required": list(MARKER_NAMES),
        }
    },
    "required": ["markers"],
}

SYSTEM_INSTRUCTION = """Você extrai informações exclusivamente de uma narrativa clínica sintética.
Não use conhecimento externo, não complete lacunas e não infira prioridade, diagnóstico ou conduta.
Para cada marcador da ontologia, registre presença, negação, temporalidade, severidade, certeza,
experienciador e o menor trecho literal que sustenta a saída. Se não houver evidência, use present=0,
negated=0, remote_present=0, temporality=nao_especificado, severity=ausente, severity_code=0, certainty=afirmado,
experiencer=paciente e evidence vazio. Retorne somente o JSON solicitado."""


class GeminiClinicalExtractor:
    """Extrai marcadores com Gemini sem receber dados estruturados, origem ou rótulo."""

    def __init__(
        self,
        *,
        model_id: str,
        extractor_id: str,
        ontology_version: str,
        prompt_version: str,
        api_key_env: str = "GEMINI_API_KEY",
        temperature: float = 0.0,
        max_output_tokens: int = 2200,
        max_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        base_seed: int = 0,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id do extrator Gemini não pode ser vazio.")
        self.model_id = model_id
        self.extractor_id = extractor_id
        self.ontology_version = ontology_version
        self.prompt_version = prompt_version
        self.api_key_env = api_key_env
        self.temperature = float(temperature)
        self.max_output_tokens = int(max_output_tokens)
        self.max_retries = int(max_retries)
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self.base_seed = int(base_seed)
        self.audit_records: list[dict[str, Any]] = []

        if client is not None:
            self._client = client
        else:
            resolved_api_key = api_key or os.getenv(api_key_env)
            if not resolved_api_key:
                raise EnvironmentError(
                    f"A variável de ambiente {api_key_env!r} não foi definida para a extração Gemini."
                )
            try:
                from google import genai
            except ImportError as error:  # pragma: no cover
                raise ImportError("Instale google-genai para usar a extração Gemini.") from error
            self._client = genai.Client(api_key=resolved_api_key)

    @staticmethod
    def _parse_json(raw_text: str) -> Mapping[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, Mapping) or not isinstance(parsed.get("markers"), Mapping):
            raise ValueError("Resposta de extração sem objeto markers.")
        return parsed

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
            timestamp = datetime.now(timezone.utc).isoformat()
            try:
                response = self._client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_output_tokens,
                        "seed": seed,
                        "response_mime_type": "application/json",
                        "response_json_schema": EXTRACTION_RESPONSE_SCHEMA,
                    },
                )
                raw_text = getattr(response, "text", None)
                if not isinstance(raw_text, str) or not raw_text.strip():
                    raise ValueError("Resposta Gemini vazia na extração.")
                parsed = self._parse_json(raw_text)
                normalized = {
                    marker: normalize_marker(marker, parsed["markers"].get(marker, {}))
                    for marker in MARKER_NAMES
                }
                record = {
                    "patient_id": patient_id,
                    "extractor_id": self.extractor_id,
                    "ontology_version": self.ontology_version,
                    "extraction_status": "success",
                    "retry_count": attempt,
                    "model_id": self.model_id,
                    "prompt_version": self.prompt_version,
                    "prompt_hash": prompt_hash,
                    "raw_response_hash": json_hash(raw_text),
                    "request_timestamp_utc": timestamp,
                    **flatten_markers(normalized, "marcadores_extraidos_"),
                }
                self.audit_records.append(
                    {
                        "patient_id": patient_id,
                        "status": "success",
                        "retry_count": attempt,
                        "prompt_hash": prompt_hash,
                        "raw_response_hash": json_hash(raw_text),
                        "raw_response": raw_text,
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
            "model_id": self.model_id,
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

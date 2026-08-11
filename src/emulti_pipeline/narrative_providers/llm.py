"""Gerador de narrativas por LLM independente de fornecedor."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from ..llm import StructuredLLMClient
from ..narratives import (
    DEFAULT_FORBIDDEN_NARRATIVE_KEYS,
    BaseNarrativeGenerator,
    NarrativeRequest,
    NarrativeResponse,
    narrative_input_payload,
    validate_narrative_has_no_psychometric_scores,
    validate_narrative_request,
)
from ..utils import json_hash


LOGGER = logging.getLogger("emulti_pipeline.llm_calls")


NARRATIVE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subjective": {
            "type": "string",
            "description": "Campo Subjetivo da nota SOAP, em português brasileiro e sem cabeçalho S.",
        },
        "assessment": {
            "type": "string",
            "description": "Campo Avaliação da nota SOAP, em português brasileiro e sem cabeçalho A.",
        },
    },
    "required": ["subjective", "assessment"],
    "additionalProperties": False,
}


SYSTEM_INSTRUCTION = """Você redige somente narrativas clínicas inteiramente sintéticas em português brasileiro.
A saída deve representar uma nota SOAP curta e objetiva, limitada aos campos Subjetivo e Avaliação.
Use exclusivamente os fatos do payload fornecido. Não invente sintomas, diagnósticos, eventos, medicamentos,
dados demográficos, informações identificáveis ou fatos temporais que não estejam no payload. Não use nomes
próprios, endereços, documentos, telefones ou identificadores. Não forneça diagnóstico, conduta, recomendação
assistencial ou decisão de triagem. Não use termos de classificação ou priorização. As manifestações psicológicas
do payload já foram traduzidas localmente para descrições qualitativas. Não mencione nomes de questionários,
instrumentos psicométricos, números de itens, escores, pontuações, faixas ou resultados de testes. Retorne apenas
o objeto JSON solicitado, sem markdown e sem explicações adicionais."""


class LLMNarrativeGenerator(BaseNarrativeGenerator):
    """Gera narrativas SOAP usando o backend e o modelo declarados no YAML."""

    def __init__(
        self,
        *,
        llm_configuration: Mapping[str, Any],
        generator_id: str,
        temperature: float | None = 1.0,
        max_output_tokens: int = 2048,
        max_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        language: str = "pt-BR",
        forbidden_input_keys: Iterable[str] | None = None,
        llm_client: StructuredLLMClient | None = None,
        completion_callable: Callable[..., Any] | None = None,
        api_key: str | None = None,
    ) -> None:
        if not generator_id.strip():
            raise ValueError("generator_id não pode ser vazio.")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens deve ser maior que zero.")
        if max_retries < 0:
            raise ValueError("max_retries não pode ser negativo.")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds não pode ser negativo.")

        self.generator_id = generator_id
        self.temperature = temperature
        self.max_output_tokens = int(max_output_tokens)
        self.max_retries = int(max_retries)
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self.language = language
        self.forbidden_input_keys = tuple(
            set(DEFAULT_FORBIDDEN_NARRATIVE_KEYS).union(forbidden_input_keys or ())
        )
        self._llm = llm_client or StructuredLLMClient(
            llm_configuration,
            completion_callable=completion_callable,
            api_key=api_key,
        )
        self.model_id = self._llm.model_id
        self.backend = self._llm.backend

    @staticmethod
    def _build_prompt(request: NarrativeRequest) -> str:
        permitted_payload = {
            "dados_estruturados": request.dados_estruturados,
            "manifestacoes_psicologicas": request.manifestacoes_psicologicas,
            "marcadores_origem": request.marcadores_origem,
        }
        return (
            "Elabore uma nota SOAP curta para um caso inteiramente sintético.\n"
            "Produza somente os campos Subjetivo e Avaliação no formato JSON solicitado.\n"
            "Descreva experiências e atitudes em linguagem clínica cotidiana, sem citar "
            "instrumentos, itens, escores ou pontuações.\n"
            "Os dados abaixo são a única fonte de informação permitida:\n"
            f"{json.dumps(permitted_payload, ensure_ascii=False, sort_keys=True, default=str)}"
        )

    @staticmethod
    def _clean_section(value: Any, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"A resposta não possui campo textual válido: {field_name}.")
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned:
            raise ValueError(f"A resposta retornou campo vazio: {field_name}.")
        cleaned = re.sub(
            rf"^(?:{field_name}|s|a|subjetivo|avaliação)\s*[-:]\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip()

    def generate(
        self,
        request: NarrativeRequest,
        *,
        progress_index: int = 1,
        progress_total: int = 1,
        progress_phase: str = "narrative_generation",
    ) -> NarrativeResponse:
        """Solicita e valida uma narrativa com retentativas rastreáveis."""

        validate_narrative_request(request, self.forbidden_input_keys)
        input_hash = json_hash(narrative_input_payload(request))
        prompt = self._build_prompt(request)
        prompt_hash = json_hash(
            {
                "system_instruction": SYSTEM_INSTRUCTION,
                "prompt": prompt,
                "response_schema": NARRATIVE_RESPONSE_SCHEMA,
                "prompt_version": request.prompt_version,
            }
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            request_timestamp = datetime.now(timezone.utc).isoformat()
            try:
                result = self._llm.generate_json(
                    system_instruction=SYSTEM_INSTRUCTION,
                    prompt=prompt,
                    response_schema=NARRATIVE_RESPONSE_SCHEMA,
                    schema_name="emulti_narrative",
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                    seed=request.seed,
                    trace_context={
                        "stage": "04_generate_narratives",
                        "phase": progress_phase,
                        "patient_id": request.patient_id,
                        "operation_index": progress_index,
                        "operation_total": progress_total,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries + 1,
                    },
                )
                subjective = self._clean_section(result.data.get("subjective"), "subjective")
                assessment = self._clean_section(result.data.get("assessment"), "assessment")
                validate_narrative_has_no_psychometric_scores(subjective, assessment)
                narrativa_clinica = f"S - {subjective}\nA - {assessment}"
                narrative_id = f"NAR-{request.patient_id}-{input_hash[:10]}"

                return NarrativeResponse(
                    patient_id=request.patient_id,
                    narrative_id=narrative_id,
                    subjective=subjective,
                    assessment=assessment,
                    narrativa_clinica=narrativa_clinica,
                    generator_id=self.generator_id,
                    prompt_version=request.prompt_version,
                    input_hash=input_hash,
                    generation_metadata={
                        "mode": "llm_api",
                        "api_called": True,
                        "backend": result.backend,
                        "model_id": result.model_id,
                        "response_model": result.response_model,
                        "finish_reason": result.finish_reason,
                        "request_timestamp_utc": request_timestamp,
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_output_tokens,
                        "seed_requested": request.seed,
                        "seed_sent": self._llm.send_seed,
                        "prompt_hash": prompt_hash,
                        "retry_count": attempt,
                        "forbidden_label_check": "passed",
                        "psychometric_score_check": "passed",
                        "psychometric_narrative_contract": "qualitative_manifestations_only_v1",
                        "response_format": self._llm.response_format,
                        "language": self.language,
                        "usage": result.usage,
                    },
                )
            except Exception as error:  # noqa: BLE001
                last_error = error
                if attempt < self.max_retries:
                    backoff = self.retry_backoff_seconds * (2**attempt)
                    LOGGER.warning(
                        "LLM_RETRY | stage=04_generate_narratives | phase=%s | "
                        "patient_id=%s | operation=%d/%d | failed_attempt=%d/%d | "
                        "next_attempt=%d/%d | backoff_seconds=%.3f | error_type=%s",
                        progress_phase,
                        request.patient_id,
                        progress_index,
                        progress_total,
                        attempt + 1,
                        self.max_retries + 1,
                        attempt + 2,
                        self.max_retries + 1,
                        backoff,
                        type(error).__name__,
                    )
                    if backoff > 0:
                        time.sleep(backoff)

        error_type = type(last_error).__name__ if last_error is not None else "UnknownError"
        LOGGER.error(
            "LLM_OPERATION_EXHAUSTED | stage=04_generate_narratives | phase=%s | "
            "patient_id=%s | operation=%d/%d | attempts=%d | error_type=%s",
            progress_phase,
            request.patient_id,
            progress_index,
            progress_total,
            self.max_retries + 1,
            error_type,
        )
        raise RuntimeError(
            "Falha ao gerar narrativa por LLM após "
            f"{self.max_retries + 1} tentativa(s). Último tipo de erro: {error_type}."
        ) from last_error

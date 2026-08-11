"""Cliente unificado para modelos de linguagem configurados por YAML.

O pipeline usa uma única interface de saída estruturada. O backend, o modelo, a
variável que contém a chave e opções adicionais pertencem à configuração, não
aos scripts metodológicos. A comunicação é delegada ao LiteLLM, que normaliza
provedores como Google AI, OpenAI, Anthropic e endpoints compatíveis.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


LOGGER = logging.getLogger("emulti_pipeline.llm_calls")


class LLMResponseTruncatedError(ValueError):
    """Indica que o provedor encerrou a resposta por limite de saída."""


@dataclass(frozen=True)
class StructuredLLMResponse:
    """Resposta JSON normalizada e metadados não sensíveis da chamada."""

    data: dict[str, Any]
    raw_text: str
    backend: str
    model_id: str
    response_model: str | None
    finish_reason: str | None
    usage: dict[str, Any]


def close_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Adiciona ``additionalProperties: false`` a todos os objetos do esquema."""

    result = copy.deepcopy(dict(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    return result


def parse_json_object(raw_text: str) -> dict[str, Any]:
    """Interpreta uma resposta JSON, tolerando somente cercas Markdown externas."""

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("A resposta estruturada deve ser um objeto JSON.")
    return parsed


def _simple_metadata(value: Any) -> dict[str, Any]:
    """Converte metadados de SDK em escalares seguros para auditoria."""

    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_none=True)
    elif hasattr(value, "dict"):
        value = value.dict()
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool)) or item is None
    }


def _first_choice(response: Any) -> Any:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        raise ValueError("O backend não retornou nenhuma alternativa de resposta.")
    return choices[0]


def _choice_content(choice: Any) -> str:
    message = getattr(choice, "message", None)
    if message is None and isinstance(choice, Mapping):
        message = choice.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("O backend não retornou conteúdo textual estruturado.")
    return content


class StructuredLLMClient:
    """Executa solicitações JSON por qualquer backend compatível com LiteLLM."""

    def __init__(
        self,
        configuration: Mapping[str, Any],
        *,
        completion_callable: Callable[..., Any] | None = None,
        api_key: str | None = None,
    ) -> None:
        self.backend = str(configuration.get("backend", "")).strip()
        self.model_id = str(configuration.get("model_id", "")).strip()
        self.api_key_env = str(configuration.get("api_key_env", "LLM_API_KEY")).strip()
        self.api_base = str(configuration.get("api_base", "")).strip() or None
        self.response_format = str(
            configuration.get("response_format", "json_schema")
        ).strip().lower()
        self.send_seed = bool(configuration.get("send_seed", False))
        request_options = configuration.get("request_options", {})
        if not isinstance(request_options, Mapping):
            raise ValueError("llm.request_options deve ser um dicionário YAML.")
        forbidden_options = {
            "api_key",
            "messages",
            "model",
            "response_format",
        }
        leaked = forbidden_options.intersection(request_options)
        if leaked:
            raise ValueError(
                "llm.request_options contém chaves reservadas: " + ", ".join(sorted(leaked))
            )
        self.request_options = dict(request_options)

        if not self.backend:
            raise ValueError("llm.backend deve identificar o provedor ou formato de API.")
        if not self.model_id:
            raise ValueError("llm.model_id deve identificar o modelo solicitado.")
        pending = [
            name
            for name, value in (("backend", self.backend), ("model_id", self.model_id))
            if value.upper().startswith("CONFIGURE_")
        ]
        if pending:
            raise ValueError(
                "A configuração LLM ainda contém valores pendentes em: "
                + ", ".join(pending)
                + ". Defina-os no arquivo YAML."
            )
        if self.response_format not in {"json_schema", "json_object", "prompt_only"}:
            raise ValueError(
                "llm.response_format deve ser json_schema, json_object ou prompt_only."
            )

        self.qualified_model_id = (
            self.model_id if "/" in self.model_id else f"{self.backend}/{self.model_id}"
        )
        self._api_key = api_key or os.getenv(self.api_key_env)
        if completion_callable is None:
            if not self._api_key:
                raise EnvironmentError(
                    f"A variável de ambiente {self.api_key_env!r} não foi definida."
                )
            try:
                from litellm import completion
            except ImportError as error:  # pragma: no cover - depende do ambiente
                raise ImportError(
                    "O pacote 'litellm' é necessário para usar narrative/extraction.provider: llm."
                ) from error
            self._completion = completion
        else:
            self._completion = completion_callable
        self._call_count = 0

    @staticmethod
    def _trace_fields(trace_context: Mapping[str, Any] | None) -> dict[str, Any]:
        """Normaliza somente campos de rastreamento não sensíveis para os logs."""

        context = dict(trace_context or {})
        operation_index = max(int(context.get("operation_index", 1)), 1)
        operation_total = max(int(context.get("operation_total", operation_index)), operation_index)
        attempt = max(int(context.get("attempt", 1)), 1)
        max_attempts = max(int(context.get("max_attempts", attempt)), attempt)
        return {
            "stage": str(context.get("stage", "llm")),
            "phase": str(context.get("phase", "request")),
            "patient_id": str(context.get("patient_id", "unknown")),
            "operation_index": operation_index,
            "operation_total": operation_total,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "planned_remaining": max(operation_total - operation_index, 0),
            "max_attempts_remaining": max(
                (max_attempts - attempt)
                + (operation_total - operation_index) * max_attempts,
                0,
            ),
        }

    @staticmethod
    def _finish_reason(choice: Any) -> str | None:
        value = getattr(choice, "finish_reason", None)
        if value is None and isinstance(choice, Mapping):
            value = choice.get("finish_reason")
        return str(value) if value is not None else None

    @staticmethod
    def _is_truncated(finish_reason: str | None) -> bool:
        if finish_reason is None:
            return False
        normalized = re.sub(r"[^A-Z0-9]+", "_", finish_reason.upper()).strip("_")
        return normalized in {
            "LENGTH",
            "MAX_TOKENS",
            "MAX_TOKEN",
            "MAX_OUTPUT_TOKENS",
        } or "MAX_TOKENS" in normalized

    def generate_json(
        self,
        *,
        system_instruction: str,
        prompt: str,
        response_schema: Mapping[str, Any],
        schema_name: str,
        temperature: float | None,
        max_output_tokens: int,
        seed: int | None = None,
        trace_context: Mapping[str, Any] | None = None,
    ) -> StructuredLLMResponse:
        """Solicita um objeto JSON e normaliza a resposta do backend selecionado."""

        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens deve ser maior que zero.")
        schema = close_json_schema(response_schema)
        effective_prompt = prompt
        response_format: dict[str, Any] | None
        if self.response_format == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            }
        elif self.response_format == "json_object":
            response_format = {"type": "json_object"}
            effective_prompt += (
                "\nResponda com um único objeto JSON compatível com este esquema:\n"
                + json.dumps(schema, ensure_ascii=False, sort_keys=True)
            )
        else:
            response_format = None
            effective_prompt += (
                "\nResponda somente com um objeto JSON compatível com este esquema:\n"
                + json.dumps(schema, ensure_ascii=False, sort_keys=True)
            )

        kwargs: dict[str, Any] = {
            "model": self.qualified_model_id,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": effective_prompt},
            ],
            "max_tokens": int(max_output_tokens),
            "drop_params": True,
            **self.request_options,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if response_format is not None:
            kwargs["response_format"] = response_format
        if seed is not None and self.send_seed:
            kwargs["seed"] = int(seed)

        trace = self._trace_fields(trace_context)
        self._call_count += 1
        call_number = self._call_count
        log_prefix = (
            "stage=%s | phase=%s | patient_id=%s | operation=%d/%d | "
            "attempt=%d/%d | api_call=%d"
        )
        LOGGER.info(
            "LLM_CALL_START | " + log_prefix
            + " | planned_remaining=%d | max_attempts_remaining=%d | model=%s",
            trace["stage"],
            trace["phase"],
            trace["patient_id"],
            trace["operation_index"],
            trace["operation_total"],
            trace["attempt"],
            trace["max_attempts"],
            call_number,
            trace["planned_remaining"],
            trace["max_attempts_remaining"],
            self.qualified_model_id,
        )
        started_at = time.perf_counter()
        try:
            response = self._completion(**kwargs)
            choice = _first_choice(response)
            finish_reason = self._finish_reason(choice)
            raw_text = _choice_content(choice)
            if self._is_truncated(finish_reason):
                raise LLMResponseTruncatedError(
                    "O provedor encerrou a resposta por limite de tokens de saída."
                )
            data = parse_json_object(raw_text)
        except Exception as error:  # noqa: BLE001
            LOGGER.warning(
                "LLM_CALL_FAILED | " + log_prefix
                + " | duration_seconds=%.3f | error_type=%s",
                trace["stage"],
                trace["phase"],
                trace["patient_id"],
                trace["operation_index"],
                trace["operation_total"],
                trace["attempt"],
                trace["max_attempts"],
                call_number,
                time.perf_counter() - started_at,
                type(error).__name__,
            )
            raise

        response_model = getattr(response, "model", None)
        if response_model is None and isinstance(response, Mapping):
            response_model = response.get("model")
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, Mapping):
            usage = response.get("usage")

        LOGGER.info(
            "LLM_CALL_SUCCESS | " + log_prefix
            + " | duration_seconds=%.3f | finish_reason=%s",
            trace["stage"],
            trace["phase"],
            trace["patient_id"],
            trace["operation_index"],
            trace["operation_total"],
            trace["attempt"],
            trace["max_attempts"],
            call_number,
            time.perf_counter() - started_at,
            finish_reason or "unknown",
        )

        return StructuredLLMResponse(
            data=data,
            raw_text=raw_text,
            backend=self.backend,
            model_id=self.model_id,
            response_model=str(response_model) if response_model is not None else None,
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=_simple_metadata(usage),
        )

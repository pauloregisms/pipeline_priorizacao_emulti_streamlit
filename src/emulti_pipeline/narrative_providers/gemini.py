"""Adaptador Gemini para geração de narrativas SOAP inteiramente sintéticas.

O adaptador usa o SDK oficial ``google-genai`` e a API ``generate_content``. Ele
não recebe dados reais, não envia ``prioridade_referencia`` e não registra chaves
de API, cabeçalhos ou o prompt completo nos artefatos do experimento.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ..narratives import (
    DEFAULT_FORBIDDEN_NARRATIVE_KEYS,
    BaseNarrativeGenerator,
    NarrativeRequest,
    NarrativeResponse,
    narrative_input_payload,
    validate_narrative_request,
)
from ..utils import json_hash


# O esquema força uma resposta mínima, rastreável e independente de formatação livre.
# O adaptador monta a forma final "S - ...\nA - ..." a partir desses dois campos.
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
}


SYSTEM_INSTRUCTION = """Você redige somente narrativas clínicas inteiramente sintéticas em português brasileiro.
A saída deve representar uma nota SOAP curta e objetiva, limitada aos campos Subjetivo e Avaliação.
Use exclusivamente os fatos do payload fornecido. Não invente sintomas, diagnósticos, eventos, medicamentos,
dados demográficos, informações identificáveis ou fatos temporais que não estejam no payload. Não use nomes
próprios, endereços, documentos, telefones ou identificadores. Não forneça diagnóstico, conduta, recomendação
assistencial ou decisão de triagem. Não use termos de classificação ou priorização. Retorne apenas o objeto JSON
solicitado, sem markdown e sem explicações adicionais."""


class GeminiNarrativeGenerator(BaseNarrativeGenerator):
    """Gera narrativas SOAP por Gemini mantendo o contrato do pipeline.

    Args:
        model_id: Identificador exato do modelo Gemini selecionado no YAML.
        generator_id: Identificador estável preservado nos artefatos do experimento.
        api_key_env: Nome da variável de ambiente que contém a chave da API.
        temperature: Parâmetro de geração registrado em metadados.
        max_output_tokens: Limite de saída para a narrativa JSON curta.
        max_retries: Número máximo de novas tentativas após a primeira chamada.
        retry_backoff_seconds: Espera inicial antes de retentativas exponenciais.
        language: Idioma esperado no texto de saída.
        forbidden_input_keys: Chaves extras a bloquear além da lista padrão.
        client: Cliente injetável para testes. Quando omitido, cria ``genai.Client``.
    """

    def __init__(
        self,
        model_id: str,
        generator_id: str,
        api_key_env: str = "GEMINI_API_KEY",
        temperature: float = 1.0,
        max_output_tokens: int = 500,
        max_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        language: str = "pt-BR",
        forbidden_input_keys: Iterable[str] | None = None,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id do Gemini não pode ser vazio.")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens deve ser maior que zero.")
        if max_retries < 0:
            raise ValueError("max_retries não pode ser negativo.")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds não pode ser negativo.")

        self.model_id = model_id
        self.generator_id = generator_id
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.language = language
        self.forbidden_input_keys = tuple(
            set(DEFAULT_FORBIDDEN_NARRATIVE_KEYS).union(forbidden_input_keys or ())
        )

        # A injeção de cliente é usada nos testes unitários. Na execução normal, a
        # chave é lida somente do ambiente e não é preservada no objeto/metadados.
        if client is not None:
            self._client = client
        else:
            resolved_api_key = api_key or os.getenv(api_key_env)
            if not resolved_api_key:
                raise EnvironmentError(
                    f"A variável de ambiente {api_key_env!r} não foi definida. "
                    "Defina a chave Gemini fora do código e tente novamente."
                )
            try:
                from google import genai
            except ImportError as error:  # pragma: no cover - depende da instalação local
                raise ImportError(
                    "O pacote 'google-genai' é necessário para usar o provedor Gemini. "
                    "Execute: python -m pip install -r requirements.txt"
                ) from error
            self._client = genai.Client(api_key=resolved_api_key)

    @staticmethod
    def _build_prompt(request: NarrativeRequest) -> str:
        """Monta prompt auditável somente com as entradas autorizadas.

        O identificador e a semente ficam no hash/metadados para rastreabilidade, mas
        não são necessários para a redação e, portanto, não seguem para o modelo.
        """
        permitted_payload = {
            "dados_estruturados": request.dados_estruturados,
            "indicadores_psicometricos": request.indicadores_psicometricos,
            "marcadores_origem": request.marcadores_origem,
        }
        return (
            "Elabore uma nota SOAP curta para um caso inteiramente sintético.\n"
            "Produza somente os campos Subjetivo e Avaliação no formato JSON solicitado.\n"
            "Os dados abaixo são a única fonte de informação permitida:\n"
            f"{json.dumps(permitted_payload, ensure_ascii=False, sort_keys=True, default=str)}"
        )

    @staticmethod
    def _clean_section(value: Any, field_name: str) -> str:
        """Valida e normaliza uma seção textual curta da resposta estruturada."""
        if not isinstance(value, str):
            raise ValueError(f"A resposta Gemini não possui campo textual válido: {field_name}.")
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned:
            raise ValueError(f"A resposta Gemini retornou campo vazio: {field_name}.")
        # Impede que o modelo replique cabeçalhos; o adaptador controla a forma SOAP final.
        cleaned = re.sub(rf"^(?:{field_name}|s|a|subjetivo|avaliação)\s*[-:]\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _parse_json_response(raw_text: str) -> Mapping[str, Any]:
        """Extrai objeto JSON mesmo se o modelo incluir delimitadores markdown."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("A resposta Gemini não pôde ser interpretada como JSON estruturado.") from error
        if not isinstance(parsed, Mapping):
            raise ValueError("A resposta Gemini estruturada deve ser um objeto JSON.")
        return parsed

    @staticmethod
    def _usage_metadata(response: Any) -> dict[str, Any]:
        """Extrai somente contagens de uso, quando o SDK as disponibilizar."""
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            raw = usage.model_dump(exclude_none=True)
            return {str(key): value for key, value in raw.items() if isinstance(value, (int, float, str, bool))}
        if isinstance(usage, Mapping):
            return {str(key): value for key, value in usage.items() if isinstance(value, (int, float, str, bool))}
        fields = ["prompt_token_count", "candidates_token_count", "total_token_count", "thoughts_token_count"]
        return {
            field: getattr(usage, field)
            for field in fields
            if getattr(usage, field, None) is not None
        }

    def generate(self, request: NarrativeRequest) -> NarrativeResponse:
        """Solicita e valida uma narrativa Gemini, com retentativas rastreáveis."""
        validate_narrative_request(request, self.forbidden_input_keys)
        input_payload = narrative_input_payload(request)
        input_hash = json_hash(input_payload)
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
            request_timestamp_utc = datetime.now(timezone.utc).isoformat()
            try:
                response = self._client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config={
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_output_tokens,
                        "seed": request.seed,
                        "response_mime_type": "application/json",
                        "response_json_schema": NARRATIVE_RESPONSE_SCHEMA,
                    },
                )
                raw_text = getattr(response, "text", None)
                if not isinstance(raw_text, str) or not raw_text.strip():
                    raise ValueError("A Gemini API não retornou texto estruturado utilizável.")

                parsed = self._parse_json_response(raw_text)
                subjective = self._clean_section(parsed.get("subjective"), "subjective")
                assessment = self._clean_section(parsed.get("assessment"), "assessment")
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
                        "mode": "gemini_api",
                        "api_called": True,
                        "provider": "gemini",
                        "model_id": self.model_id,
                        "model_version": getattr(response, "model_version", None),
                        "request_timestamp_utc": request_timestamp_utc,
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_output_tokens,
                        "seed": request.seed,
                        "prompt_hash": prompt_hash,
                        "retry_count": attempt,
                        "forbidden_label_check": "passed",
                        "response_format": "application/json",
                        "language": self.language,
                        "usage": self._usage_metadata(response),
                    },
                )
            except Exception as error:  # noqa: BLE001 - API/validação podem usar classes variadas
                last_error = error
                if attempt < self.max_retries and self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))

        # Não inclui a mensagem do provedor: ela pode conter detalhes sensíveis ou da
        # configuração local. O tipo de erro basta para auditoria e depuração inicial.
        error_type = type(last_error).__name__ if last_error is not None else "UnknownError"
        raise RuntimeError(
            "Falha ao gerar narrativa com Gemini após "
            f"{self.max_retries + 1} tentativa(s). Último tipo de erro: {error_type}."
        ) from last_error

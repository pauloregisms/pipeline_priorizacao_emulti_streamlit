"""Contratos, validações e fábrica para geração de narrativas clínicas sintéticas.

A geração textual permanece desacoplada do restante do pipeline. O projeto inclui:

- ``TemplateNarrativeGenerator``: simulador local, determinístico por semente;
- ``LLMNarrativeGenerator``: adaptador unificado para backends de LLM;
- ``create_narrative_generator``: fábrica configurável por YAML.

Todos os provedores recebem somente ``NarrativeRequest`` e devem devolver
``NarrativeResponse``. A prioridade de referência simulada e qualquer pista direta
do rótulo são bloqueadas antes da montagem do prompt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping

import numpy as np

from .markers import MARKER_NAMES, normalize_marker
from .utils import json_hash


# Itens e totais são preservados na etapa psicométrica e nos conjuntos analíticos,
# mas não pertencem ao contrato textual. A narrativa recebe somente uma tradução
# qualitativa local das experiências representadas pelas respostas simuladas.
RAW_PSYCHOMETRIC_NARRATIVE_KEYS = frozenset(
    {
        "phq9_total",
        "gad7_total",
        "idate_estado_total",
        "phq9_band",
        "gad7_band",
        *(f"phq9_item_{index:02d}" for index in range(1, 10)),
        *(f"gad7_item_{index:02d}" for index in range(1, 8)),
        *(f"idate_estado_item_{index:02d}_raw" for index in range(1, 21)),
        *(f"idate_estado_item_{index:02d}_score" for index in range(1, 21)),
    }
)


# Esta lista protege a fronteira metodológica do pipeline. Ela pode ser estendida
# no YAML, mas nunca deve ser reduzida por um adaptador de provedor.
DEFAULT_FORBIDDEN_NARRATIVE_KEYS = frozenset(
    {
        "prioridade_referencia",
        "prioridade_referencia_codigo",
        "prioridade_prevista",
        "prioridade_prevista_codigo",
        "priority",
        "priority_code",
        "prioridade",
        "priority_label",
        "label",
        "target",
        "yref",
        "yhat",
        *RAW_PSYCHOMETRIC_NARRATIVE_KEYS,
    }
)


_PSYCHOLOGICAL_ITEM_DOMAINS = (
    ("phq9_item_01", "redução do interesse ou do prazer nas atividades habituais"),
    ("phq9_item_02", "humor deprimido"),
    ("phq9_item_03", "alteração do sono"),
    ("phq9_item_04", "cansaço ou redução da energia"),
    ("phq9_item_05", "alteração do apetite"),
    ("phq9_item_06", "autopercepção negativa"),
    ("phq9_item_07", "dificuldade de concentração"),
    ("phq9_item_08", "agitação ou lentificação percebida"),
    # O conteúdo de segurança do nono item não é traduzido aqui. Ideação e
    # autoagressão são controladas exclusivamente por marcadores de origem para
    # evitar narrativas contraditórias.
    ("gad7_item_01", "nervosismo ou tensão"),
    ("gad7_item_02", "dificuldade para controlar as preocupações"),
    ("gad7_item_03", "preocupações excessivas com diferentes situações"),
    ("gad7_item_04", "dificuldade para relaxar"),
    ("gad7_item_05", "inquietação"),
    ("gad7_item_06", "irritabilidade"),
    ("gad7_item_07", "apreensão de que algo ruim possa acontecer"),
)

_QUALITATIVE_FREQUENCY = {
    1: "ocasional",
    2: "frequente",
    3: "muito frequente",
}

_FORBIDDEN_PSYCHOMETRIC_TEXT = re.compile(
    r"\b(?:phq\s*-?\s*9|gad\s*-?\s*7|idate(?:\s*-?\s*estado)?|"
    r"invent[aá]rio\s+de\s+ansiedade|question[aá]rio\s+psicom[eé]trico|"
    r"instrumento\s+psicom[eé]trico|escore|pontua(?:ç|c)[aã]o|"
    r"\d+\s+pontos?|\d+\s*/\s*(?:21|27|80))\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class NarrativeRequest:
    """Dados permitidos para geração da narrativa de um perfil sintético.

    O contrato não possui campo de prioridade. O adaptador ainda valida o conteúdo
    dos dicionários para impedir que chaves proibidas sejam inseridas indiretamente.
    """

    patient_id: str
    seed: int
    dados_estruturados: dict[str, Any]
    manifestacoes_psicologicas: dict[str, Any]
    marcadores_origem: dict[str, Any]
    prompt_version: str


@dataclass(frozen=True)
class NarrativeResponse:
    """Contrato de retorno preservado para simulador local ou provedor de API."""

    patient_id: str
    narrative_id: str
    subjective: str
    assessment: str
    narrativa_clinica: str
    generator_id: str
    prompt_version: str
    input_hash: str
    generation_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Converte a resposta para estrutura serializável em JSON."""
        return asdict(self)


class BaseNarrativeGenerator(ABC):
    """Interface mínima que qualquer adaptador de LLM deve implementar."""

    @abstractmethod
    def generate(
        self,
        request: NarrativeRequest,
        *,
        progress_index: int = 1,
        progress_total: int = 1,
        progress_phase: str = "narrative_generation",
    ) -> NarrativeResponse:
        """Gera narrativa sem receber rótulo de prioridade ou informação equivalente."""


def narrative_input_payload(request: NarrativeRequest) -> dict[str, Any]:
    """Retorna exclusivamente o payload metodologicamente autorizado.

    A função é compartilhada para que o hash de entrada tenha a mesma semântica em
    todos os provedores. ``patient_id`` e ``seed`` entram no hash de rastreabilidade,
    mas não precisam ser enviados ao modelo de linguagem.
    """
    return {
        "patient_id": request.patient_id,
        "seed": request.seed,
        "dados_estruturados": request.dados_estruturados,
        "manifestacoes_psicologicas": request.manifestacoes_psicologicas,
        "marcadores_origem": request.marcadores_origem,
        "prompt_version": request.prompt_version,
    }


def _require_ordinal_value(
    scales: Mapping[str, Any],
    key: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    """Lê uma resposta ordinal simulada sem permitir valores fora do contrato."""

    if key not in scales:
        raise ValueError(f"Resposta psicométrica ausente para tradução qualitativa: {key}.")
    try:
        value = int(scales[key])
    except (TypeError, ValueError) as error:
        raise ValueError(f"Resposta psicométrica inválida para tradução qualitativa: {key}.") from error
    if value < minimum or value > maximum:
        raise ValueError(
            f"Resposta psicométrica fora da faixa para tradução qualitativa: {key}."
        )
    return value


def build_qualitative_psychological_context(
    scales: Mapping[str, Any],
) -> dict[str, Any]:
    """Traduz respostas simuladas em manifestações sem expor instrumentos ou escores.

    Os nomes dos instrumentos, os números dos itens, as respostas ordinais e os
    totais permanecem fora do objeto devolvido. A seleção prioriza até seis
    manifestações mais frequentes para manter a narrativa curta. O conteúdo de
    ideação ou autoagressão é deliberadamente reservado aos marcadores clínicos.
    """

    candidates: list[tuple[int, int, str]] = []
    for order, (column, description) in enumerate(_PSYCHOLOGICAL_ITEM_DOMAINS):
        value = _require_ordinal_value(scales, column, minimum=0, maximum=3)
        if value > 0:
            candidates.append((value, order, description))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    manifestations = [
        {
            "descricao": description,
            "frequencia": _QUALITATIVE_FREQUENCY[value],
        }
        for value, _, description in candidates[:6]
    ]

    state_values = [
        _require_ordinal_value(
            scales,
            f"idate_estado_item_{index:02d}_score",
            minimum=1,
            maximum=4,
        )
        for index in range(1, 21)
    ]
    state_mean = float(np.mean(state_values))
    if state_mean < 1.75:
        emotional_state = "predomínio de tranquilidade no momento"
    elif state_mean < 2.50:
        emotional_state = "tensão emocional ocasional no momento"
    elif state_mean < 3.25:
        emotional_state = "tensão e ansiedade frequentes no momento"
    else:
        emotional_state = "tensão e ansiedade muito frequentes no momento"

    highest_frequency = candidates[0][0] if candidates else 0
    if highest_frequency >= 3 or state_mean >= 3.25:
        summary = "refere sofrimento emocional intenso e persistente"
    elif highest_frequency >= 2 or state_mean >= 2.50:
        summary = "refere sofrimento emocional frequente, com repercussão no cotidiano"
    elif highest_frequency >= 1 or state_mean >= 1.75:
        summary = "refere manifestações emocionais ocasionais e oscilantes"
    else:
        summary = "não refere manifestações emocionais relevantes no momento"

    return {
        "sintese": summary,
        "estado_emocional_atual": emotional_state,
        "manifestacoes_relevantes": manifestations,
    }


def validate_narrative_has_no_psychometric_scores(*sections: str) -> None:
    """Impede que a narrativa exponha nomes de instrumentos ou seus escores."""

    for section in sections:
        match = _FORBIDDEN_PSYCHOMETRIC_TEXT.search(section)
        if match:
            raise ValueError(
                "A narrativa contém referência explícita a instrumento ou escore psicométrico."
            )


def validate_qualitative_psychological_context(context: Mapping[str, Any]) -> None:
    """Valida que o contexto textual contém apenas descrições qualitativas."""

    allowed_keys = {"sintese", "estado_emocional_atual", "manifestacoes_relevantes"}
    unexpected = set(context) - allowed_keys
    if unexpected:
        raise ValueError(
            "Contexto psicológico contém campos não autorizados: "
            + ", ".join(sorted(str(key) for key in unexpected))
        )
    for key in ("sintese", "estado_emocional_atual"):
        value = context.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Contexto psicológico qualitativo inválido: {key}.")
        validate_narrative_has_no_psychometric_scores(value)

    manifestations = context.get("manifestacoes_relevantes")
    if not isinstance(manifestations, list):
        raise ValueError("manifestacoes_relevantes deve ser uma lista qualitativa.")
    for manifestation in manifestations:
        if not isinstance(manifestation, Mapping):
            raise ValueError("Manifestação psicológica qualitativa inválida.")
        if set(manifestation) != {"descricao", "frequencia"}:
            raise ValueError(
                "Manifestação psicológica deve conter somente descrição e frequência."
            )
        for value in manifestation.values():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Manifestação psicológica deve conter somente texto qualitativo.")
            validate_narrative_has_no_psychometric_scores(value)


def find_forbidden_narrative_keys(
    payload: Any,
    forbidden_keys: Iterable[str] | None = None,
    path: str = "",
) -> list[str]:
    """Localiza recursivamente chaves proibidas em um payload de narrativa.

    A verificação recursiva impede que uma prioridade seja escondida em dicionários
    aninhados. O retorno traz caminhos legíveis para facilitar depuração sem expor
    valores do payload.
    """
    forbidden = {
        str(key).strip().lower()
        for key in (forbidden_keys or DEFAULT_FORBIDDEN_NARRATIVE_KEYS)
    }
    matches: list[str] = []

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.strip().lower() in forbidden:
                matches.append(child_path)
            matches.extend(find_forbidden_narrative_keys(value, forbidden, child_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            child_path = f"{path}[{index}]"
            matches.extend(find_forbidden_narrative_keys(value, forbidden, child_path))

    return matches


def validate_narrative_request(
    request: NarrativeRequest,
    forbidden_keys: Iterable[str] | None = None,
) -> None:
    """Falha explicitamente quando uma requisição inclui um campo proibido."""
    if not isinstance(request.manifestacoes_psicologicas, Mapping):
        raise ValueError("manifestacoes_psicologicas deve ser um dicionário qualitativo.")
    validate_qualitative_psychological_context(request.manifestacoes_psicologicas)
    leaked = find_forbidden_narrative_keys(
        narrative_input_payload(request),
        forbidden_keys=forbidden_keys,
    )
    if leaked:
        raise ValueError(
            "A requisição para narrativa contém chaves proibidas que podem causar "
            f"vazamento de rótulo: {sorted(leaked)}"
        )


def _functional_description(level: int) -> str:
    descriptions = {
        0: "mantém funcionalidade preservada nas atividades habituais",
        1: "relata dificuldade leve para manter as atividades habituais",
        2: "relata dificuldade moderada para manter atividades cotidianas",
        3: "relata importante comprometimento para atividades cotidianas",
    }
    return descriptions.get(int(level), "não foi possível caracterizar a funcionalidade")


class TemplateNarrativeGenerator(BaseNarrativeGenerator):
    """Gerador local, determinístico por semente, que simula a saída de uma LLM.

    O uso de variantes linguísticas torna a extração mais realista do que uma simples
    cópia de colunas. Ainda assim, o texto é estritamente condicionado aos atributos
    permitidos da requisição.
    """

    def __init__(
        self,
        generator_id: str = "template-simulator-v2-qualitative",
        forbidden_input_keys: Iterable[str] | None = None,
        omission_rate: float = 0.0,
    ) -> None:
        if not 0 <= omission_rate <= 1:
            raise ValueError("omission_rate deve estar entre 0 e 1.")
        self.generator_id = generator_id
        self.omission_rate = float(omission_rate)
        self.forbidden_input_keys = tuple(
            set(DEFAULT_FORBIDDEN_NARRATIVE_KEYS).union(forbidden_input_keys or ())
        )

    def generate(
        self,
        request: NarrativeRequest,
        *,
        progress_index: int = 1,
        progress_total: int = 1,
        progress_phase: str = "narrative_generation",
    ) -> NarrativeResponse:
        validate_narrative_request(request, self.forbidden_input_keys)

        rng = np.random.default_rng(request.seed)
        psychological_context = request.manifestacoes_psicologicas
        z = {
            marker: normalize_marker(marker, request.marcadores_origem.get(marker, {}))
            for marker in MARKER_NAMES
        }

        summary = str(psychological_context.get("sintese", "")).strip()
        emotional_state = str(
            psychological_context.get("estado_emocional_atual", "")
        ).strip()
        if not summary or not emotional_state:
            raise ValueError("Contexto psicológico qualitativo incompleto para a narrativa.")
        subjective_parts = [f"{summary}.", f"Apresenta {emotional_state}."]
        manifestations = psychological_context.get("manifestacoes_relevantes", [])
        if not isinstance(manifestations, list):
            raise ValueError("manifestacoes_relevantes deve ser uma lista qualitativa.")
        for manifestation in manifestations[:4]:
            if not isinstance(manifestation, Mapping):
                raise ValueError("Manifestação psicológica qualitativa inválida.")
            description = str(manifestation.get("descricao", "")).strip()
            frequency = str(manifestation.get("frequencia", "")).strip()
            if description and frequency:
                subjective_parts.append(
                    f"Refere {description} de forma {frequency}."
                )
        assessment_parts = [
            "Quadro compatível, no cenário sintético, com necessidade de acompanhamento conforme evolução e rede de suporte.",
        ]

        # Cada menção é controlada pelo contrato de origem. O cenário de omissão
        # remove menções antes da extração sem modificar a prioridade de referência.
        terms = {
            "ideacao_suicida": "ideação suicida",
            "planejamento_suicida": "planejamento suicida",
            "autoagressao_iminente": "autoagressão iminente",
            "risco_violencia": "risco de violência",
            "sintomas_psicoticos": "sintomas psicóticos",
            "uso_problematico_substancias": "uso problemático de substâncias",
            "internacao_previa": "internação prévia relacionada a sofrimento psíquico",
            "agravamento_recente": "agravamento recente dos sintomas",
        }
        for marker in MARKER_NAMES:
            value = z[marker]
            expressed = bool(value["present"] or value["negated"] or value["remote_present"])
            if not expressed or rng.random() < self.omission_rate:
                continue
            if marker == "comprometimento_funcional":
                if value["negated"]:
                    subjective_parts.append("Paciente mantém funcionalidade preservada nas atividades habituais.")
                else:
                    subjective_parts.append(
                        "Paciente " + _functional_description(int(value["severity_code"])) + "."
                    )
                continue
            if marker == "suporte_social_baixo":
                subjective_parts.append(
                    "Paciente refere rede de apoio limitada no momento."
                    if value["present"]
                    else "Paciente refere rede de apoio disponível no momento."
                )
                continue

            term = terms[marker]
            subject = "Um familiar" if value["experiencer"] == "terceiro" else "Paciente"
            if value["remote_present"] and marker != "internacao_previa":
                subjective_parts.append(f"{subject} apresentou {term} no passado.")
            temporal = {
                "atual": "atualmente",
                "remoto": "no passado",
                "nao_especificado": "",
            }[value["temporality"]]
            if value["negated"]:
                sentence = f"{subject} nega {term} {temporal}."
            else:
                hedge = "possivelmente " if value["certainty"] == "incerto" else ""
                sentence = f"{subject} {hedge}apresenta {term} {temporal}."
            subjective_parts.append(" ".join(sentence.split()))

        # Pequena variação superficial do texto, sem introduzir informação clínica nova.
        opening = rng.choice(["Usuário", "Pessoa acompanhada", "Paciente fictício"])
        subjective = f"{opening}: " + " ".join(subjective_parts)
        assessment = "Avaliação: " + " ".join(assessment_parts)
        narrativa_clinica = f"S - {subjective}\nA - {assessment}"
        validate_narrative_has_no_psychometric_scores(subjective, assessment)

        input_hash = json_hash(narrative_input_payload(request))
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
                "mode": "simulated_template",
                "random_seed": request.seed,
                "api_called": False,
                "forbidden_label_check": "passed",
                "psychometric_score_check": "passed",
                "psychometric_narrative_contract": "qualitative_manifestations_only_v1",
                "narrative_omission_rate": self.omission_rate,
            },
        )


def create_narrative_generator(narrative_config: Mapping[str, Any]) -> BaseNarrativeGenerator:
    """Instancia o provedor textual configurado sem acoplar scripts ao fornecedor.

    O valor padrão é ``template`` para preservar a execução local. O provedor
    ``llm`` lê backend, modelo e credencial exclusivamente do YAML e do ambiente.
    """
    provider = str(narrative_config.get("provider", "template")).strip().lower()
    forbidden_input_keys = narrative_config.get("forbidden_input_keys", ())

    if provider == "template":
        return TemplateNarrativeGenerator(
            generator_id=str(
                narrative_config.get("generator_id", "template-simulator-v2-qualitative")
            ),
            forbidden_input_keys=forbidden_input_keys,
            omission_rate=float(narrative_config.get("omission_rate", 0.0)),
        )

    if provider == "llm":
        from .narrative_providers.llm import LLMNarrativeGenerator

        llm_config = narrative_config.get("llm", {})
        if not isinstance(llm_config, Mapping):
            raise ValueError("O bloco narrative.llm deve ser um dicionário YAML.")
        temperature = llm_config.get("temperature", 1.0)
        return LLMNarrativeGenerator(
            llm_configuration=llm_config,
            generator_id=str(
                llm_config.get(
                    "generator_id",
                    f"llm-{llm_config.get('backend', 'backend')}-{llm_config.get('model_id', 'model')}",
                )
            ),
            temperature=None if temperature is None else float(temperature),
            max_output_tokens=int(llm_config.get("max_output_tokens", 2048)),
            max_retries=int(narrative_config.get("max_retries", 2)),
            retry_backoff_seconds=float(llm_config.get("retry_backoff_seconds", 2.0)),
            language=str(narrative_config.get("language", "pt-BR")),
            forbidden_input_keys=forbidden_input_keys,
        )

    raise ValueError(
        f"Provedor de narrativa desconhecido: {provider!r}. "
        "Use 'template' ou 'llm'."
    )

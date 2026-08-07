"""Contratos, validações e fábrica para geração de narrativas clínicas sintéticas.

A geração textual permanece desacoplada do restante do pipeline. O projeto inclui:

- ``TemplateNarrativeGenerator``: simulador local, determinístico por semente;
- ``GeminiNarrativeGenerator``: adaptador opcional para a Gemini API;
- ``create_narrative_generator``: fábrica configurável por YAML.

Todos os provedores recebem somente ``NarrativeRequest`` e devem devolver
``NarrativeResponse``. A prioridade de referência simulada e qualquer pista direta
do rótulo são bloqueadas antes da montagem do prompt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

import numpy as np

from .markers import MARKER_NAMES, normalize_marker
from .utils import json_hash


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
    }
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
    indicadores_psicometricos: dict[str, Any]
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
    def generate(self, request: NarrativeRequest) -> NarrativeResponse:
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
        "indicadores_psicometricos": request.indicadores_psicometricos,
        "marcadores_origem": request.marcadores_origem,
        "prompt_version": request.prompt_version,
    }


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
    leaked = find_forbidden_narrative_keys(
        narrative_input_payload(request),
        forbidden_keys=forbidden_keys,
    )
    if leaked:
        raise ValueError(
            "A requisição para narrativa contém chaves proibidas que podem causar "
            f"vazamento de rótulo: {sorted(leaked)}"
        )


def _score_description(phq: int, gad: int, stai: int) -> str:
    """Converte escores em descrição clínica genérica, sem declarar prioridade."""
    if phq >= 20 or gad >= 15 or stai >= 65:
        return "refere sofrimento emocional intenso, com sintomas persistentes de humor deprimido e ansiedade"
    if phq >= 10 or gad >= 10 or stai >= 50:
        return "refere sintomas de ansiedade e humor deprimido com repercussão no cotidiano"
    if phq >= 5 or gad >= 5:
        return "refere sintomas leves e oscilantes de ansiedade ou humor"
    return "refere sintomas emocionais leves e atualmente estáveis"


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
        generator_id: str = "template-simulator-v1",
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

    def generate(self, request: NarrativeRequest) -> NarrativeResponse:
        validate_narrative_request(request, self.forbidden_input_keys)

        rng = np.random.default_rng(request.seed)
        s = request.indicadores_psicometricos
        z = {
            marker: normalize_marker(marker, request.marcadores_origem.get(marker, {}))
            for marker in MARKER_NAMES
        }

        symptom_text = _score_description(
            int(s["phq9_total"]), int(s["gad7_total"]), int(s["idate_estado_total"])
        )
        subjective_parts = [symptom_text]
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
                "narrative_omission_rate": self.omission_rate,
            },
        )


def create_narrative_generator(narrative_config: Mapping[str, Any]) -> BaseNarrativeGenerator:
    """Instancia o provedor textual configurado sem acoplar scripts ao fornecedor.

    O valor padrão é ``template`` para preservar execução local sem credenciais. O
    provedor ``gemini`` só é instanciado quando selecionado explicitamente no YAML.
    """
    provider = str(narrative_config.get("provider", "template")).strip().lower()
    forbidden_input_keys = narrative_config.get("forbidden_input_keys", ())

    if provider == "template":
        return TemplateNarrativeGenerator(
            generator_id=str(narrative_config.get("generator_id", "template-simulator-v1")),
            forbidden_input_keys=forbidden_input_keys,
            omission_rate=float(narrative_config.get("omission_rate", 0.0)),
        )

    if provider == "gemini":
        # Importação tardia: quem usa somente o simulador local não precisa importar
        # nem inicializar dependências da Gemini API.
        from .narrative_providers.gemini import GeminiNarrativeGenerator

        gemini_config = narrative_config.get("gemini", {})
        if not isinstance(gemini_config, Mapping):
            raise ValueError("O bloco narrative.gemini deve ser um dicionário YAML.")

        return GeminiNarrativeGenerator(
            model_id=str(gemini_config.get("model_id", "gemini-3.5-flash")),
            generator_id=str(
                gemini_config.get(
                    "generator_id",
                    f"gemini-api-{gemini_config.get('model_id', 'model')}",
                )
            ),
            api_key_env=str(gemini_config.get("api_key_env", "GEMINI_API_KEY")),
            temperature=float(gemini_config.get("temperature", 1.0)),
            max_output_tokens=int(gemini_config.get("max_output_tokens", 500)),
            max_retries=int(narrative_config.get("max_retries", 2)),
            retry_backoff_seconds=float(gemini_config.get("retry_backoff_seconds", 2.0)),
            language=str(narrative_config.get("language", "pt-BR")),
            forbidden_input_keys=forbidden_input_keys,
        )

    raise ValueError(
        f"Provedor de narrativa desconhecido: {provider!r}. "
        "Use 'template' ou 'gemini'."
    )


class FutureApiNarrativeGenerator(BaseNarrativeGenerator):
    """Esqueleto genérico para futuras integrações que não usem Gemini."""

    def generate(self, request: NarrativeRequest) -> NarrativeResponse:  # pragma: no cover
        raise NotImplementedError(
            "Implemente um adaptador de API que herde de BaseNarrativeGenerator. "
            "O adaptador deve respeitar NarrativeRequest/NarrativeResponse e nunca enviar prioridade_referencia."
        )

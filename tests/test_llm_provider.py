"""Testes sem rede para a camada LLM neutra e as fábricas de provedores."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from emulti_pipeline.config import load_config
from emulti_pipeline.llm import LLMResponseTruncatedError, StructuredLLMClient
from emulti_pipeline.narrative_providers.llm import LLMNarrativeGenerator
from emulti_pipeline.narratives import (
    NarrativeRequest,
    TemplateNarrativeGenerator,
    build_qualitative_psychological_context,
    create_narrative_generator,
)


class _FakeCompletion:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="backend-model-version",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(self.payload, ensure_ascii=False)
                    ),
                )
            ],
            usage={"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        )


class _SequenceCompletion:
    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        content, finish_reason = self.responses.pop(0)
        return SimpleNamespace(
            model="backend-model-version",
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(content=content),
                )
            ],
            usage={},
        )


def _request() -> NarrativeRequest:
    return NarrativeRequest(
        patient_id="SYN-0001",
        seed=1234,
        dados_estruturados={"age_years": 35, "social_vulnerability": 0.4},
        manifestacoes_psicologicas={
            "sintese": "refere manifestações emocionais ocasionais e oscilantes",
            "estado_emocional_atual": "tensão emocional ocasional no momento",
            "manifestacoes_relevantes": [
                {"descricao": "dificuldade de concentração", "frequencia": "ocasional"}
            ],
        },
        marcadores_origem={
            "ideacao_suicida": 0,
            "planejamento_suicida": 0,
            "autoagressao_iminente": 0,
            "risco_violencia": 0,
            "sintomas_psicoticos": 0,
            "uso_problematico_substancias": 0,
            "internacao_previa": 0,
            "agravamento_recente": 1,
            "suporte_social_baixo": 0,
            "comprometimento_funcional": 1,
        },
        prompt_version="test_prompt_v1",
    )


class LLMNarrativeGeneratorTests(unittest.TestCase):
    def test_rejects_pending_backend_placeholders(self) -> None:
        with self.assertRaises(ValueError):
            StructuredLLMClient(
                {
                    "backend": "CONFIGURE_BACKEND",
                    "model_id": "CONFIGURE_MODEL_ID",
                },
                completion_callable=_FakeCompletion({}),
            )

    def test_routes_backend_and_returns_safe_contract(self) -> None:
        completion = _FakeCompletion(
            {
                "subjective": "Refere sintomas de ansiedade e relata piora recente.",
                "assessment": "Narrativa sintética coerente com os dados informados.",
            }
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={
                "backend": "openai",
                "model_id": "modelo-teste",
                "response_format": "json_schema",
                "send_seed": True,
            },
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )

        with self.assertLogs("emulti_pipeline.llm_calls", level="INFO") as captured:
            response = generator.generate(
                _request(),
                progress_index=2,
                progress_total=5,
            )

        self.assertEqual(response.patient_id, "SYN-0001")
        self.assertTrue(response.narrativa_clinica.startswith("S - "))
        self.assertIn("\nA - ", response.narrativa_clinica)
        self.assertEqual(response.generation_metadata["backend"], "openai")
        self.assertTrue(response.generation_metadata["api_called"])
        self.assertEqual(response.generation_metadata["forbidden_label_check"], "passed")
        self.assertNotIn("api_key", response.generation_metadata)
        self.assertEqual(len(completion.calls), 1)
        logs = "\n".join(captured.output)
        self.assertIn("patient_id=SYN-0001", logs)
        self.assertIn("operation=2/5", logs)
        self.assertIn("attempt=1/1", logs)
        self.assertIn("planned_remaining=3", logs)

        call = completion.calls[0]
        self.assertEqual(call["model"], "openai/modelo-teste")
        self.assertEqual(call["response_format"]["type"], "json_schema")
        self.assertEqual(call["seed"], 1234)
        user_prompt = call["messages"][1]["content"]
        self.assertNotIn("prioridade_referencia", user_prompt)
        self.assertNotIn("prioridade_prevista", user_prompt)
        payload_text = user_prompt.split("Os dados abaixo são a única fonte de informação permitida:\n", 1)[1]
        self.assertNotIn("phq", payload_text.lower())
        self.assertNotIn("gad", payload_text.lower())
        self.assertNotIn("idate", payload_text.lower())
        self.assertNotIn("escore", payload_text.lower())

    def test_logs_retry_and_recovers_after_invalid_json(self) -> None:
        valid = json.dumps(
            {
                "subjective": "Refere tensão ocasional.",
                "assessment": "Narrativa sintética coerente.",
            },
            ensure_ascii=False,
        )
        completion = _SequenceCompletion([('{"subjective": "incompleta', "stop"), (valid, "stop")])
        generator = LLMNarrativeGenerator(
            llm_configuration={"backend": "openai", "model_id": "modelo-teste"},
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=1,
            retry_backoff_seconds=0,
        )

        with self.assertLogs("emulti_pipeline.llm_calls", level="INFO") as captured:
            response = generator.generate(_request(), progress_index=1, progress_total=4)

        self.assertEqual(response.generation_metadata["retry_count"], 1)
        self.assertEqual(len(completion.calls), 2)
        logs = "\n".join(captured.output)
        self.assertIn("LLM_RETRY", logs)
        self.assertIn("next_attempt=2/2", logs)
        self.assertIn("error_type=JSONDecodeError", logs)

    def test_detects_provider_truncation_before_parsing_json(self) -> None:
        completion = _SequenceCompletion([('{"subjective": "incompleta', "MAX_TOKENS")])
        client = StructuredLLMClient(
            {"backend": "gemini", "model_id": "modelo-teste"},
            completion_callable=completion,
        )

        with self.assertRaises(LLMResponseTruncatedError):
            client.generate_json(
                system_instruction="Sistema",
                prompt="Solicitação",
                response_schema={"type": "object", "properties": {}},
                schema_name="test",
                temperature=0.0,
                max_output_tokens=10,
                trace_context={"patient_id": "SYN-0001"},
            )

    def test_translates_item_responses_without_exposing_instruments_or_scores(self) -> None:
        scales = {
            **{f"phq9_item_{index:02d}": 0 for index in range(1, 10)},
            **{f"gad7_item_{index:02d}": 0 for index in range(1, 8)},
            **{f"idate_estado_item_{index:02d}_score": 1 for index in range(1, 21)},
            "phq9_total": 0,
            "gad7_total": 0,
            "idate_estado_total": 20,
        }
        scales["phq9_item_07"] = 2
        scales["gad7_item_04"] = 3

        context = build_qualitative_psychological_context(scales)
        serialized = json.dumps(context, ensure_ascii=False).lower()

        self.assertIn("dificuldade de concentração", serialized)
        self.assertIn("dificuldade para relaxar", serialized)
        for forbidden in ("phq", "gad", "idate", "item", "total", "escore", "pontuação"):
            self.assertNotIn(forbidden, serialized)

    def test_rejects_raw_psychometric_key_in_narrative_request(self) -> None:
        completion = _FakeCompletion(
            {"subjective": "Relato sintético.", "assessment": "Avaliação sintética."}
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={"backend": "openai", "model_id": "modelo-teste"},
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )
        request = _request()
        object.__setattr__(
            request,
            "manifestacoes_psicologicas",
            {"sintese": "qualitativa", "phq9_total": 12},
        )

        with self.assertRaises(ValueError):
            generator.generate(request)
        self.assertEqual(completion.calls, [])

    def test_rejects_numeric_value_disguised_as_qualitative_context(self) -> None:
        completion = _FakeCompletion(
            {"subjective": "Relato sintético.", "assessment": "Avaliação sintética."}
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={"backend": "openai", "model_id": "modelo-teste"},
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )
        request = _request()
        object.__setattr__(
            request,
            "manifestacoes_psicologicas",
            {
                "sintese": "qualitativa",
                "estado_emocional_atual": "tensão ocasional",
                "manifestacoes_relevantes": [
                    {"descricao": "dificuldade de concentração", "frequencia": 2}
                ],
            },
        )

        with self.assertRaises(ValueError):
            generator.generate(request)
        self.assertEqual(completion.calls, [])

    def test_rejects_narrative_that_mentions_psychometric_score(self) -> None:
        completion = _FakeCompletion(
            {
                "subjective": "Apresentou pontuação de 12 pontos no questionário.",
                "assessment": "Avaliação sintética.",
            }
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={"backend": "openai", "model_id": "modelo-teste"},
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )

        with self.assertRaises(RuntimeError):
            generator.generate(_request())
        self.assertEqual(len(completion.calls), 1)

    def test_anthropic_backend_is_selected_only_by_configuration(self) -> None:
        completion = _FakeCompletion(
            {"subjective": "Relato sintético.", "assessment": "Avaliação sintética."}
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={
                "backend": "anthropic",
                "model_id": "modelo-teste",
                "response_format": "json_object",
            },
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )

        generator.generate(_request())

        call = completion.calls[0]
        self.assertEqual(call["model"], "anthropic/modelo-teste")
        self.assertEqual(call["response_format"], {"type": "json_object"})

    def test_fails_when_forbidden_label_field_is_nested(self) -> None:
        completion = _FakeCompletion(
            {"subjective": "Relato.", "assessment": "Avaliação."}
        )
        generator = LLMNarrativeGenerator(
            llm_configuration={"backend": "openai", "model_id": "modelo-teste"},
            generator_id="llm-test",
            completion_callable=completion,
            max_retries=0,
        )
        request = _request()
        object.__setattr__(
            request,
            "dados_estruturados",
            {"contexto": {"prioridade_referencia": "alta"}},
        )

        with self.assertRaises(ValueError):
            generator.generate(request)
        self.assertEqual(completion.calls, [])

    def test_factory_keeps_template_as_default(self) -> None:
        generator = create_narrative_generator({"generator_id": "template-test"})
        self.assertIsInstance(generator, TemplateNarrativeGenerator)
        self.assertEqual(generator.generator_id, "template-test")


class ConfigInheritanceTests(unittest.TestCase):
    def test_extends_merges_nested_llm_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            (directory / "base.yaml").write_text(
                "narrative:\n  provider: template\n  language: pt-BR\n  llm:\n    backend: openai\n    model_id: base-model\n",
                encoding="utf-8",
            )
            (directory / "child.yaml").write_text(
                "extends: base.yaml\nnarrative:\n  provider: llm\n  llm:\n    backend: anthropic\n    model_id: child-model\n",
                encoding="utf-8",
            )
            config = load_config(directory / "child.yaml")

        self.assertEqual(config["narrative"]["provider"], "llm")
        self.assertEqual(config["narrative"]["language"], "pt-BR")
        self.assertEqual(config["narrative"]["llm"]["backend"], "anthropic")
        self.assertEqual(config["narrative"]["llm"]["model_id"], "child-model")


if __name__ == "__main__":
    unittest.main()

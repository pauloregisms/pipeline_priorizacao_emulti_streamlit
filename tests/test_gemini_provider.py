"""Testes sem rede para o adaptador Gemini e a fábrica de provedores."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from emulti_pipeline.config import load_config
from emulti_pipeline.narrative_providers.gemini import GeminiNarrativeGenerator
from emulti_pipeline.narratives import (
    NarrativeRequest,
    TemplateNarrativeGenerator,
    create_narrative_generator,
)


class _FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "subjective": "Refere sintomas de ansiedade e relata piora recente.",
                    "assessment": "Narrativa sintética coerente com os dados informados.",
                },
                ensure_ascii=False,
            ),
            model_version="fake-model-version",
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=15,
                total_token_count=25,
            ),
        )


class _FakeGeminiClient:
    def __init__(self) -> None:
        self.models = _FakeModels()


def _request() -> NarrativeRequest:
    return NarrativeRequest(
        patient_id="SYN-0001",
        seed=1234,
        dados_estruturados={"age_years": 35, "social_vulnerability": 0.4},
        indicadores_psicometricos={"phq9_total": 12, "gad7_total": 11, "idate_estado_total": 52},
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


class GeminiNarrativeGeneratorTests(unittest.TestCase):
    def test_returns_contract_and_registers_safe_metadata(self) -> None:
        client = _FakeGeminiClient()
        generator = GeminiNarrativeGenerator(
            model_id="gemini-test",
            generator_id="gemini-api-test",
            client=client,
            max_retries=0,
        )

        response = generator.generate(_request())

        self.assertEqual(response.patient_id, "SYN-0001")
        self.assertTrue(response.narrativa_clinica.startswith("S - "))
        self.assertIn("\nA - ", response.narrativa_clinica)
        self.assertEqual(response.generation_metadata["provider"], "gemini")
        self.assertTrue(response.generation_metadata["api_called"])
        self.assertEqual(response.generation_metadata["forbidden_label_check"], "passed")
        self.assertNotIn("api_key", response.generation_metadata)
        self.assertEqual(len(client.models.calls), 1)

        call = client.models.calls[0]
        self.assertEqual(call["model"], "gemini-test")
        self.assertEqual(call["config"]["response_mime_type"], "application/json")
        self.assertEqual(call["config"]["seed"], 1234)
        # O prompt possui apenas os três grupos de atributos permitidos.
        self.assertNotIn("prioridade_referencia", call["contents"])
        self.assertNotIn("prioridade_prevista", call["contents"])

    def test_fails_when_forbidden_label_field_is_nested(self) -> None:
        client = _FakeGeminiClient()
        generator = GeminiNarrativeGenerator(
            model_id="gemini-test",
            generator_id="gemini-api-test",
            client=client,
            max_retries=0,
        )
        request = _request()
        object.__setattr__(request, "dados_estruturados", {"contexto": {"prioridade_referencia": "alta"}})

        with self.assertRaises(ValueError):
            generator.generate(request)
        self.assertEqual(client.models.calls, [])

    def test_factory_keeps_template_as_default(self) -> None:
        generator = create_narrative_generator({"generator_id": "template-test"})
        self.assertIsInstance(generator, TemplateNarrativeGenerator)
        self.assertEqual(generator.generator_id, "template-test")


class ConfigInheritanceTests(unittest.TestCase):
    def test_extends_merges_nested_narrative_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            (directory / "base.yaml").write_text(
                "narrative:\n  provider: template\n  language: pt-BR\n  gemini:\n    model_id: base-model\n",
                encoding="utf-8",
            )
            (directory / "child.yaml").write_text(
                "extends: base.yaml\nnarrative:\n  provider: gemini\n  gemini:\n    model_id: child-model\n",
                encoding="utf-8",
            )
            config = load_config(directory / "child.yaml")

        self.assertEqual(config["narrative"]["provider"], "gemini")
        self.assertEqual(config["narrative"]["language"], "pt-BR")
        self.assertEqual(config["narrative"]["gemini"]["model_id"], "child-model")


if __name__ == "__main__":
    unittest.main()

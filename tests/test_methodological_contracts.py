"""Testes dos contratos que sustentam as comparações metodológicas."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

import pandas as pd

from emulti_pipeline.config import load_config
from emulti_pipeline.extraction_providers.llm import LLMClinicalExtractor
from emulti_pipeline.features import build_analytical_sets
from emulti_pipeline.markers import MARKER_NAMES, flatten_markers
from emulti_pipeline.priority import apply_priority_matrix


def _empty_markers() -> dict:
    return {marker: {} for marker in MARKER_NAMES}


class _FakeCompletion:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = []

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
            usage={},
        )


class MethodologicalContractTests(unittest.TestCase):
    def test_llm_extractor_receives_only_narrative(self) -> None:
        markers = _empty_markers()
        markers["ideacao_suicida"] = {
            "present": 0,
            "negated": 1,
            "remote_present": 1,
            "temporality": "atual",
            "severity": "ausente",
            "severity_code": 0,
            "certainty": "afirmado",
            "experiencer": "paciente",
            "evidence": "nega ideação suicida atualmente",
        }
        normalized = {}
        for marker, value in markers.items():
            normalized[marker] = {
                "present": int(value.get("present", 0)),
                "negated": int(value.get("negated", 0)),
                "remote_present": int(value.get("remote_present", 0)),
                "temporality": value.get("temporality", "nao_especificado"),
                "severity": value.get("severity", "ausente"),
                "severity_code": int(value.get("severity_code", 0)),
                "certainty": value.get("certainty", "afirmado"),
                "experiencer": value.get("experiencer", "paciente"),
                "evidence": value.get("evidence", ""),
            }
        completion = _FakeCompletion({"markers": normalized})
        extractor = LLMClinicalExtractor(
            llm_configuration={
                "backend": "anthropic",
                "model_id": "modelo-teste",
                "response_format": "json_schema",
            },
            extractor_id="test",
            ontology_version="v2",
            prompt_version="p1",
            completion_callable=completion,
            max_retries=0,
        )
        with self.assertLogs("emulti_pipeline.llm_calls", level="INFO") as captured:
            result = extractor.extract(
                pd.DataFrame(
                    {
                        "patient_id": ["SYN-1"],
                        "narrativa_clinica": [
                            "Nega ideação atual; houve ideação no passado."
                        ],
                    }
                ),
                progress_offset=3,
                progress_total=10,
                progress_phase="stability_1_of_3",
            )
        call = completion.calls[0]
        self.assertEqual(call["model"], "anthropic/modelo-teste")
        user_prompt = call["messages"][1]["content"]
        self.assertIn("Narrativa (única fonte permitida)", user_prompt)
        self.assertNotIn("prioridade", user_prompt.lower())
        self.assertEqual(result.loc[0, "marcadores_extraidos_ideacao_suicida_remote_present"], 1)
        logs = "\n".join(captured.output)
        self.assertIn("stage=06_extract_markers", logs)
        self.assertIn("phase=stability_1_of_3", logs)
        self.assertIn("patient_id=SYN-1", logs)
        self.assertIn("operation=4/10", logs)

    def test_origin_and_extracted_sets_have_identical_feature_schema(self) -> None:
        origin = flatten_markers(_empty_markers(), "marcadores_origem_")
        extracted_values = flatten_markers(_empty_markers(), "marcadores_extraidos_")
        profiles = pd.DataFrame([{"patient_id": "SYN-1", "seed": 11, "age_years": 40, "social_vulnerability": 0.4, "gravidade_latente_auditoria": 0.2, **origin}])
        psychometrics = pd.DataFrame([{"patient_id": "SYN-1", "phq9_total": 5, "gad7_total": 4, "idate_estado_total": 35}])
        priority = pd.DataFrame([{"patient_id": "SYN-1", "prioridade_referencia": "baixa", "prioridade_referencia_codigo": 0, "urgent_rule_triggered": 0}])
        extracted = pd.DataFrame([{"patient_id": "SYN-1", **extracted_values}])
        config = load_config("config/base.yaml")
        datasets = build_analytical_sets(profiles, psychometrics, priority, extracted, config)
        upper = datasets["02_limite_superior_marcadores_origem"]
        operational = datasets["03_operacional_marcadores_extraidos"]
        self.assertEqual(list(upper.columns), list(operational.columns))
        self.assertNotIn("seed", upper.columns)
        self.assertTrue(any(column.startswith("marker_ideacao_suicida_") for column in upper.columns))

    def test_same_priority_matrix_for_origin_and_extracted_contracts(self) -> None:
        rules = load_config("config/base.yaml")["priority_rules"]
        markers = _empty_markers()
        markers["ideacao_suicida"] = {"present": 1, "temporality": "atual"}
        markers["planejamento_suicida"] = {"present": 1, "temporality": "atual", "severity_code": 3, "severity": "alto"}
        base = {"phq9_total": 5, "gad7_total": 4, "idate_estado_total": 35, "social_vulnerability": 0.2}
        origin = pd.DataFrame([{**base, **flatten_markers(markers, "marcadores_origem_")}])
        extracted = pd.DataFrame([{**base, **flatten_markers(markers, "marcadores_extraidos_")}])
        self.assertEqual(
            apply_priority_matrix(origin, rules, "marcadores_origem_").loc[0, "priority_label"],
            apply_priority_matrix(extracted, rules, "marcadores_extraidos_").loc[0, "priority_label"],
        )


if __name__ == "__main__":
    unittest.main()

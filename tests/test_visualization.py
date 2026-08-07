"""Testes da tabela simplificada de classificação."""

from __future__ import annotations

import unittest

import pandas as pd

from emulti_pipeline.visualization import build_simplified_classification_table


class SimplifiedClassificationTableTests(unittest.TestCase):
    def test_sorts_urgent_before_other_priorities_and_formats_columns(self) -> None:
        profiles = pd.DataFrame(
            {
                "patient_id": ["SYN-1", "SYN-2", "SYN-3"],
                "age_years": [30, 45, 52],
                "gender_category": ["feminino", "masculino", "outro_ou_nao_informado"],
                "social_vulnerability": [0.2, 0.8, 0.5],
            }
        )
        psychometrics = pd.DataFrame(
            {
                "patient_id": ["SYN-1", "SYN-2", "SYN-3"],
                "phq9_total": [4, 22, 14],
                "gad7_total": [3, 17, 11],
                "idate_estado_total": [35, 70, 56],
            }
        )
        extracted = pd.DataFrame(
            {
                "patient_id": ["SYN-1", "SYN-2", "SYN-3"],
                "marcadores_extraidos_ideacao_suicida_present": [0, 1, 0],
                "marcadores_extraidos_planejamento_suicida_present": [0, 1, 0],
                "marcadores_extraidos_autoagressao_iminente_present": [0, 0, 0],
                "marcadores_extraidos_risco_violencia_present": [0, 0, 0],
                "marcadores_extraidos_sintomas_psicoticos_present": [0, 0, 0],
                "marcadores_extraidos_uso_problematico_substancias_present": [0, 1, 0],
                "marcadores_extraidos_internacao_previa_present": [0, 0, 0],
                "marcadores_extraidos_agravamento_recente_present": [0, 1, 1],
                "marcadores_extraidos_suporte_social_baixo_present": [0, 1, 0],
                "marcadores_extraidos_comprometimento_funcional_severity_code": [0, 3, 2],
            }
        )
        predictions = pd.DataFrame(
            {
                "patient_id": ["SYN-1", "SYN-2", "SYN-3"],
                "prioridade_referencia_codigo": [0, 3, 2],
                "prioridade_prevista_codigo": [0, 3, 2],
                "prioridade_referencia": ["baixa", "urgente", "alta"],
                "prioridade_prevista": ["baixa", "urgente", "alta"],
                "proba_0": [0.8, 0.01, 0.02],
                "proba_1": [0.1, 0.01, 0.08],
                "proba_2": [0.08, 0.08, 0.75],
                "proba_3": [0.02, 0.90, 0.15],
            }
        )

        table = build_simplified_classification_table(
            profiles, psychometrics, extracted, predictions, include_reference=True
        )

        self.assertEqual(table.loc[0, "Prioridade prevista"], "Urgente")
        self.assertEqual(table.loc[0, "ID do perfil sintético"], "SYN-2")
        self.assertEqual(table.loc[0, "Concorda com a referência simulada?"], "Sim")
        self.assertIn("Ideação suicida", table.loc[0, "Sinais de atenção extraídos"])
        self.assertEqual(table.loc[0, "Probabilidade alta/urgente"], "98.0%")


if __name__ == "__main__":
    unittest.main()

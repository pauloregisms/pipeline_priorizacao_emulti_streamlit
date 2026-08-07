"""Etapa 14: gera uma tabela simplificada e ordenada da classificação final.

A tabela consolida previsões do conjunto-teste final com atributos e escores dos
perfis sintéticos. Ela é destinada à inspeção dos resultados experimentais e não
representa uma fila clínica ou recomendação assistencial.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.utils import read_json, save_csv, setup_logging, stage_dir, write_json
from emulti_pipeline.visualization import (
    build_simplified_classification_table,
    save_simplified_classification_table,
)


DEFAULT_DATASET = "03_operacional_marcadores_extraidos"


def _select_model(modeling_summary: pd.DataFrame, dataset: str, requested_model: str) -> tuple[str, str]:
    """Resolve o modelo solicitado sem escolher pelo desempenho do teste final.

    Quando ``requested_model`` é ``best``, a escolha usa somente a média F1 macro
    obtida na validação aninhada do conjunto de desenvolvimento. Assim, a tabela do
    teste final não é usada para selecionar retrospectivamente o modelo.
    """
    candidates = modeling_summary.loc[modeling_summary["dataset"] == dataset].copy()
    if candidates.empty:
        available = sorted(modeling_summary["dataset"].dropna().unique().tolist())
        raise ValueError(f"Conjunto analítico '{dataset}' não encontrado. Disponíveis: {available}")

    if requested_model != "best":
        if requested_model not in set(candidates["model"]):
            available = sorted(candidates["model"].dropna().unique().tolist())
            raise ValueError(f"Modelo '{requested_model}' não encontrado para '{dataset}'. Disponíveis: {available}")
        return requested_model, "modelo informado explicitamente por --model"

    required = {"model", "development_f1_macro"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"modeling_summary.csv sem colunas para seleção do modelo: {sorted(missing)}")

    best_row = candidates.sort_values(
        by=["development_f1_macro", "model"], ascending=[False, True], kind="stable"
    ).iloc[0]
    return str(best_row["model"]), "maior F1 macro na validação cruzada aninhada (desenvolvimento)"


def main() -> None:
    parser = common_parser("Gera tabela ordenada da classificação final de perfis sintéticos.")
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Conjunto analítico usado pelo modelo. Padrão: {DEFAULT_DATASET}.",
    )
    parser.add_argument(
        "--model",
        default="best",
        help="Nome do modelo ou 'best' para selecionar por F1 macro da validação aninhada.",
    )
    parser.add_argument(
        "--include-reference",
        action="store_true",
        help="Inclui prioridade_referencia e concordância. Use apenas para avaliação sintética, não para visão operacional.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging("14_export_priority_table")
    run_root = stage_dir(config, args.run_id, "14_priority_view").parent
    model_root = run_root / "10_modeling"
    summary_path = model_root / "modeling_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError("modeling_summary.csv não encontrado. Execute 10_train_evaluate_models.py primeiro.")

    summary = pd.read_csv(summary_path)
    model_name, selection_criterion = _select_model(summary, args.dataset, args.model)
    predictions_path = model_root / args.dataset / model_name / "final_test_predictions.csv"
    if not predictions_path.exists():
        raise FileNotFoundError(
            f"Previsões do teste final não encontradas: {predictions_path}. "
            "Verifique dataset, modelo e run_id."
        )

    profiles = pd.read_csv(run_root / "01_profiles" / "profiles.csv")
    psychometrics = pd.read_csv(run_root / "02_psychometrics" / "psychometrics.csv")
    extracted = pd.read_csv(run_root / "06_extraction" / "marcadores_extraidos.csv")
    predictions = pd.read_csv(predictions_path)

    table = build_simplified_classification_table(
        profiles,
        psychometrics,
        extracted,
        predictions,
        include_reference=bool(args.include_reference),
    )
    output = stage_dir(config, args.run_id, "14_priority_view")
    csv_path, html_path = save_simplified_classification_table(table, output)

    narratives = pd.read_csv(run_root / "04_narratives" / "narratives_index.csv")
    priority = pd.read_csv(run_root / "05_priority" / "prioridade_referencia.csv")
    priority_metadata = read_json(run_root / "05_priority" / "priority_metadata.json")
    extraction_manifest = read_json(run_root / "06_extraction" / "extraction_manifest.json")
    run_metadata = read_json(run_root / "run_metadata.json")
    traceability = predictions.merge(
        profiles[["patient_id", "seed"]], on="patient_id", how="left", validate="one_to_one"
    )
    narrative_columns = [
        column
        for column in ["patient_id", "narrative_id", "generator_id", "prompt_version", "input_hash"]
        if column in narratives
    ]
    traceability = traceability.merge(narratives[narrative_columns], on="patient_id", how="left", validate="one_to_one")
    extraction_columns = [
        column
        for column in ["patient_id", "extractor_id", "ontology_version", "model_id", "prompt_version", "prompt_hash", "extraction_status", "retry_count"]
        if column in extracted
    ]
    traceability = traceability.merge(
        extracted[extraction_columns], on="patient_id", how="left", validate="one_to_one", suffixes=("_generation", "_extraction")
    )
    traceability = traceability.merge(
        priority[["patient_id", "priority_score", "urgent_rule_triggered"]],
        on="patient_id",
        how="left",
        validate="one_to_one",
    )
    traceability["run_id"] = args.run_id
    traceability["config_hash"] = run_metadata["config_hash"]
    traceability["priority_rule_version"] = priority_metadata["rule_version"]
    traceability["extraction_provider"] = extraction_manifest["provider"]
    traceability["dataset"] = args.dataset
    traceability["selected_model"] = model_name
    save_csv(traceability, output / "prediction_traceability.csv")

    priority_distribution = table["Prioridade prevista"].value_counts().to_dict()
    write_json(
        output / "priority_view_manifest.json",
        {
            "dataset": args.dataset,
            "selected_model": model_name,
            "model_selection_criterion": selection_criterion,
            "predictions_source": str(predictions_path.relative_to(run_root)),
            "n_profiles_in_final_test": int(len(table)),
            "priority_distribution": priority_distribution,
            "include_reference_simulated": bool(args.include_reference),
            "csv": csv_path.name,
            "html": html_path.name,
            "traceability": "prediction_traceability.csv",
            "warning": (
                "Tabela para inspeção de perfis sintéticos. Não representa fila clínica, "
                "prioridade de pacientes reais ou recomendação assistencial."
            ),
        },
    )
    logger.info("Tabela criada com %d perfis usando o modelo %s: %s", len(table), model_name, csv_path)


if __name__ == "__main__":
    main()

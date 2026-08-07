"""Etapa 10: validação interna aninhada e teste final isolado.

A modelagem compara uma regra-base observável, regressão logística ordinal, Random
Forest e XGBoost. A prioridade de referência é um rótulo simulado; as métricas devem
ser interpretadas como recuperação de prioridade_referencia, não como validação clínica.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.evaluation import bootstrap_metric_intervals, calculate_classification_metrics, calibration_curve_table
from emulti_pipeline.models import build_model_registry, infer_feature_types
from emulti_pipeline.priority import PRIORITY_ORDER, PRIORITY_TO_CODE, rule_baseline_from_available_features
from emulti_pipeline.utils import save_csv, setup_logging, stage_dir, write_json


def _class_counts_ok(y: pd.Series, n_splits: int) -> bool:
    return int(y.value_counts().min()) >= n_splits


def _align_probabilities(estimator: Any, raw_probabilities: np.ndarray, n_classes: int = 4) -> np.ndarray:
    """Alinha a ordem de colunas de um estimador à codificação 0..3."""
    classes = getattr(estimator, "classes_", None)
    if classes is None and hasattr(estimator, "named_steps"):
        classes = getattr(estimator.named_steps["model"], "classes_", None)
    if classes is None:
        return raw_probabilities
    aligned = np.zeros((raw_probabilities.shape[0], n_classes), dtype=float)
    for source_index, class_code in enumerate(classes):
        aligned[:, int(class_code)] = raw_probabilities[:, source_index]
    aligned = np.clip(aligned, 1e-9, None)
    return aligned / aligned.sum(axis=1, keepdims=True)


def _save_evaluation(output: Path, prefix: str, prioridade_referencia_codigo: np.ndarray, prioridade_prevista_codigo: np.ndarray, probability: np.ndarray | None, bootstrap_reps: int, seed: int, calibration_bins: int = 10) -> dict[str, float]:
    metrics, per_class, matrix = calculate_classification_metrics(prioridade_referencia_codigo, prioridade_prevista_codigo, probability)
    save_csv(pd.DataFrame([metrics]), output / f"{prefix}_metrics.csv")
    save_csv(per_class, output / f"{prefix}_per_class.csv")
    matrix.to_csv(output / f"{prefix}_confusion_matrix.csv", encoding="utf-8")
    prediction_payload = {
            "prioridade_referencia_codigo": prioridade_referencia_codigo,
            "prioridade_prevista_codigo": prioridade_prevista_codigo,
    }
    if probability is not None:
        prediction_payload.update({f"proba_{index}": probability[:, index] for index in range(4)})
        save_csv(
            calibration_curve_table(prioridade_referencia_codigo, probability, calibration_bins),
            output / f"{prefix}_calibration_curves.csv",
        )
    intervals = bootstrap_metric_intervals(
        pd.DataFrame(prediction_payload),
        bootstrap_reps,
        seed,
    )
    save_csv(intervals, output / f"{prefix}_bootstrap_intervals.csv")
    return metrics


def _run_rule_baseline(
    X_dev: pd.DataFrame,
    y_dev: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    patient_ids_test: pd.Series,
    output: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Avalia a regra observável sem treinamento; ela é uma linha de base obrigatória."""
    dev_labels = rule_baseline_from_available_features(X_dev, config)
    test_labels = rule_baseline_from_available_features(X_test, config)
    dev_pred = np.asarray([PRIORITY_TO_CODE[label] for label in dev_labels], dtype=int)
    test_pred = np.asarray([PRIORITY_TO_CODE[label] for label in test_labels], dtype=int)
    dev_output = output / "rule_baseline"
    dev_output.mkdir(parents=True, exist_ok=True)
    nested_metrics = _save_evaluation(dev_output, "development_reference", y_dev, dev_pred, None, config["modeling"]["bootstrap_repetitions"], config["modeling"]["random_state"])
    final_metrics = _save_evaluation(dev_output, "final_test", y_test, test_pred, None, config["modeling"]["bootstrap_repetitions"], config["modeling"]["random_state"] + 1)
    predictions = pd.DataFrame({
        "patient_id": patient_ids_test.to_numpy(),
        "set": "final_test",
        "prioridade_referencia_codigo": y_test,
        "prioridade_prevista_codigo": test_pred,
        "prioridade_referencia": [PRIORITY_ORDER[index] for index in y_test],
        "prioridade_prevista": [PRIORITY_ORDER[index] for index in test_pred],
    })
    save_csv(predictions, dev_output / "final_test_predictions.csv")
    return {"model": "rule_baseline", "development_f1_macro": nested_metrics["f1_macro"], "final_test_f1_macro": final_metrics["f1_macro"]}


def _run_trainable_model(
    name: str,
    estimator: Any,
    param_grid: dict[str, list[Any]],
    X_dev: pd.DataFrame,
    y_dev: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    patient_ids_test: pd.Series,
    patient_ids_dev: pd.Series,
    config: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    """Executa CV aninhada no desenvolvimento e teste final isolado."""
    model_cfg = config["modeling"]
    model_output = output / name
    model_output.mkdir(parents=True, exist_ok=True)
    outer = StratifiedKFold(n_splits=int(model_cfg["outer_splits"]), shuffle=True, random_state=int(model_cfg["random_state"]))

    outer_rows: list[pd.DataFrame] = []
    chosen_params: list[dict[str, Any]] = []
    for fold_index, (train_index, valid_index) in enumerate(outer.split(X_dev, y_dev), start=1):
        X_train = X_dev.iloc[train_index]
        X_valid = X_dev.iloc[valid_index]
        y_train = y_dev[train_index]
        y_valid = y_dev[valid_index]
        inner = StratifiedKFold(n_splits=int(model_cfg["inner_splits"]), shuffle=True, random_state=int(model_cfg["random_state"]) + fold_index)
        search = GridSearchCV(
            estimator=estimator,
            param_grid=param_grid,
            scoring=model_cfg["scoring"],
            cv=inner,
            n_jobs=1,  # evita concorrência excessiva quando modelos já usam múltiplos núcleos.
            refit=True,
            error_score="raise",
        )
        search.fit(X_train, y_train)
        raw_proba = search.best_estimator_.predict_proba(X_valid)
        proba = _align_probabilities(search.best_estimator_, raw_proba)
        pred = np.argmax(proba, axis=1)
        fitted_component = search.best_estimator_.named_steps.get("model")
        chosen_params.append(
            {
                "outer_fold": fold_index,
                "converged": getattr(fitted_component, "converged_", None),
                "optimization_message": getattr(fitted_component, "optimization_message_", None),
                **search.best_params_,
            }
        )
        outer_rows.append(pd.DataFrame({
            "outer_fold": fold_index,
            "patient_id": patient_ids_dev.iloc[valid_index].to_numpy(),
            "prioridade_referencia_codigo": y_valid,
            "prioridade_prevista_codigo": pred,
            **{f"proba_{index}": proba[:, index] for index in range(4)},
        }))

    outer_predictions = pd.concat(outer_rows, ignore_index=True)
    save_csv(outer_predictions, model_output / "nested_outer_predictions.csv")
    outer_metrics = _save_evaluation(
        model_output,
        "nested_outer",
        outer_predictions["prioridade_referencia_codigo"].to_numpy(),
        outer_predictions["prioridade_prevista_codigo"].to_numpy(),
        outer_predictions[[f"proba_{index}" for index in range(4)]].to_numpy(),
        int(model_cfg["bootstrap_repetitions"]),
        int(model_cfg["random_state"]) + 10,
        int(model_cfg.get("calibration_bins", 10)),
    )
    save_csv(pd.DataFrame(chosen_params), model_output / "nested_outer_best_parameters.csv")

    # Somente depois de completar a avaliação aninhada, ajustar hiperparâmetros em todo
    # o conjunto de desenvolvimento. O teste final permaneceu isolado até este ponto.
    final_inner = StratifiedKFold(n_splits=int(model_cfg["inner_splits"]), shuffle=True, random_state=int(model_cfg["random_state"]) + 999)
    final_search = GridSearchCV(
        estimator=estimator,
        param_grid=param_grid,
        scoring=model_cfg["scoring"],
        cv=final_inner,
        n_jobs=1,
        refit=True,
        error_score="raise",
    )
    final_search.fit(X_dev, y_dev)
    final_model = final_search.best_estimator_
    raw_test_proba = final_model.predict_proba(X_test)
    test_proba = _align_probabilities(final_model, raw_test_proba)
    test_pred = np.argmax(test_proba, axis=1)
    final_metrics = _save_evaluation(
        model_output,
        "final_test",
        y_test,
        test_pred,
        test_proba,
        int(model_cfg["bootstrap_repetitions"]),
        int(model_cfg["random_state"]) + 11,
        int(model_cfg.get("calibration_bins", 10)),
    )
    test_predictions = pd.DataFrame({
        "patient_id": patient_ids_test.to_numpy(),
        "prioridade_referencia_codigo": y_test,
        "prioridade_prevista_codigo": test_pred,
        "prioridade_referencia": [PRIORITY_ORDER[index] for index in y_test],
        "prioridade_prevista": [PRIORITY_ORDER[index] for index in test_pred],
        **{f"proba_{index}": test_proba[:, index] for index in range(4)},
    })
    save_csv(test_predictions, model_output / "final_test_predictions.csv")
    joblib.dump(final_model, model_output / "final_model.joblib")
    fitted_component = final_model.named_steps.get("model")
    write_json(model_output / "final_model_metadata.json", {
        "best_params": final_search.best_params_,
        "best_inner_score": float(final_search.best_score_),
        "model_name": name,
        "converged": getattr(fitted_component, "converged_", None),
        "optimization_message": getattr(fitted_component, "optimization_message_", None),
        "interpretation": "Modelo ajustado apenas no desenvolvimento; explicações devem usar conjunto-teste final.",
    })
    return {"model": name, "development_f1_macro": outer_metrics["f1_macro"], "final_test_f1_macro": final_metrics["f1_macro"], "final_best_params": final_search.best_params_}


def main() -> None:
    parser = common_parser("Executa validação aninhada e teste final dos modelos.")
    parser.add_argument("--dataset", default="all", help="Nome do CSV analítico ou 'all'.")
    parser.add_argument("--models", default="all", help="Lista separada por vírgulas: rule_baseline,ordinal_logit,random_forest,xgboost ou all.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("10_train_evaluate_models")
    model_cfg = config["modeling"]
    data_dir = stage_dir(config, args.run_id, "09_analytical_sets")
    output_root = stage_dir(config, args.run_id, "10_modeling")

    available_files = sorted(data_dir.glob("*.csv"))
    if not available_files:
        raise FileNotFoundError("Nenhum conjunto analítico encontrado. Execute 09_build_analytical_datasets.py.")
    selected = [path for path in available_files if args.dataset == "all" or path.stem == args.dataset]
    if not selected:
        raise ValueError(f"Dataset solicitado não encontrado: {args.dataset}")

    summary_rows = []
    for path in selected:
        dataset_name = path.stem
        frame = pd.read_csv(path)
        y = frame["prioridade_referencia_codigo"].to_numpy(dtype=int)
        if not _class_counts_ok(pd.Series(y), max(int(model_cfg["outer_splits"]), int(model_cfg["inner_splits"]))):
            counts = pd.Series(y).value_counts().to_dict()
            raise ValueError(f"Classes insuficientes para CV em {dataset_name}: {counts}. Aumente n_records ou ajuste parâmetros.")

        target_columns = ["patient_id", "prioridade_referencia", "prioridade_referencia_codigo", "urgent_rule_triggered"]
        X = frame.drop(columns=target_columns)
        patient_ids = frame["patient_id"]
        X_dev, X_test, y_dev, y_test, patient_ids_dev, patient_ids_test = train_test_split(
            X,
            y,
            patient_ids,
            test_size=float(model_cfg["final_test_size"]),
            stratify=y,
            random_state=int(model_cfg["random_state"]),
        )
        numeric, categorical = infer_feature_types(X, [])
        dataset_output = output_root / dataset_name
        dataset_output.mkdir(parents=True, exist_ok=True)
        write_json(dataset_output / "dataset_split_metadata.json", {
            "dataset": dataset_name,
            "n_total": int(len(frame)),
            "n_development": int(len(X_dev)),
            "n_final_test": int(len(X_test)),
            "class_distribution_total": pd.Series(y).value_counts().sort_index().to_dict(),
            "numeric_features": numeric,
            "categorical_features": categorical,
        })

        requested_models = {name.strip() for name in args.models.split(",")} if args.models != "all" else {"all"}
        # Linha de base é avaliada para cada conjunto, usando apenas as colunas presentes.
        if "all" in requested_models or "rule_baseline" in requested_models:
            summary_rows.append({"dataset": dataset_name, **_run_rule_baseline(
                X_dev, y_dev, X_test, y_test, patient_ids_test, dataset_output, config
            )})

        registry = build_model_registry(numeric, categorical, int(model_cfg["random_state"]), int(model_cfg["n_jobs"]))
        required_trainable = set(model_cfg.get("required_models", registry)) if "all" in requested_models else requested_models - {"rule_baseline"}
        unavailable = required_trainable - set(registry)
        if unavailable and bool(model_cfg.get("strict_dependencies", True)):
            raise ImportError(f"Modelos obrigatórios indisponíveis: {sorted(unavailable)}. Instale as dependências antes da análise.")
        for model_name, (estimator, grid) in registry.items():
            if "all" not in requested_models and model_name not in requested_models:
                continue
            logger.info("Ajustando %s no conjunto %s", model_name, dataset_name)
            summary_rows.append({"dataset": dataset_name, **_run_trainable_model(
                model_name, estimator, grid, X_dev, y_dev, X_test, y_test, patient_ids_test, patient_ids_dev,
                config, dataset_output,
            )})

    summary = pd.DataFrame(summary_rows)
    save_csv(summary, output_root / "modeling_summary.csv")
    logger.info("Modelagem concluída. Resumo salvo em %s", output_root / "modeling_summary.csv")


if __name__ == "__main__":
    main()

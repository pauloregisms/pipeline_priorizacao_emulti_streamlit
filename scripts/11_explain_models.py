"""Etapa 11: gera explicações em conjunto-teste final, não usado no ajuste."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.models import infer_feature_types
from emulti_pipeline.utils import save_csv, setup_logging, stage_dir, write_json


def _rebuild_final_test(frame: pd.DataFrame, config: dict):
    """Reconstrói deterministicamente a mesma partição final usada na etapa 10."""
    from sklearn.model_selection import train_test_split

    target_columns = ["patient_id", "prioridade_referencia", "prioridade_referencia_codigo", "urgent_rule_triggered"]
    X = frame.drop(columns=target_columns)
    y = frame["prioridade_referencia_codigo"].to_numpy(dtype=int)
    ids = frame["patient_id"]
    _, X_test, _, y_test, _, ids_test = train_test_split(
        X,
        y,
        ids,
        test_size=float(config["modeling"]["final_test_size"]),
        stratify=y,
        random_state=int(config["modeling"]["random_state"]),
    )
    return X_test, y_test, ids_test


def _feature_names(pipeline) -> list[str]:
    preprocessor = pipeline.named_steps["preprocessor"]
    return list(preprocessor.get_feature_names_out())


def _ordinal_coefficients(pipeline) -> pd.DataFrame:
    model = pipeline.named_steps["model"]
    names = _feature_names(pipeline)
    return pd.DataFrame({"feature": names, "coefficient": model.coef_, "abs_coefficient": np.abs(model.coef_)}).sort_values("abs_coefficient", ascending=False)


def _tree_shap_importance(pipeline, X_test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula importância global e exemplos locais de SHAP para modelos de árvores."""
    try:
        import shap
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError("A biblioteca shap não está instalada. Execute pip install -r requirements.txt.") from exc

    transformed = pipeline.named_steps["preprocessor"].transform(X_test)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    names = _feature_names(pipeline)
    model = pipeline.named_steps["model"]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(transformed)

    # SHAP possui formatos diferentes entre versões/modelos. A função abaixo reduz
    # para importância média absoluta agregada nas classes alta (2) e urgente (3).
    if isinstance(shap_values, list):
        selected = np.abs(np.asarray(shap_values[2])) + np.abs(np.asarray(shap_values[3]))
    else:
        array = np.asarray(shap_values)
        if array.ndim == 3:  # (amostras, atributos, classes)
            selected = np.abs(array[:, :, 2]) + np.abs(array[:, :, 3])
        else:  # saída binária ou formato alternativo
            selected = np.abs(array)
    global_importance = pd.DataFrame({"feature": names, "mean_abs_shap_highurgent": selected.mean(axis=0)}).sort_values("mean_abs_shap_highurgent", ascending=False)
    local = pd.DataFrame(selected[: min(10, len(selected))], columns=names)
    local.insert(0, "test_row_index", np.arange(len(local)))
    return global_importance, local


def main() -> None:
    parser = common_parser("Explica modelos usando somente o conjunto-teste final.")
    parser.add_argument("--dataset", default="all", help="Conjunto analítico a explicar ou 'all'.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("11_explain_models")
    data_root = stage_dir(config, args.run_id, "09_analytical_sets")
    dataset_paths = sorted(data_root.glob("*.csv")) if args.dataset == "all" else [data_root / f"{args.dataset}.csv"]
    missing = [path for path in dataset_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Conjunto analítico não encontrado: {missing[0]}")
    output_root = stage_dir(config, args.run_id, "11_explanations")
    summary = {"datasets": [], "interpretation": "SHAP/coeficientes descrevem contribuição para a previsão, não causalidade clínica."}

    for dataset_path in dataset_paths:
        dataset = dataset_path.stem
        frame = pd.read_csv(dataset_path)
        X_test, y_test, ids_test = _rebuild_final_test(frame, config)
        model_root = stage_dir(config, args.run_id, "10_modeling") / dataset
        output = output_root / dataset
        output.mkdir(parents=True, exist_ok=True)
        metadata = {"dataset": dataset, "n_test_rows": int(len(X_test)), "models": []}
        for model_name in ["ordinal_logit", "random_forest", "xgboost"]:
            model_path = model_root / model_name / "final_model.joblib"
            if not model_path.exists():
                continue
            pipeline = joblib.load(model_path)
            model_output = output / model_name
            model_output.mkdir(parents=True, exist_ok=True)
            if model_name == "ordinal_logit":
                save_csv(_ordinal_coefficients(pipeline), model_output / "ordinal_coefficients.csv")
                metadata["models"].append({"model": model_name, "method": "coeficientes", "file": "ordinal_coefficients.csv"})
            else:
                try:
                    importance, local = _tree_shap_importance(pipeline, X_test)
                    save_csv(importance, model_output / "global_shap_importance_highurgent.csv")
                    save_csv(local, model_output / "local_shap_absolute_examples.csv")
                    metadata["models"].append({"model": model_name, "method": "TreeSHAP", "file": "global_shap_importance_highurgent.csv"})
                except Exception as exc:
                    write_json(model_output / "shap_error.json", {"error": str(exc)})
                    logger.warning("SHAP falhou para %s/%s: %s", dataset, model_name, exc)
        save_csv(pd.DataFrame({"patient_id": ids_test.to_numpy(), "prioridade_referencia_codigo": y_test}), output / "test_patient_ids.csv")
        write_json(output / "explanation_metadata.json", {**metadata, "test_ids_file": "test_patient_ids.csv"})
        summary["datasets"].append(metadata)
    write_json(output_root / "explanation_summary.json", summary)
    logger.info("Explicações concluídas para %d conjunto(s)", len(dataset_paths))


if __name__ == "__main__":
    main()

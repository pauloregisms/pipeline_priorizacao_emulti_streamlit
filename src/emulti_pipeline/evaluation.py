"""Métricas de classificação, ordinalidade, calibração e incerteza."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    precision_recall_fscore_support,
    roc_auc_score,
)

from .utils import logit


def _safe_auc_ovr(prioridade_referencia_codigo: np.ndarray, probability: np.ndarray, n_classes: int) -> float:
    try:
        return float(roc_auc_score(prioridade_referencia_codigo, probability, multi_class="ovr", average="macro", labels=np.arange(n_classes)))
    except ValueError:
        return float("nan")


def _safe_auprc(prioridade_referencia_codigo: np.ndarray, probability: np.ndarray, target_class: int) -> float:
    binary = (prioridade_referencia_codigo == target_class).astype(int)
    if binary.min() == binary.max():
        return float("nan")
    return float(average_precision_score(binary, probability[:, target_class]))


def calibration_metrics(prioridade_referencia_codigo: np.ndarray, probability_highurgent: np.ndarray) -> dict[str, float]:
    """Calcula Brier, log loss e intercepto/inclinação de calibração binária."""
    binary = (prioridade_referencia_codigo >= 2).astype(int)
    probability = np.clip(probability_highurgent, 1e-6, 1 - 1e-6)
    brier = float(np.mean((binary - probability) ** 2))
    ll = float(log_loss(binary, np.column_stack([1 - probability, probability]), labels=[0, 1]))
    if binary.min() == binary.max():
        return {"brier_highurgent": brier, "log_loss_highurgent": ll, "calibration_intercept": float("nan"), "calibration_slope": float("nan")}
    calibration_model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    calibration_model.fit(logit(probability).reshape(-1, 1), binary)
    return {
        "brier_highurgent": brier,
        "log_loss_highurgent": ll,
        "calibration_intercept": float(calibration_model.intercept_[0]),
        "calibration_slope": float(calibration_model.coef_[0, 0]),
    }


def calculate_classification_metrics(prioridade_referencia_codigo: np.ndarray, prioridade_prevista_codigo: np.ndarray, probability: np.ndarray | None = None, labels: list[int] | None = None) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    """Compila métricas globais, por classe e matriz de confusão."""
    prioridade_referencia_codigo = np.asarray(prioridade_referencia_codigo, dtype=int)
    prioridade_prevista_codigo = np.asarray(prioridade_prevista_codigo, dtype=int)
    n_classes = probability.shape[1] if probability is not None else 4
    if labels is None:
        labels = list(range(n_classes))

    precision, recall, f1, support = precision_recall_fscore_support(prioridade_referencia_codigo, prioridade_prevista_codigo, labels=labels, zero_division=0)
    per_class = pd.DataFrame(
        {
            "class_code": labels,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    )
    matrix = pd.DataFrame(confusion_matrix(prioridade_referencia_codigo, prioridade_prevista_codigo, labels=labels), index=[f"referencia_{label}" for label in labels], columns=[f"prevista_{label}" for label in labels])

    metrics = {
        "f1_macro": float(f1_score(prioridade_referencia_codigo, prioridade_prevista_codigo, labels=labels, average="macro", zero_division=0)),
        "weighted_kappa": float(cohen_kappa_score(prioridade_referencia_codigo, prioridade_prevista_codigo, weights="quadratic")),
        "ordinal_mae": float(mean_absolute_error(prioridade_referencia_codigo, prioridade_prevista_codigo)),
        "recall_alta": float(recall[labels.index(2)]) if 2 in labels else float("nan"),
        "recall_urgente": float(recall[labels.index(3)]) if 3 in labels else float("nan"),
    }
    if probability is not None:
        one_hot = np.eye(n_classes)[prioridade_referencia_codigo]
        metrics.update(
            {
                "auc_roc_ovr_macro": _safe_auc_ovr(prioridade_referencia_codigo, probability, n_classes),
                "auprc_alta": _safe_auprc(prioridade_referencia_codigo, probability, 2),
                "auprc_urgente": _safe_auprc(prioridade_referencia_codigo, probability, 3),
                "multiclass_brier": float(np.mean(np.sum((one_hot - probability) ** 2, axis=1))),
                "multiclass_log_loss": float(log_loss(prioridade_referencia_codigo, probability, labels=labels)),
            }
        )
        metrics.update(calibration_metrics(prioridade_referencia_codigo, probability[:, 2] + probability[:, 3]))
    return metrics, per_class, matrix


def calibration_curve_table(
    prioridade_referencia_codigo: np.ndarray,
    probability: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Retorna pontos de calibração por classe e para o desfecho alta/urgente."""
    y = np.asarray(prioridade_referencia_codigo, dtype=int)
    rows: list[dict[str, Any]] = []
    targets = [(f"class_{index}", (y == index).astype(int), probability[:, index]) for index in range(probability.shape[1])]
    targets.append(("high_or_urgent", (y >= 2).astype(int), probability[:, 2] + probability[:, 3]))
    edges = np.linspace(0, 1, n_bins + 1)
    for target, observed, predicted in targets:
        bins = np.clip(np.digitize(predicted, edges[1:-1], right=True), 0, n_bins - 1)
        for bin_index in range(n_bins):
            selected = bins == bin_index
            if selected.any():
                rows.append(
                    {
                        "target": target,
                        "bin": bin_index,
                        "n": int(selected.sum()),
                        "mean_predicted": float(np.mean(predicted[selected])),
                        "observed_fraction": float(np.mean(observed[selected])),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_metric_intervals(predictions: pd.DataFrame, n_bootstrap: int, seed: int) -> pd.DataFrame:
    """Obtém IC percentil por bootstrap das previsões de teste/folds externos."""
    rng = np.random.default_rng(seed)
    if predictions.empty:
        return pd.DataFrame()
    values: list[dict[str, Any]] = []
    prioridade_referencia_codigo = predictions["prioridade_referencia_codigo"].to_numpy(dtype=int)
    prioridade_prevista_codigo = predictions["prioridade_prevista_codigo"].to_numpy(dtype=int)
    probability_columns = [f"proba_{i}" for i in range(4)]
    probabilities = (
        predictions[probability_columns].to_numpy(dtype=float)
        if set(probability_columns).issubset(predictions.columns)
        else None
    )
    class_indices = [np.flatnonzero(prioridade_referencia_codigo == label) for label in np.unique(prioridade_referencia_codigo)]
    for _ in range(n_bootstrap):
        # Reamostragem estratificada preserva todas as classes raras em cada réplica.
        sampled = np.concatenate(
            [rng.choice(indices, size=len(indices), replace=True) for indices in class_indices]
        )
        rng.shuffle(sampled)
        sampled_probability = probabilities[sampled] if probabilities is not None else None
        metric, _, _ = calculate_classification_metrics(prioridade_referencia_codigo[sampled], prioridade_prevista_codigo[sampled], sampled_probability)
        values.append(metric)
    boot = pd.DataFrame(values)
    interval_rows = []
    for column in boot.columns:
        interval_rows.append(
            {
                "metric": column,
                "bootstrap_lower_2_5": float(boot[column].quantile(0.025)),
                "bootstrap_upper_97_5": float(boot[column].quantile(0.975)),
            }
        )
    return pd.DataFrame(interval_rows)

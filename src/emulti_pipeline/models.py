"""Modelos e pipelines de pré-processamento para avaliação interna.

Inclui uma implementação compacta de regressão logística ordinal cumulativa. Ela evita
uma dependência adicional e permite manter o baseline ordinal explicitamente alinhado
à variável-alvo de quatro categorias.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class OrdinalLogitClassifier(BaseEstimator, ClassifierMixin):
    """Regressão logística ordinal proporcional com limiares ordenados.

    A probabilidade cumulativa é P(Y <= k) = sigmoid(theta_k - X beta).
    Os incrementos entre limiares são parametrizados por softplus para garantir que
    theta_1 < theta_2 < ... durante a otimização.
    """

    def __init__(self, alpha: float = 1.0, max_iter: int = 300, class_weight: str | None = "balanced") -> None:
        self.alpha = alpha
        self.max_iter = max_iter
        self.class_weight = class_weight

    @staticmethod
    def _softplus(values: np.ndarray) -> np.ndarray:
        return np.logaddexp(0.0, values)

    def _unpack(self, params: np.ndarray, n_features: int, n_classes: int) -> tuple[np.ndarray, np.ndarray]:
        beta = params[:n_features]
        raw_thresholds = params[n_features:]
        thresholds = np.empty(n_classes - 1, dtype=float)
        thresholds[0] = raw_thresholds[0]
        if n_classes > 2:
            thresholds[1:] = thresholds[0] + np.cumsum(self._softplus(raw_thresholds[1:]))
        return beta, thresholds

    def fit(self, X: Any, y: Any, sample_weight: np.ndarray | None = None) -> "OrdinalLogitClassifier":
        y_array = np.asarray(y, dtype=int)
        self.classes_ = np.unique(y_array)
        # Os rótulos precisam ser 0..K-1 para a forma cumulativa do modelo.
        if not np.array_equal(self.classes_, np.arange(len(self.classes_))):
            raise ValueError("OrdinalLogitClassifier requer rótulos codificados de 0 a K-1.")
        n_classes = len(self.classes_)
        if n_classes < 2:
            raise ValueError("A regressão ordinal exige ao menos duas classes.")
        n_features = X.shape[1]

        if sample_weight is None:
            weights = np.ones_like(y_array, dtype=float)
        else:
            weights = np.asarray(sample_weight, dtype=float)
        if self.class_weight == "balanced":
            counts = np.bincount(y_array, minlength=n_classes)
            class_weights = len(y_array) / (n_classes * np.maximum(counts, 1))
            weights = weights * class_weights[y_array]

        # Inicialização baseada em quantis da classe, evitando limiares coincidentes.
        cumulative = [np.mean(y_array <= category) for category in range(n_classes - 1)]
        cumulative = np.clip(cumulative, 0.05, 0.95)
        theta_init = np.log(np.asarray(cumulative) / (1 - np.asarray(cumulative)))
        raw_thresholds = np.empty(n_classes - 1, dtype=float)
        raw_thresholds[0] = theta_init[0]
        if n_classes > 2:
            diffs = np.maximum(np.diff(theta_init), 0.10)
            raw_thresholds[1:] = np.log(np.expm1(diffs))
        initial = np.concatenate([np.zeros(n_features, dtype=float), raw_thresholds])

        def objective(params: np.ndarray) -> float:
            beta, thresholds = self._unpack(params, n_features, n_classes)
            linear = np.asarray(X @ beta).reshape(-1)
            cdf = expit(thresholds[None, :] - linear[:, None])
            probabilities = np.empty((len(y_array), n_classes), dtype=float)
            probabilities[:, 0] = cdf[:, 0]
            for category in range(1, n_classes - 1):
                probabilities[:, category] = cdf[:, category] - cdf[:, category - 1]
            probabilities[:, -1] = 1 - cdf[:, -1]
            observed = np.clip(probabilities[np.arange(len(y_array)), y_array], 1e-12, 1.0)
            loss = -np.average(np.log(observed), weights=weights)
            regularization = 0.5 * float(self.alpha) * np.sum(beta ** 2) / max(n_features, 1)
            return float(loss + regularization)

        result = minimize(objective, initial, method="L-BFGS-B", options={"maxiter": int(self.max_iter)})
        if not result.success:
            # A estimativa ainda é armazenada se a função reduziu o objetivo, mas deixa
            # explícito no atributo de convergência para inspeção posterior.
            self.converged_ = False
        else:
            self.converged_ = True
        self.optimization_message_ = str(result.message)
        self.n_features_in_ = n_features
        self.params_ = result.x
        self.coef_, self.thresholds_ = self._unpack(result.x, n_features, n_classes)
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        if not hasattr(self, "params_"):
            raise RuntimeError("O modelo precisa ser ajustado antes de predict_proba.")
        linear = np.asarray(X @ self.coef_).reshape(-1)
        cdf = expit(self.thresholds_[None, :] - linear[:, None])
        n = len(linear)
        n_classes = len(self.classes_)
        probabilities = np.empty((n, n_classes), dtype=float)
        probabilities[:, 0] = cdf[:, 0]
        for category in range(1, n_classes - 1):
            probabilities[:, category] = cdf[:, category] - cdf[:, category - 1]
        probabilities[:, -1] = 1 - cdf[:, -1]
        probabilities = np.clip(probabilities, 1e-12, None)
        return probabilities / probabilities.sum(axis=1, keepdims=True)

    def predict(self, X: Any) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)


def infer_feature_types(frame, target_columns: list[str]) -> tuple[list[str], list[str]]:
    """Separa variáveis numéricas e categóricas a partir do DataFrame analítico."""
    features = [column for column in frame.columns if column not in target_columns]
    categorical = [column for column in features if frame[column].dtype == object or str(frame[column].dtype).startswith("category")]
    numeric = [column for column in features if column not in categorical]
    return numeric, categorical


def make_preprocessor(numeric_features: list[str], categorical_features: list[str]) -> ColumnTransformer:
    """Cria transformação que é ajustada somente dentro do treinamento de cada fold."""
    numeric_pipeline = Pipeline(
        steps=[
            # Indicadores de ausência preservam a informação do cenário de
            # sensibilidade sem calcular imputações fora dos folds.
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, numeric_features),
            ("categorical", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )


def build_model_registry(numeric_features: list[str], categorical_features: list[str], random_state: int, n_jobs: int) -> dict[str, tuple[Pipeline, dict[str, list[Any]]]]:
    """Retorna os três modelos treináveis e os espaços de hiperparâmetros internos."""
    preprocessor = make_preprocessor(numeric_features, categorical_features)

    ordinal = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", OrdinalLogitClassifier()),
        ]
    )
    random_forest = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=random_state,
                    n_jobs=n_jobs,
                ),
            ),
        ]
    )

    registry: dict[str, tuple[Pipeline, dict[str, list[Any]]]] = {
        "ordinal_logit": (ordinal, {"model__alpha": [0.5, 1.0]}),
        "random_forest": (
            random_forest,
            {
                "model__max_depth": [None, 12],
                "model__min_samples_leaf": [1, 5],
                "model__max_features": ["sqrt"],
            },
        ),
    }

    # XGBoost é importado dentro da função para manter os scripts de geração/extracão
    # executáveis mesmo quando a dependência de modelagem não estiver instalada.
    try:
        from xgboost import XGBClassifier

        xgb = Pipeline(
            steps=[
                ("preprocessor", make_preprocessor(numeric_features, categorical_features)),
                (
                    "model",
                    XGBClassifier(
                        objective="multi:softprob",
                        num_class=4,
                        eval_metric="mlogloss",
                        random_state=random_state,
                        n_estimators=150,
                        learning_rate=0.05,
                        max_depth=4,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        n_jobs=n_jobs,
                    ),
                ),
            ]
        )
        registry["xgboost"] = (
            xgb,
            {
                "model__max_depth": [3, 5],
                "model__min_child_weight": [1],
                "model__subsample": [0.85],
            },
        )
    except Exception:
        # O script de modelagem registrará a ausência de XGBoost em vez de ocultá-la.
        pass
    return registry

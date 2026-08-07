"""Etapa 8: valida presença, qualificadores, estabilidade e anotação humana."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score, precision_score, recall_score

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.extraction import extraction_reference_table
from emulti_pipeline.markers import MARKER_FEATURE_FIELDS, MARKER_NAMES, marker_column
from emulti_pipeline.utils import effective_seed, read_json, save_csv, setup_logging, stage_dir, write_json

BINARY_FIELDS = ("present", "negated", "remote_present")
CATEGORICAL_FIELDS = ("temporality", "severity", "certainty", "experiencer")


def _numeric(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0).astype(int)


def _safe_kappa(left: pd.Series, right: pd.Series, *, weights: str | None = None) -> float:
    if not len(left) or left.nunique() < 2:
        return float("nan")
    return float(cohen_kappa_score(left, right, weights=weights))


def _evaluate(reference: pd.DataFrame, predicted: pd.DataFrame, extractor: str) -> tuple[pd.DataFrame, dict]:
    merged = reference.merge(predicted, on="patient_id", validate="one_to_one")
    rows: list[dict] = []
    origin_all: list[np.ndarray] = []
    predicted_all: list[np.ndarray] = []
    omissions = hallucinations = positives = negatives = 0
    qualification_errors = qualification_comparisons = 0
    for marker in MARKER_NAMES:
        expressed = (
            _numeric(merged[marker_column("marcadores_origem_", marker, "present")])
            | _numeric(merged[marker_column("marcadores_origem_", marker, "negated")])
            | _numeric(merged[marker_column("marcadores_origem_", marker, "remote_present")])
        ).astype(bool)
        for field in BINARY_FIELDS:
            origin = _numeric(merged[marker_column("marcadores_origem_", marker, field)])
            found = _numeric(merged[marker_column("marcadores_extraidos_", marker, field)])
            rows.append(
                {
                    "extractor": extractor,
                    "marker": marker,
                    "dimension": field,
                    "n": len(origin),
                    "precision": precision_score(origin, found, zero_division=0),
                    "recall": recall_score(origin, found, zero_division=0),
                    "f1": f1_score(origin, found, zero_division=0),
                    "accuracy": accuracy_score(origin, found) if len(origin) else np.nan,
                    "kappa": _safe_kappa(origin, found),
                }
            )
            if field == "present":
                origin_all.append(origin.to_numpy())
                predicted_all.append(found.to_numpy())
                positives += int(origin.sum())
                negatives += int((origin == 0).sum())
                omissions += int(((origin == 1) & (found == 0)).sum())
                hallucinations += int(((origin == 0) & (found == 1)).sum())
        for field in CATEGORICAL_FIELDS:
            origin = merged.loc[expressed, marker_column("marcadores_origem_", marker, field)].fillna("ausente").astype(str)
            found = merged.loc[expressed, marker_column("marcadores_extraidos_", marker, field)].fillna("ausente").astype(str)
            qualification_comparisons += len(origin)
            qualification_errors += int((origin != found).sum())
            rows.append(
                {
                    "extractor": extractor,
                    "marker": marker,
                    "dimension": field,
                    "n": len(origin),
                    "accuracy": accuracy_score(origin, found) if len(origin) else np.nan,
                    "kappa": _safe_kappa(origin, found),
                }
            )
        origin_code = _numeric(merged.loc[expressed, marker_column("marcadores_origem_", marker, "severity_code")])
        found_code = _numeric(merged.loc[expressed, marker_column("marcadores_extraidos_", marker, "severity_code")])
        qualification_comparisons += len(origin_code)
        qualification_errors += int((origin_code != found_code).sum())
        rows.append(
            {
                "extractor": extractor,
                "marker": marker,
                "dimension": "severity_code",
                "n": len(origin_code),
                "accuracy": accuracy_score(origin_code, found_code) if len(origin_code) else np.nan,
                "kappa": _safe_kappa(origin_code, found_code, weights="quadratic"),
                "mae": float(np.mean(np.abs(origin_code - found_code))) if len(origin_code) else np.nan,
            }
        )
    y_true = np.concatenate(origin_all)
    y_pred = np.concatenate(predicted_all)
    present_rows = [row for row in rows if row["dimension"] == "present"]
    status = predicted["extraction_status"] if "extraction_status" in predicted else pd.Series("success", index=predicted.index)
    retries = predicted["retry_count"] if "retry_count" in predicted else pd.Series(0, index=predicted.index)
    return pd.DataFrame(rows), {
        "extractor": extractor,
        "n": int(len(merged)),
        "macro_precision": float(np.mean([row["precision"] for row in present_rows])),
        "macro_recall": float(np.mean([row["recall"] for row in present_rows])),
        "macro_f1": float(np.mean([row["f1"] for row in present_rows])),
        "micro_precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "micro_recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "micro_f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "omission_rate": omissions / positives if positives else 0.0,
        "hallucination_rate": hallucinations / negatives if negatives else 0.0,
        "qualification_error_rate": qualification_errors / qualification_comparisons if qualification_comparisons else 0.0,
        "failed_extractions": int((status == "failed").sum()),
        "invalid_or_failed_extractions": int((status == "failed").sum()),
        "retry_count": int(pd.to_numeric(retries, errors="coerce").fillna(0).sum()),
    }


def _confusion_tables(reference: pd.DataFrame, predicted: pd.DataFrame, extractor: str) -> pd.DataFrame:
    merged = reference.merge(predicted, on="patient_id", validate="one_to_one")
    rows = []
    for marker in MARKER_NAMES:
        expressed = (
            _numeric(merged[marker_column("marcadores_origem_", marker, "present")])
            | _numeric(merged[marker_column("marcadores_origem_", marker, "negated")])
            | _numeric(merged[marker_column("marcadores_origem_", marker, "remote_present")])
        ).astype(bool)
        for field in (*BINARY_FIELDS, *CATEGORICAL_FIELDS, "severity_code"):
            mask = pd.Series(True, index=merged.index) if field in BINARY_FIELDS else expressed
            left = merged.loc[mask, marker_column("marcadores_origem_", marker, field)].fillna("missing").astype(str)
            right = merged.loc[mask, marker_column("marcadores_extraidos_", marker, field)].fillna("missing").astype(str)
            labels = sorted(set(left) | set(right))
            if not labels:
                continue
            matrix = confusion_matrix(left, right, labels=labels)
            for i, reference_label in enumerate(labels):
                for j, predicted_label in enumerate(labels):
                    if matrix[i, j]:
                        rows.append({"extractor": extractor, "marker": marker, "dimension": field, "reference": reference_label, "predicted": predicted_label, "count": int(matrix[i, j])})
    return pd.DataFrame(rows)


def _bootstrap(reference: pd.DataFrame, predicted: pd.DataFrame, extractor: str, repetitions: int, seed: int) -> pd.DataFrame:
    merged = reference.merge(predicted, on="patient_id", validate="one_to_one")
    rng = np.random.default_rng(seed)
    rows = []
    for repetition in range(repetitions):
        sample = merged.iloc[rng.integers(0, len(merged), len(merged))]
        y_true = np.concatenate([_numeric(sample[marker_column("marcadores_origem_", marker, "present")]) for marker in MARKER_NAMES])
        y_pred = np.concatenate([_numeric(sample[marker_column("marcadores_extraidos_", marker, "present")]) for marker in MARKER_NAMES])
        marker_f1 = [
            f1_score(
                _numeric(sample[marker_column("marcadores_origem_", marker, "present")]),
                _numeric(sample[marker_column("marcadores_extraidos_", marker, "present")]),
                zero_division=0,
            )
            for marker in MARKER_NAMES
        ]
        rows.append({"extractor": extractor, "repetition": repetition, "macro_f1": np.mean(marker_f1), "micro_f1": f1_score(y_true, y_pred, zero_division=0)})
    return pd.DataFrame(rows)


def _bootstrap_ci(samples: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (extractor, metric), values in samples.melt(id_vars=["extractor", "repetition"], var_name="metric", value_name="value").groupby(["extractor", "metric"]):
        rows.append({"extractor": extractor, "metric": metric, "mean": values["value"].mean(), "ci_2_5": values["value"].quantile(0.025), "ci_97_5": values["value"].quantile(0.975)})
    return pd.DataFrame(rows)


def _stability(input_dir: Path, files: list[str]) -> pd.DataFrame:
    rows = []
    for left_name, right_name in combinations(files, 2):
        left = pd.read_csv(input_dir / left_name)
        right = pd.read_csv(input_dir / right_name)
        merged = left.merge(right, on="patient_id", suffixes=("_a", "_b"), validate="one_to_one")
        for marker in MARKER_NAMES:
            for field in MARKER_FEATURE_FIELDS:
                column = marker_column("marcadores_extraidos_", marker, field)
                rows.append({"run_a": left_name, "run_b": right_name, "marker": marker, "dimension": field, "n": len(merged), "agreement": (merged[f"{column}_a"].fillna("missing") == merged[f"{column}_b"].fillna("missing")).mean()})
    return pd.DataFrame(rows, columns=["run_a", "run_b", "marker", "dimension", "n", "agreement"])


def _human_agreement(path_a: str | None, path_b: str | None) -> tuple[pd.DataFrame, dict]:
    if not path_a or not path_b:
        return pd.DataFrame([{"status": "pending", "reason": "Provide --annotator-a and --annotator-b."}]), {"available": False}
    left = pd.read_csv(path_a)
    right = pd.read_csv(path_b)
    merged = left.merge(right, on="patient_id", suffixes=("_a", "_b"), validate="one_to_one")
    rows = []
    for marker in MARKER_NAMES:
        for field in MARKER_FEATURE_FIELDS:
            column = f"{marker}_{field}"
            valid = merged[f"{column}_a"].notna() & merged[f"{column}_b"].notna()
            a = merged.loc[valid, f"{column}_a"].astype(str)
            b = merged.loc[valid, f"{column}_b"].astype(str)
            rows.append({"marker": marker, "dimension": field, "n": int(valid.sum()), "agreement": float((a == b).mean()) if valid.any() else np.nan, "kappa": _safe_kappa(a, b)})
    return pd.DataFrame(rows), {"available": True, "n_joined": int(len(merged))}


def main() -> None:
    parser = common_parser("Valida extração contra referência qualificada e anotações humanas.")
    parser.add_argument("--annotator-a", default=None)
    parser.add_argument("--annotator-b", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("08_validate_extraction")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    extraction_dir = stage_dir(config, args.run_id, "06_extraction")
    reference = extraction_reference_table(profiles)
    manifest = read_json(extraction_dir / "extraction_manifest.json")
    sources = [("primary", "marcadores_extraidos.csv")]
    if manifest.get("rule_baseline_file"):
        sources.append(("rule_baseline", str(manifest["rule_baseline_file"])))

    metrics_parts = []
    bootstrap_parts = []
    confusion_parts = []
    summaries = []
    repetitions = int(config["extraction"].get("bootstrap_repetitions", 200))
    for extractor, filename in sources:
        predicted = pd.read_csv(extraction_dir / filename)
        metrics, summary = _evaluate(reference, predicted, extractor)
        metrics_parts.append(metrics)
        confusion_parts.append(_confusion_tables(reference, predicted, extractor))
        summaries.append(summary)
        bootstrap_parts.append(_bootstrap(reference, predicted, extractor, repetitions, effective_seed(config) + 6000))

    output = stage_dir(config, args.run_id, "08_extraction_validation")
    metrics_frame = pd.concat(metrics_parts, ignore_index=True)
    bootstrap_frame = pd.concat(bootstrap_parts, ignore_index=True)
    save_csv(metrics_frame, output / "metrics_by_marker_and_dimension.csv")
    save_csv(pd.concat(confusion_parts, ignore_index=True), output / "confusion_matrices_long.csv")
    save_csv(bootstrap_frame, output / "bootstrap_samples.csv")
    save_csv(_bootstrap_ci(bootstrap_frame), output / "bootstrap_confidence_intervals.csv")
    save_csv(_stability(extraction_dir, list(manifest.get("stability_files", []))), output / "stability_agreement.csv")
    human_frame, human_summary = _human_agreement(args.annotator_a, args.annotator_b)
    save_csv(human_frame, output / "inter_annotator_agreement.csv")
    write_json(output / "validation_summary.json", {"extractors": summaries, "bootstrap_repetitions": repetitions, "human_annotation": human_summary, "interpretation": "A referência sintética mede preservação controlada; validação humana independente permanece necessária para validade externa."})
    logger.info("Validação concluída para %d extrator(es)", len(sources))


if __name__ == "__main__":
    main()

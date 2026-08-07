"""Etapa 7: prepara amostra estratificada para anotação humana independente e cega."""

from __future__ import annotations

import json

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.markers import MARKER_ALL_FIELDS, MARKER_NAMES
from emulti_pipeline.utils import effective_seed, save_csv, setup_logging, stage_dir, write_json


def _load_jsonl(path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as handle:
        return pd.DataFrame(json.loads(line) for line in handle if line.strip())


def main() -> None:
    parser = common_parser("Cria formulário cego de anotação estratificado pela referência simulada.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("07_create_annotation_sample")
    narratives = _load_jsonl(stage_dir(config, args.run_id, "04_narratives") / "narratives.jsonl")
    priority = pd.read_csv(stage_dir(config, args.run_id, "05_priority") / "prioridade_referencia.csv")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    merged = narratives.merge(priority[["patient_id", "prioridade_referencia"]], on="patient_id", validate="one_to_one")

    critical_columns = [
        "marcadores_origem_ideacao_suicida_present",
        "marcadores_origem_planejamento_suicida_present",
        "marcadores_origem_autoagressao_iminente_present",
        "marcadores_origem_risco_violencia_present",
        "marcadores_origem_sintomas_psicoticos_present",
    ]
    audit_source = profiles[["patient_id", *critical_columns]].copy()
    audit_source["critical_case"] = audit_source[critical_columns].max(axis=1).astype(int)
    merged = merged.merge(audit_source[["patient_id", "critical_case"]], on="patient_id", validate="one_to_one")

    n_per_priority = int(config["annotation"]["n_per_priority"])
    seed = effective_seed(config) + 5000
    selected: list[pd.DataFrame] = []
    for label in ["baixa", "moderada", "alta", "urgente"]:
        subset = merged[merged["prioridade_referencia"] == label]
        selected.append(subset.sample(n=min(n_per_priority, len(subset)), random_state=seed))
    sample = pd.concat(selected, ignore_index=True).drop_duplicates("patient_id")

    if bool(config["annotation"].get("include_critical_cases", True)) and not sample["critical_case"].any():
        candidates = merged[(merged["critical_case"] == 1) & ~merged["patient_id"].isin(sample["patient_id"])]
        if len(candidates):
            sample = pd.concat([sample, candidates.sample(n=1, random_state=seed)], ignore_index=True)
    sample = sample.sample(frac=1, random_state=seed).reset_index(drop=True)

    # O formulário não contém prioridade, marcadores de origem ou outros dados estruturados.
    annotation = sample[["patient_id", "narrativa_clinica"]].copy()
    for marker in MARKER_NAMES:
        for field in MARKER_ALL_FIELDS:
            annotation[f"{marker}_{field}"] = ""
    annotation["annotator_id"] = ""
    annotation["notes"] = ""

    output = stage_dir(config, args.run_id, "07_annotation")
    save_csv(annotation, output / "annotation_template.csv")
    save_csv(
        sample[["patient_id", "prioridade_referencia", "critical_case"]],
        output / "annotation_sampling_audit.csv",
    )
    write_json(
        output / "annotation_instructions.json",
        {
            "instructions": (
                "Dois anotadores devem preencher cópias separadas, de forma independente, sem acesso à "
                "prioridade ou aos marcadores de origem. Divergências devem ser adjudicadas por um terceiro "
                "revisor. present representa achado atual afirmado; remote_present registra antecedente."
            ),
            "fields": list(MARKER_ALL_FIELDS),
            "n_selected": int(len(annotation)),
            "n_critical_cases": int(sample["critical_case"].sum()),
            "blinded": True,
        },
    )
    logger.info("Amostra cega criada com %d narrativas", len(annotation))


if __name__ == "__main__":
    main()

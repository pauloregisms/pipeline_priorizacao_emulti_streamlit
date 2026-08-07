"""Etapa 9: constrói os três conjuntos analíticos do experimento."""

from __future__ import annotations

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.features import build_analytical_sets
from emulti_pipeline.utils import save_csv, setup_logging, stage_dir, write_json


def main() -> None:
    parser = common_parser("Prepara conjuntos dados_estruturados + indicadores_psicometricos, dados_estruturados + indicadores_psicometricos + marcadores_origem e dados_estruturados + indicadores_psicometricos + marcadores_extraidos.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("09_build_analytical_datasets")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    psychometrics = pd.read_csv(stage_dir(config, args.run_id, "02_psychometrics") / "psychometrics.csv")
    priority = pd.read_csv(stage_dir(config, args.run_id, "05_priority") / "prioridade_referencia.csv")
    extracted = pd.read_csv(stage_dir(config, args.run_id, "06_extraction") / "marcadores_extraidos.csv")

    datasets = build_analytical_sets(profiles, psychometrics, priority, extracted, config)
    output = stage_dir(config, args.run_id, "09_analytical_sets")
    manifest = {}
    for name, frame in datasets.items():
        save_csv(frame, output / f"{name}.csv")
        manifest[name] = {"n_rows": int(len(frame)), "n_columns": int(frame.shape[1]), "path": f"{name}.csv"}
    write_json(output / "datasets_manifest.json", manifest)
    logger.info("Foram criados %d conjuntos analíticos", len(datasets))


if __name__ == "__main__":
    main()

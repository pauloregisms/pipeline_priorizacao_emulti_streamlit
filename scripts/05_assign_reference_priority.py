"""Etapa 5: produz a prioridade de referência simulada prioridade_referencia a partir de dados estruturados, indicadores psicométricos e marcadores de origem."""

from __future__ import annotations

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.priority import assign_reference_priority
from emulti_pipeline.utils import effective_seed, save_csv, setup_logging, stage_dir, write_json


def main() -> None:
    parser = common_parser("Aplica a matriz protocolada de prioridade de referência simulada.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("05_assign_reference_priority")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    psychometrics = pd.read_csv(stage_dir(config, args.run_id, "02_psychometrics") / "psychometrics.csv")

    # Esta etapa é independente da narrativa. Portanto, prioridade_referencia nunca retroalimenta a
    # produção de texto e não pode ser considerado como pista lexical para o extrator.
    priority = assign_reference_priority(profiles, psychometrics, config, effective_seed(config))
    output = stage_dir(config, args.run_id, "05_priority")
    save_csv(priority, output / "prioridade_referencia.csv")
    write_json(output / "priority_metadata.json", {
        "priority_order": ["baixa", "moderada", "alta", "urgente"],
        "interpretation": "prioridade de referência simulada; não é prioridade clínica real",
        "rule_version": config["priority_rules"]["version"],
        "validation_status": config["priority_rules"]["validation_status"],
        "rule_parameters": config["priority_rules"],
        "seed": effective_seed(config) + 3000,
        "class_distribution": priority["prioridade_referencia"].value_counts().sort_index().to_dict(),
    })
    logger.info("Distribuição de prioridade_referencia: %s", priority["prioridade_referencia"].value_counts().to_dict())


if __name__ == "__main__":
    main()

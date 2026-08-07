"""Etapa 2: gera itens e escores de PHQ-9, GAD-7 e IDATE-Estado."""

from __future__ import annotations

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.simulation import simulate_psychometrics
from emulti_pipeline.utils import effective_seed, save_csv, setup_logging, stage_dir, write_json


def main() -> None:
    parser = common_parser("Simula instrumentos psicométricos item a item.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("02_simulate_psychometrics")
    profiles_path = stage_dir(config, args.run_id, "01_profiles") / "profiles.csv"
    if not profiles_path.exists():
        raise FileNotFoundError("Execute 01_generate_profiles.py antes desta etapa.")
    profiles = pd.read_csv(profiles_path)

    # Os totais são calculados apenas depois dos itens, conforme definido na metodologia.
    result = simulate_psychometrics(profiles, config, effective_seed(config))
    output = stage_dir(config, args.run_id, "02_psychometrics")
    save_csv(result.data, output / "psychometrics.csv")
    write_json(output / "psychometrics_metadata.json", result.metadata)
    logger.info("Itens e escores gerados para %d perfis", len(result.data))


if __name__ == "__main__":
    main()

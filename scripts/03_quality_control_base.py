"""Etapa 3: verifica plausibilidade e consistência antes de gerar textos."""

from __future__ import annotations

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.quality import validate_profile_ranges, validate_psychometrics
from emulti_pipeline.utils import save_csv, setup_logging, stage_dir, write_json


def main() -> None:
    parser = common_parser("Executa controle de qualidade da base estrutural e psicométrica.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("03_quality_control_base")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    psychometrics = pd.read_csv(stage_dir(config, args.run_id, "02_psychometrics") / "psychometrics.csv")

    profile_checks, profile_summary = validate_profile_ranges(profiles, config)
    scale_checks, scale_summary = validate_psychometrics(psychometrics)
    output = stage_dir(config, args.run_id, "03_quality_control")
    save_csv(profile_checks, output / "profile_checks.csv")
    save_csv(scale_checks, output / "psychometric_checks.csv")
    write_json(output / "quality_summary.json", {"profiles": profile_summary, "psychometrics": scale_summary})

    failures = int((~profile_checks["passed"]).sum() + (~scale_checks["passed"]).sum())
    if failures:
        raise RuntimeError(f"Controle de qualidade encontrou {failures} falhas. Corrija antes de continuar.")
    logger.info("Controle de qualidade concluído sem falhas.")


if __name__ == "__main__":
    main()

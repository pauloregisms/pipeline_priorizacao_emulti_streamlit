"""Etapa 12: executa cenários pré-especificados de robustez.

Cada cenário altera somente parâmetros explícitos do YAML, executa uma nova réplica e
consolida o resumo de desempenho. Esta etapa deve ser executada depois de validar o
cenário-base, pois pode ser computacionalmente custosa.
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from _bootstrap import PROJECT_ROOT, common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.utils import save_csv, setup_logging, stage_dir, write_json


def _deep_update(target: dict, override: dict) -> dict:
    """Aplica overrides aninhados sem descartar parâmetros não alterados."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


def main() -> None:
    parser = common_parser("Executa os cenários de sensibilidade configurados.")
    parser.add_argument("--skip-modeling", action="store_true", help="Executa apenas geração/extracão para depuração rápida.")
    args = parser.parse_args()
    base_config = load_config(args.config)
    logger = setup_logging("12_run_sensitivity")
    scenarios = base_config.get("sensitivity", {}).get("scenarios", [])
    if not scenarios:
        raise ValueError("Nenhum cenário configurado em sensitivity.scenarios.")

    output = stage_dir(base_config, args.run_id, "12_sensitivity")
    temporary_dir = output / "temporary_configs"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for scenario in scenarios:
        config = copy.deepcopy(base_config)
        _deep_update(config, dict(scenario.get("overrides", {})))
        config["project"]["run_description"] = f"Sensibilidade: {scenario['name']}"
        config_path = temporary_dir / f"{scenario['name']}.yaml"
        with config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, allow_unicode=True, sort_keys=False)

        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_pipeline.py"),
            "--config", str(config_path),
            "--run-id", f"{args.run_id}__{scenario['name']}",
            "--skip-explanations",
            "--skip-report",
        ]
        if args.skip_modeling:
            command.append("--stop-after")
            command.append("09_build_analytical_datasets.py")
        logger.info("Executando cenário de sensibilidade: %s", scenario["name"])
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)

        scenario_run_id = f"{args.run_id}__{scenario['name']}"
        summary_path = stage_dir(config, scenario_run_id, "10_modeling") / "modeling_summary.csv"
        if summary_path.exists():
            frame = pd.read_csv(summary_path)
            frame.insert(0, "scenario", scenario["name"])
            rows.append(frame)

    if rows:
        combined = pd.concat(rows, ignore_index=True)
        save_csv(combined, output / "sensitivity_modeling_summary.csv")
    write_json(
        output / "sensitivity_manifest.json",
        {
            "scenarios": scenarios,
            "n_completed_with_modeling": len(rows),
            "dimensions_varied": [
                "random_seed",
                "extraction_error",
                "missingness",
                "narrative_omission",
                "priority_thresholds",
            ],
        },
    )
    logger.info("Sensibilidade concluída. Cenários com modelagem: %d", len(rows))


if __name__ == "__main__":
    main()

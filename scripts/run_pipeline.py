"""Orquestrador para executar o fluxo metodológico completo em ordem rastreável."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import PROJECT_ROOT


STAGES = [
    "00_prepare_workspace.py",
    "01_generate_profiles.py",
    "02_simulate_psychometrics.py",
    "03_quality_control_base.py",
    "04_generate_narratives.py",
    "05_assign_reference_priority.py",
    "06_extract_markers.py",
    "07_create_annotation_sample.py",
    "08_validate_extraction.py",
    "09_build_analytical_datasets.py",
    "10_train_evaluate_models.py",
    "14_export_priority_table.py",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o pipeline de simulação e-Multi por etapas.")
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--run-id", default="baseline")
    parser.add_argument("--skip-explanations", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--models", default="all", help="Modelos encaminhados à etapa 10.")
    parser.add_argument("--stop-after", default=None, help="Nome do script após o qual a execução deve parar.")
    args = parser.parse_args()

    for stage in STAGES:
        command = [sys.executable, str(PROJECT_ROOT / "scripts" / stage), "--config", args.config, "--run-id", args.run_id]
        if stage == "10_train_evaluate_models.py":
            command.extend(["--models", args.models])
        print(f"\n=== Executando {stage} ===", flush=True)
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)
        if args.stop_after == stage:
            return

    if not args.skip_explanations:
        stage = "11_explain_models.py"
        print(f"\n=== Executando {stage} ===", flush=True)
        subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / stage), "--config", args.config, "--run-id", args.run_id], check=True, cwd=PROJECT_ROOT)
    if not args.skip_report:
        stage = "13_generate_report.py"
        print(f"\n=== Executando {stage} ===", flush=True)
        subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / stage), "--config", args.config, "--run-id", args.run_id], check=True, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    main()

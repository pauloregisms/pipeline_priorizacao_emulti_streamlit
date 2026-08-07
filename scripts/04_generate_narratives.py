"""Etapa 4: gera narrativas SOAP por provedor configurável e desacoplado."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.markers import markers_from_row
from emulti_pipeline.narratives import NarrativeRequest, create_narrative_generator
from emulti_pipeline.utils import effective_seed, setup_logging, stage_dir, write_json


def _record_to_request(profile: pd.Series, scales: pd.Series, prompt_version: str) -> NarrativeRequest:
    """Monta a entrada explicitamente permitida para o gerador textual.

    A função seleciona somente dados estruturados, indicadores psicométricos e
    marcadores de origem. Ela não importa arquivos da etapa de prioridade e não aceita
    ``prioridade_referencia`` como campo de entrada.
    """
    structured_columns = [
        "age_years", "gender_category", "education", "income_brl", "food_insecurity",
        "poor_housing", "social_vulnerability", "mental_health_history", "chronic_condition",
        "recent_service_contact",
    ]
    dados_estruturados = {column: profile[column] for column in structured_columns}
    indicadores_psicometricos = {
        "phq9_total": int(scales["phq9_total"]),
        "gad7_total": int(scales["gad7_total"]),
        "idate_estado_total": int(scales["idate_estado_total"]),
    }
    marcadores_origem = markers_from_row(profile, "marcadores_origem_")
    return NarrativeRequest(
        patient_id=str(profile["patient_id"]),
        seed=int(profile["seed"]) + 2000,
        dados_estruturados=dados_estruturados,
        indicadores_psicometricos=indicadores_psicometricos,
        marcadores_origem=marcadores_origem,
        prompt_version=prompt_version,
    )


def main() -> None:
    parser = common_parser("Gera narrativas clínicas sintéticas sem vazamento de rótulo.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("04_generate_narratives")
    profiles = pd.read_csv(stage_dir(config, args.run_id, "01_profiles") / "profiles.csv")
    psychometrics = pd.read_csv(stage_dir(config, args.run_id, "02_psychometrics") / "psychometrics.csv")
    merged = profiles.merge(psychometrics, on="patient_id", how="inner", validate="one_to_one")

    # Invariante explícita: esta etapa ocorre antes da criação de prioridade_referencia
    # e não pode receber nenhuma coluna que represente prioridade.
    if any("priority" in column.lower() or "prioridade" in column.lower() for column in merged.columns):
        raise ValueError("Foram detectadas colunas de prioridade na entrada da geração textual.")

    narrative_config = dict(config["narrative"])
    narrative_config["omission_rate"] = float(config["simulation"].get("narrative_omission_rate", 0.0))
    generator = create_narrative_generator(narrative_config)
    output = stage_dir(config, args.run_id, "04_narratives")
    output_file = output / "narratives.jsonl"
    rows = []
    with output_file.open("w", encoding="utf-8") as handle:
        for _, record in merged.iterrows():
            request = _record_to_request(record, record, config["narrative"]["prompt_version"])
            response = generator.generate(request)
            row = response.to_dict()
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)

    # CSV compacto facilita inspeção humana; JSONL preserva a resposta completa e os metadados.
    pd.DataFrame(rows).drop(columns=["generation_metadata"], errors="ignore").to_csv(
        output / "narratives_index.csv", index=False, encoding="utf-8"
    )

    api_called = any(bool(row["generation_metadata"].get("api_called")) for row in rows)
    provider = str(config["narrative"].get("provider", "template"))
    manifest = {
        "provider": provider,
        "generator_id": getattr(generator, "generator_id", config["narrative"].get("generator_id")),
        "prompt_version": config["narrative"]["prompt_version"],
        "narratives": len(rows),
        "api_called": api_called,
        "forbidden_input_keys": sorted(getattr(generator, "forbidden_input_keys", config["narrative"]["forbidden_input_keys"])),
        "seed_base": effective_seed(config),
    }
    if provider.lower() == "gemini":
        gemini_config = config["narrative"].get("gemini", {})
        manifest["model_id"] = gemini_config.get("model_id")
        manifest["api_key_env"] = gemini_config.get("api_key_env")
        manifest["temperature"] = gemini_config.get("temperature")
        manifest["max_output_tokens"] = gemini_config.get("max_output_tokens")
    write_json(output / "narrative_generation_manifest.json", manifest)
    logger.info(
        "Foram geradas %d narrativas sintéticas com provedor %s em %s",
        len(rows),
        provider,
        output_file,
    )


if __name__ == "__main__":
    main()

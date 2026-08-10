"""Etapa 6: extrai marcadores por provedor configurado e linha de base por regras."""

from __future__ import annotations

import json

import pandas as pd

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.extraction import RuleBasedClinicalExtractor, create_clinical_extractor
from emulti_pipeline.utils import effective_seed, save_csv, setup_logging, stage_dir, write_json


def _load_jsonl(path) -> pd.DataFrame:
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return pd.DataFrame(records)


def _write_jsonl(path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def main() -> None:
    parser = common_parser("Extrai marcadores sem acesso à origem ou à prioridade simulada.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("06_extract_markers")
    narratives = _load_jsonl(stage_dir(config, args.run_id, "04_narratives") / "narratives.jsonl")
    allowed = narratives[["patient_id", "narrativa_clinica"]].copy()
    seed = effective_seed(config) + 4000

    extraction_config = dict(config["extraction"])
    extraction_config["flip_rate"] = float(config["simulation"].get("extraction_flip_rate", 0.0))
    extractor = create_clinical_extractor(extraction_config, seed=seed)
    extracted = extractor.extract(allowed)
    output = stage_dir(config, args.run_id, "06_extraction")
    save_csv(extracted, output / "marcadores_extraidos.csv")

    audit_records = list(getattr(extractor, "audit_records", []))
    if audit_records:
        _write_jsonl(output / "extraction_audit.jsonl", audit_records)

    provider = str(extraction_config.get("provider", "rules")).lower()
    rule_file = None
    if provider != "rules":
        rule_extractor = RuleBasedClinicalExtractor(
            ontology_version=str(extraction_config["ontology_version"]),
            extractor_id="rule-dictionary-qualified-v2",
            flip_rate=0.0,
            seed=seed,
        )
        save_csv(rule_extractor.extract(allowed), output / "marcadores_extraidos_regra.csv")
        rule_file = "marcadores_extraidos_regra.csv"

    stability_cfg = extraction_config.get("stability", {})
    stability_files: list[str] = []
    if provider == "llm" and bool(stability_cfg.get("enabled", False)):
        n_records = min(int(stability_cfg.get("n_records", 50)), len(allowed))
        repetitions = int(stability_cfg.get("repetitions", 3))
        sample = allowed.sample(n=n_records, random_state=seed).sort_values("patient_id")
        for repetition in range(1, repetitions + 1):
            result = extractor.extract(sample, seed_offset=repetition * 100_000)
            filename = f"stability_run_{repetition}.csv"
            save_csv(result, output / filename)
            stability_files.append(filename)

    failure_count = int((extracted.get("extraction_status", "success") == "failed").sum())
    retry_count = int(pd.to_numeric(extracted.get("retry_count", 0), errors="coerce").fillna(0).sum())
    write_json(
        output / "extraction_manifest.json",
        {
            "provider": provider,
            "extractor_id": getattr(extractor, "extractor_id", extraction_config.get("extractor_id")),
            "ontology_version": getattr(extractor, "ontology_version", extraction_config.get("ontology_version")),
            "backend": getattr(extractor, "backend", None),
            "model_id": getattr(extractor, "model_id", None),
            "n_narratives": int(len(extracted)),
            "failure_count": failure_count,
            "retry_count": retry_count,
            "rule_baseline_file": rule_file,
            "stability_files": stability_files,
            "input_contract": ["patient_id", "narrativa_clinica"],
            "forbidden_inputs": ["dados_estruturados", "indicadores_psicometricos", "marcadores_origem", "prioridade_referencia"],
            "note": "A extração recebe somente a narrativa sintética; a regra independente é preservada como comparador.",
        },
    )
    logger.info("Marcadores extraídos para %d narrativas com provedor %s", len(extracted), provider)


if __name__ == "__main__":
    main()

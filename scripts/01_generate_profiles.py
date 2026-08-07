"""Etapa 1: gera dados estruturados, vulnerabilidade social, gravidade latente e marcadores de origem do modelo estrutural sintético."""

from __future__ import annotations

from _bootstrap import common_parser
from emulti_pipeline.config import load_config
from emulti_pipeline.simulation import generate_profiles
from emulti_pipeline.utils import effective_seed, save_csv, setup_logging, stage_dir, write_json


def main() -> None:
    parser = common_parser("Gera perfis estruturados e marcadores clínicos verdadeiros.")
    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logging("01_generate_profiles")
    seed = effective_seed(config)

    # A saída contém gravidade_latente_auditoria apenas para auditoria do gerador. Scripts de modelagem removem
    # explicitamente esta variável para impedir vazamento de informação latente.
    result = generate_profiles(config, seed)
    output = stage_dir(config, args.run_id, "01_profiles")
    save_csv(result.data, output / "profiles.csv")
    write_json(output / "generation_metadata.json", result.metadata)
    logger.info("Foram gerados %d perfis sintéticos com seed=%d", len(result.data), seed)


if __name__ == "__main__":
    main()

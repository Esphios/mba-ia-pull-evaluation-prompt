from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .utils import DATASET_PATH
except ImportError:
    from utils import DATASET_PATH


def load_dataset_rows(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de dataset não encontrado: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido na linha {line_number} de {path}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Era esperado um objeto na linha {line_number} de {path}")
            rows.append(row)

    return rows


def build_evaluation_examples(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row in load_dataset_rows(path):
        examples.append(
            {
                "inputs": row["inputs"],
                "outputs": row["outputs"],
                "metadata": row.get("metadata", {}),
            }
        )
    return examples


def build_langsmith_examples(
    path: Path = DATASET_PATH,
    *,
    minimum_examples: int = 20,
) -> list[dict[str, Any]]:
    """Expande o dataset remoto de forma determinística sem alterar o JSONL fonte."""

    base_examples = build_evaluation_examples(path)
    if len(base_examples) >= minimum_examples:
        return base_examples

    expanded_examples: list[dict[str, Any]] = []
    replica_count_by_source: dict[int, int] = {}

    def clone_example(source_index: int) -> dict[str, Any]:
        replica_count_by_source[source_index] = replica_count_by_source.get(source_index, 0) + 1
        source_example = base_examples[source_index]
        metadata = dict(source_example.get("metadata", {}))
        metadata.update(
            {
                "source_row_index": source_index + 1,
                "replica_index": replica_count_by_source[source_index],
                "dataset_variant": "langsmith_evidence",
            }
        )
        return {
            "inputs": dict(source_example["inputs"]),
            "outputs": dict(source_example["outputs"]),
            "metadata": metadata,
        }

    for source_index in range(len(base_examples)):
        expanded_examples.append(clone_example(source_index))

    next_source_index = 0
    while len(expanded_examples) < minimum_examples:
        expanded_examples.append(clone_example(next_source_index))
        next_source_index = (next_source_index + 1) % len(base_examples)

    return expanded_examples

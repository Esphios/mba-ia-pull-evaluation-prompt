from __future__ import annotations

from pathlib import Path
import unicodedata

import yaml

try:
    from src.dataset import load_dataset_rows
except ImportError:
    from dataset import load_dataset_rows

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "bug_to_user_story_v2.yml"


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def load_prompt() -> dict:
    assert PROMPT_PATH.exists(), f"Arquivo de prompt não encontrado: {PROMPT_PATH}"
    with PROMPT_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_prompt_has_system_prompt():
    data = load_prompt()
    assert "system_prompt" in data
    assert str(data["system_prompt"]).strip()


def test_prompt_has_role_definition():
    data = load_prompt()
    text = normalize(str(data.get("system_prompt", "")))
    assert "voce e" in text or "you are" in text


def test_prompt_mentions_format():
    data = load_prompt()
    combined = normalize(
        f"{data.get('system_prompt', '')}\n{data.get('user_prompt', '')}"
    )
    assert "markdown" in combined or "user story" in combined


def test_prompt_has_few_shot_examples():
    data = load_prompt()
    examples = data.get("few_shot_examples", [])
    assert isinstance(examples, list)
    assert len(examples) >= 2
    for example in examples:
        assert str(example.get("input", "")).strip()
        assert str(example.get("output", "")).strip()


def test_prompt_no_todos():
    data = load_prompt()
    serialized = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    assert "TODO" not in serialized
    assert "[TODO]" not in serialized


def test_minimum_techniques():
    data = load_prompt()
    techniques = data.get("metadata", {}).get("techniques", [])
    assert isinstance(techniques, list)
    assert len(techniques) >= 2


def test_prompt_has_required_metadata_fields():
    data = load_prompt()
    metadata = data.get("metadata", {})
    for field in ("version", "techniques", "author", "target_format", "status"):
        assert field in metadata
        assert metadata[field]


def test_few_shot_examples_do_not_reuse_dataset_reports():
    data = load_prompt()
    dataset_reports = {
        normalize(str(row.get("inputs", {}).get("bug_report", "")))
        for row in load_dataset_rows()
    }

    for example in data.get("few_shot_examples", []):
        normalized_input = normalize(str(example.get("input", "")))
        assert normalized_input not in dataset_reports
        assert all(
            report not in normalized_input and normalized_input not in report
            for report in dataset_reports
        )

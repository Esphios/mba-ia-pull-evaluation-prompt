from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
DATASET_PATH = ROOT_DIR / "datasets" / "bug_to_user_story.jsonl"
PROMPT_V1_PATH = PROMPTS_DIR / "bug_to_user_story_v1.yml"
PROMPT_V2_PATH = PROMPTS_DIR / "bug_to_user_story_v2.yml"
RAW_PROMPTS_PATH = PROMPTS_DIR / "raw_prompts.yml"
DEFAULT_DATASET_NAME = "bug_to_user_story_eval"


@dataclass(frozen=True)
class Settings:
    provider: str
    openai_model: str
    openai_eval_model: str
    google_model: str
    google_eval_model: str
    langsmith_prompt_source: str
    langsmith_prompt_target: str
    langsmith_dataset_name: str
    langsmith_project: str
    langsmith_upload_results: bool


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def canonical_dataset_name(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate or candidate.lower() == "default":
        return DEFAULT_DATASET_NAME
    return candidate


def load_settings() -> Settings:
    load_dotenv()

    provider = _env("PROVIDER", "LLM_PROVIDER", default="openai").strip().lower()
    if provider == "gemini":
        provider = "google"

    return Settings(
        provider=provider,
        openai_model=_env("OPENAI_MODEL", "LLM_MODEL", default="gpt-4o-mini"),
        openai_eval_model=_env("OPENAI_EVAL_MODEL", "EVAL_MODEL", default="gpt-4o"),
        google_model=_env("GOOGLE_MODEL", "LLM_MODEL", default="gemini-2.5-flash"),
        google_eval_model=_env("GOOGLE_EVAL_MODEL", "EVAL_MODEL", default="gemini-2.5-flash"),
        langsmith_prompt_source=_env(
            "LANGSMITH_PROMPT_SOURCE",
            default="leonanluppi/bug_to_user_story_v1",
        ),
        langsmith_prompt_target=_env("LANGSMITH_PROMPT_TARGET"),
        langsmith_dataset_name=canonical_dataset_name(
            _env("LANGSMITH_DATASET_NAME", default=DEFAULT_DATASET_NAME)
        ),
        langsmith_project=_env(
            "LANGSMITH_PROJECT",
            "LANGCHAIN_PROJECT",
            default="bug-to-user-story",
        ),
        langsmith_upload_results=parse_bool(
            _env("LANGSMITH_UPLOAD_RESULTS", default="true"),
            default=True,
        ),
    )


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Era esperado um objeto YAML do tipo mapa em {path}, mas foi encontrado {type(data).__name__}."
        )
    return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def load_prompt_document(path: Path = PROMPT_V2_PATH) -> dict[str, Any]:
    return read_yaml(path)


def validate_prompt_document(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_fields = (
        "name",
        "description",
        "metadata",
        "system_prompt",
        "few_shot_examples",
        "user_prompt",
    )
    for field in required_fields:
        if field not in document:
            errors.append(f"Campo obrigatório ausente: {field}")

    system_prompt = str(document.get("system_prompt", "")).strip()
    user_prompt = str(document.get("user_prompt", "")).strip()
    if not system_prompt:
        errors.append("system_prompt está vazio.")
    if not user_prompt:
        errors.append("user_prompt está vazio.")

    few_shot_examples = document.get("few_shot_examples", [])
    if not isinstance(few_shot_examples, list) or len(few_shot_examples) < 2:
        errors.append("few_shot_examples deve conter pelo menos 2 exemplos.")

    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata deve ser um objeto YAML.")
        metadata = {}

    required_metadata_fields = (
        "version",
        "techniques",
        "author",
        "target_format",
        "status",
    )
    for field in required_metadata_fields:
        value = metadata.get(field)
        if value in (None, "", []):
            errors.append(f"metadata.{field} estÃ¡ ausente ou vazio.")

    techniques = metadata.get("techniques", []) if isinstance(metadata, dict) else []
    if not isinstance(techniques, list) or len(techniques) < 2:
        errors.append("metadata.techniques deve conter pelo menos 2 itens.")

    serialized = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    if "TODO" in serialized:
        errors.append("O documento do prompt ainda contém marcadores TODO.")

    return errors


def build_chat_prompt_from_document(document: dict[str, Any]) -> ChatPromptTemplate:
    messages: list[tuple[str, str]] = [("system", str(document["system_prompt"]).strip())]

    for example in document.get("few_shot_examples", []):
        example_input = str(example.get("input", "")).strip()
        example_output = str(example.get("output", "")).strip()
        if example_input and example_output:
            messages.append(("human", example_input))
            messages.append(("ai", example_output))

    messages.append(("human", str(document["user_prompt"]).strip()))
    return ChatPromptTemplate.from_messages(messages)


def role_from_message_template(message: Any) -> str:
    class_name = type(message).__name__.lower()
    if "system" in class_name:
        return "system"
    if "ai" in class_name:
        return "ai"
    return "human"


def extract_prompt_messages(prompt: ChatPromptTemplate) -> list[dict[str, str]]:
    extracted: list[dict[str, str]] = []
    for message in prompt.messages:
        template = getattr(getattr(message, "prompt", None), "template", None)
        if template is None:
            template = str(message)
        extracted.append(
            {
                "role": role_from_message_template(message),
                "template": str(template).strip(),
            }
        )
    return extracted


def build_generation_model(settings: Settings, *, eval_mode: bool = False):
    if settings.provider == "openai":
        from langchain_openai import ChatOpenAI

        api_key = _env("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY não está configurada.")

        model_name = settings.openai_eval_model if eval_mode else settings.openai_model
        return ChatOpenAI(model=model_name, temperature=0, api_key=api_key)

    if settings.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = _env("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY não está configurada.")

        model_name = settings.google_eval_model if eval_mode else settings.google_model
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key,
        )

    raise RuntimeError("PROVIDER não suportado. Use 'openai' ou 'google'.")


def coerce_response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered

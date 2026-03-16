from __future__ import annotations

from pathlib import Path

from langsmith import Client
from langsmith.utils import LangSmithConflictError

try:
    from .utils import (
        PROMPT_V2_PATH,
        build_chat_prompt_from_document,
        load_prompt_document,
        load_settings,
        unique_strings,
        validate_prompt_document,
    )
except ImportError:
    from utils import (
        PROMPT_V2_PATH,
        build_chat_prompt_from_document,
        load_prompt_document,
        load_settings,
        unique_strings,
        validate_prompt_document,
    )


def build_tags(prompt_document: dict[str, object]) -> list[str]:
    metadata = prompt_document.get("metadata", {})
    techniques = metadata.get("techniques", []) if isinstance(metadata, dict) else []
    version = metadata.get("version") if isinstance(metadata, dict) else None
    target_format = metadata.get("target_format") if isinstance(metadata, dict) else None
    status = metadata.get("status") if isinstance(metadata, dict) else None
    return unique_strings(
        [
            "bug-to-user-story",
            "prompt-engineering",
            "langsmith",
            f"version:{version}" if version else "",
            f"format:{target_format}" if target_format else "",
            f"status:{status}" if status else "",
            *[str(technique) for technique in techniques],
        ]
    )


def main() -> int:
    settings = load_settings()
    if not settings.langsmith_prompt_target or "/" not in settings.langsmith_prompt_target:
        raise RuntimeError(
            "LANGSMITH_PROMPT_TARGET deve estar definido como <usuario>/bug_to_user_story_v2."
        )

    prompt_document = load_prompt_document(PROMPT_V2_PATH)
    errors = validate_prompt_document(prompt_document)
    if errors:
        joined = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(f"O documento do prompt é inválido:\n{joined}")

    prompt = build_chat_prompt_from_document(prompt_document)
    client = Client()
    readme = Path("README.md").read_text(encoding="utf-8")

    try:
        url = client.push_prompt(
            settings.langsmith_prompt_target,
            object=prompt,
            description=str(prompt_document.get("description", "")).strip(),
            readme=readme,
            tags=build_tags(prompt_document),
            is_public=True,
        )
    except LangSmithConflictError as exc:
        message = str(exc)
        if "Nothing to commit" not in message:
            raise
        url = client._get_prompt_url(settings.langsmith_prompt_target)
        print("Nenhuma alteraÃ§Ã£o nova para publicar no prompt remoto.")
        print(f"Prompt atual jÃ¡ estÃ¡ sincronizado em: {url}")
        return 0

    print(f"Prompt publicado com sucesso: {settings.langsmith_prompt_target}")
    print(f"URL no LangSmith: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.load.dump import dumpd
from langsmith import Client

try:
    from .utils import (
        PROMPT_V1_PATH,
        RAW_PROMPTS_PATH,
        extract_prompt_messages,
        load_settings,
        write_yaml,
    )
except ImportError:
    from utils import (
        PROMPT_V1_PATH,
        RAW_PROMPTS_PATH,
        extract_prompt_messages,
        load_settings,
        write_yaml,
    )


def build_prompt_payload(prompt_identifier: str, messages: list[dict[str, str]]) -> dict[str, object]:
    system_prompt = next(
        (message["template"] for message in messages if message["role"] == "system"),
        "",
    )
    user_prompt = next(
        (message["template"] for message in reversed(messages) if message["role"] == "human"),
        "",
    )

    return {
        "name": prompt_identifier.split("/")[-1],
        "description": "Prompt baseline obtido do LangSmith Prompt Hub.",
        "metadata": {
            "version": "v1",
            "source": "langsmith",
            "original_prompt": prompt_identifier,
            "quality": "low",
            "status": "baseline",
        },
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "messages": messages,
    }


def main() -> int:
    settings = load_settings()
    client = Client()

    prompt = client.pull_prompt(settings.langsmith_prompt_source)
    messages = extract_prompt_messages(prompt)
    pulled_at = datetime.now(timezone.utc).isoformat()

    raw_payload = {
        "source_prompt": settings.langsmith_prompt_source,
        "pulled_at": pulled_at,
        "manifest": dumpd(prompt),
    }
    normalized_payload = build_prompt_payload(settings.langsmith_prompt_source, messages)

    write_yaml(RAW_PROMPTS_PATH, raw_payload)
    write_yaml(PROMPT_V1_PATH, normalized_payload)

    print(f"Prompt obtido do LangSmith: {settings.langsmith_prompt_source}")
    print(f"Manifesto bruto salvo em: {RAW_PROMPTS_PATH}")
    print(f"Prompt normalizado salvo em: {PROMPT_V1_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

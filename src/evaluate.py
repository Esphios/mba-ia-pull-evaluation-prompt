from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from statistics import fmean
from typing import Any, Callable

from langsmith import Client, evaluate

try:
    from .dataset import build_evaluation_examples, build_langsmith_examples
    from .metrics import (
        acceptance_criteria_score,
        completeness_score,
        tone_score,
        user_story_format_score,
    )
    from .utils import (
        PROMPT_V1_PATH,
        PROMPT_V2_PATH,
        build_chat_prompt_from_document,
        build_generation_model,
        coerce_response_text,
        load_prompt_document,
        load_settings,
    )
except ImportError:
    from dataset import build_evaluation_examples, build_langsmith_examples
    from metrics import (
        acceptance_criteria_score,
        completeness_score,
        tone_score,
        user_story_format_score,
    )
    from utils import (
        PROMPT_V1_PATH,
        PROMPT_V2_PATH,
        build_chat_prompt_from_document,
        build_generation_model,
        coerce_response_text,
        load_prompt_document,
        load_settings,
    )

EVALUATORS = [
    tone_score,
    acceptance_criteria_score,
    user_story_format_score,
    completeness_score,
]
THRESHOLD = 0.9
LOCAL_PROMPT_V1 = "local:v1"
LOCAL_PROMPT_V2 = "local:v2"


@dataclass(frozen=True)
class PromptVariant:
    name: str
    label: str
    prompt_reference: str
    source: str


def configure_console_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Avalia os prompts bug_to_user_story em modo local ou publicado."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Executa a avaliação local por exemplo e mostra os casos mais fracos.",
    )
    parser.add_argument(
        "--example",
        type=int,
        help="Inspeciona um exemplo específico do dataset local (índice começando em 1).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita a quantidade de exemplos locais processados no modo de debug.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Força a avaliação local sem publicar resultados no LangSmith.",
    )
    parser.add_argument(
        "--variant",
        choices=("auto", "v1", "v2", "all"),
        default="auto",
        help=(
            "Escolhe qual variante avaliar. 'auto' usa v2 no modo local e v1+v2 "
            "no modo publicado."
        ),
    )
    return parser.parse_args()


def resolve_requested_variant(args: argparse.Namespace) -> str:
    if args.variant != "auto":
        return args.variant
    return "v2"


def build_prompt_variants(
    *,
    requested_variant: str,
    should_upload: bool,
    settings: Any,
) -> list[PromptVariant]:
    variants: list[PromptVariant] = []

    if requested_variant in ("v1", "all"):
        prompt_reference = (
            settings.langsmith_prompt_source if should_upload else LOCAL_PROMPT_V1
        )
        variants.append(
            PromptVariant(
                name="v1",
                label="Prompt v1 baseline",
                prompt_reference=prompt_reference,
                source="langsmith" if should_upload else "local",
            )
        )

    if requested_variant in ("v2", "all"):
        if should_upload and not settings.langsmith_prompt_target:
            raise RuntimeError(
                "LANGSMITH_PROMPT_TARGET deve estar configurado para avaliar o prompt v2 publicado."
            )
        prompt_reference = (
            settings.langsmith_prompt_target if should_upload else LOCAL_PROMPT_V2
        )
        variants.append(
            PromptVariant(
                name="v2",
                label="Prompt v2 otimizado",
                prompt_reference=prompt_reference,
                source="langsmith" if should_upload else "local",
            )
        )

    if not variants:
        raise RuntimeError("Nenhuma variante de prompt foi selecionada para avaliação.")

    return variants


def load_prompt_for_reference(prompt_reference: str):
    if prompt_reference == LOCAL_PROMPT_V1:
        return build_chat_prompt_from_document(load_prompt_document(PROMPT_V1_PATH))
    if prompt_reference == LOCAL_PROMPT_V2:
        return build_chat_prompt_from_document(load_prompt_document(PROMPT_V2_PATH))
    client = Client()
    return client.pull_prompt(prompt_reference)


@lru_cache(maxsize=8)
def get_chain(prompt_reference: str):
    settings = load_settings()
    prompt = load_prompt_for_reference(prompt_reference)
    model = build_generation_model(settings)
    return prompt | model


def invoke_prompt(prompt_reference: str, inputs: dict[str, Any]) -> dict[str, str]:
    response = get_chain(prompt_reference).invoke({"bug_report": inputs["bug_report"]})
    return {"answer": coerce_response_text(response)}


def make_target(prompt_reference: str) -> Callable[[dict[str, Any]], dict[str, str]]:
    def target(inputs: dict[str, Any]) -> dict[str, str]:
        return invoke_prompt(prompt_reference, inputs)

    return target


def dataset_fingerprint(rows: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "inputs": row.get("inputs", {}),
            "outputs": row.get("outputs", {}),
        }
        for row in rows
    ]
    payload = "\n".join(
        sorted(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in normalized)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dataset_matches_local_copy(
    client: Client,
    dataset_id: str,
    rows: list[dict[str, Any]],
) -> bool:
    remote_examples = list(client.list_examples(dataset_id=dataset_id, limit=len(rows) + 1))
    if len(remote_examples) != len(rows):
        return False

    remote_rows = [
        {
            "inputs": example.inputs or {},
            "outputs": example.outputs or {},
        }
        for example in remote_examples
    ]
    return dataset_fingerprint(remote_rows) == dataset_fingerprint(rows)


def ensure_langsmith_dataset(
    client: Client,
    dataset_name: str,
    rows: list[dict[str, Any]],
):
    existing = next(client.list_datasets(dataset_name=dataset_name, limit=1), None)
    if existing is not None:
        if dataset_matches_local_copy(client, str(existing.id), rows):
            return existing

        print(
            f"O dataset '{dataset_name}' já existe, mas não corresponde à versão "
            "atual derivada de datasets/bug_to_user_story.jsonl. Ele será recriado."
        )
        client.delete_dataset(dataset_id=existing.id)

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="Dataset de avaliação para otimização do prompt bug report -> user story.",
        metadata={
            "source_file": "datasets/bug_to_user_story.jsonl",
            "example_count": len(rows),
            "fingerprint": dataset_fingerprint(rows),
        },
    )
    for row in rows:
        client.create_example(
            dataset_id=dataset.id,
            inputs=row["inputs"],
            outputs=row["outputs"],
            metadata=row.get("metadata"),
        )
    return dataset


def summarize_langsmith_results(results: Any) -> dict[str, float]:
    buckets: dict[str, list[float]] = {evaluator.__name__: [] for evaluator in EVALUATORS}

    for row in results:
        evaluation_results = row.get("evaluation_results", {})
        for evaluation in evaluation_results.get("results", []):
            score = getattr(evaluation, "score", None)
            key = getattr(evaluation, "key", "")
            if key in buckets and isinstance(score, (int, float)):
                buckets[key].append(float(score))

    return {
        key: round(fmean(values), 4) if values else 0.0
        for key, values in buckets.items()
    }


def score_example(row: dict[str, Any], prompt_reference: str) -> dict[str, Any]:
    outputs = invoke_prompt(prompt_reference, row["inputs"])
    scores: dict[str, float] = {}
    metric_results: dict[str, dict[str, Any]] = {}
    for evaluator in EVALUATORS:
        result = evaluator(
            inputs=row["inputs"],
            outputs=outputs,
            reference_outputs=row["outputs"],
        )
        scores[evaluator.__name__] = float(result["score"])
        metric_results[evaluator.__name__] = result

    return {
        "inputs": row["inputs"],
        "reference_outputs": row["outputs"],
        "outputs": outputs,
        "scores": scores,
        "metric_results": metric_results,
    }


def evaluate_rows_locally(
    rows: list[dict[str, Any]],
    prompt_reference: str,
    *,
    limit: int | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    selected_rows = rows[:limit] if limit else rows
    buckets: dict[str, list[float]] = {evaluator.__name__: [] for evaluator in EVALUATORS}
    details: list[dict[str, Any]] = []

    for index, row in enumerate(selected_rows, start=1):
        detail = score_example(row, prompt_reference)
        detail["index"] = index
        details.append(detail)
        for key, score in detail["scores"].items():
            buckets[key].append(score)

    summary = {
        key: round(fmean(values), 4) if values else 0.0
        for key, values in buckets.items()
    }
    return summary, details


def print_summary(scores: dict[str, float], label: str) -> bool:
    metric_labels = {
        "tone_score": "Tone Score",
        "acceptance_criteria_score": "Acceptance Criteria Score",
        "user_story_format_score": "User Story Format Score",
        "completeness_score": "Completeness Score",
    }

    print(f"\nResumo da avaliação: {label}")
    print("-" * (22 + len(label)))
    for key, metric_label in metric_labels.items():
        score = scores.get(key, 0.0)
        status = "OK" if score >= THRESHOLD else "FALHA"
        print(f"{metric_label}: {score:.4f} [{status}]")

    overall = round(fmean(scores.values()), 4) if scores else 0.0
    all_metrics_passed = all(score >= THRESHOLD for score in scores.values())
    overall_passed = overall >= THRESHOLD

    print(f"Média geral: {overall:.4f}")
    if all_metrics_passed and overall_passed:
        print("Status: APROVADO")
        return True

    print("Status: REPROVADO")
    return False


def print_debug_summary(details: list[dict[str, Any]], label: str, *, top_n: int = 5) -> None:
    if not details:
        return

    metric_labels = {
        "tone_score": "Tone Score",
        "acceptance_criteria_score": "Acceptance Criteria Score",
        "user_story_format_score": "User Story Format Score",
        "completeness_score": "Completeness Score",
    }

    print(f"\nExemplos locais mais fracos: {label}")
    print("-" * (30 + len(label)))
    weakest = sorted(
        details,
        key=lambda detail: (
            fmean(detail["scores"].values()),
            detail["scores"]["completeness_score"],
        ),
    )[:top_n]

    for detail in weakest:
        bug_report = str(detail["inputs"].get("bug_report", "")).replace("\n", " ").strip()
        weakest_metric = min(detail["scores"], key=detail["scores"].get)
        print(
            f"#{detail['index']}: "
            f"tone={detail['scores']['tone_score']:.4f}, "
            f"acceptance={detail['scores']['acceptance_criteria_score']:.4f}, "
            f"format={detail['scores']['user_story_format_score']:.4f}, "
            f"completeness={detail['scores']['completeness_score']:.4f}, "
            f"mais fraca={metric_labels[weakest_metric]}"
        )
        print(f"Bug: {bug_report[:220]}")
        print()


def print_debug_example(detail: dict[str, Any], label: str) -> None:
    print(f"\nExemplo em análise: {label}")
    print("-" * (20 + len(label)))
    print(f"Índice: {detail['index']}")
    for key, value in detail["scores"].items():
        print(f"{key}: {value:.4f}")
        comment = str(detail["metric_results"][key].get("comment", "")).strip()
        if comment:
            print(f"  {comment}")

    print("\nRelato do bug")
    print("-------------")
    print(detail["inputs"].get("bug_report", ""))

    print("\nResposta gerada")
    print("---------------")
    print(detail["outputs"].get("answer", ""))

    print("\nSaída de referência")
    print("-------------------")
    print(detail["reference_outputs"].get("reference", ""))


def build_comparison_url(project_url: str | None, dataset_id: Any) -> str | None:
    if not project_url:
        return None
    clean_project_url = project_url.split("?")[0]
    base_url = clean_project_url.split("/projects/p/")[0]
    project_id = clean_project_url.rsplit("/", maxsplit=1)[-1]
    return f"{base_url}/datasets/{dataset_id}/compare?selectedSessions={project_id}"


def evaluate_and_publish_variant(
    *,
    client: Client,
    dataset: Any,
    variant: PromptVariant,
) -> tuple[dict[str, float], str | None]:
    results = evaluate(
        make_target(variant.prompt_reference),
        data=dataset.name,
        evaluators=EVALUATORS,
        experiment_prefix=f"bug-to-user-story-{variant.name}",
        description=f"Avaliação automatizada da variante {variant.name} do prompt bug_to_user_story.",
        metadata={
            "prompt_variant": variant.name,
            "prompt_reference": variant.prompt_reference,
            "prompt_source": variant.source,
        },
        client=client,
    )
    scores = summarize_langsmith_results(results)
    project = client.read_project(project_name=results.experiment_name)
    comparison_url = build_comparison_url(getattr(project, "url", None), dataset.id)
    return scores, comparison_url


def main() -> int:
    configure_console_output()
    args = parse_args()
    settings = load_settings()

    local_rows = build_evaluation_examples()
    print(f"Usando dataset local: {settings.langsmith_dataset_name} ({len(local_rows)} exemplos)")

    has_langsmith_key = bool(os.getenv("LANGSMITH_API_KEY"))
    should_upload = has_langsmith_key and settings.langsmith_upload_results and not args.local
    requested_variant = resolve_requested_variant(args)

    if args.debug and requested_variant == "all":
        raise RuntimeError("--debug aceita apenas uma variante. Use --variant v1 ou --variant v2.")
    if args.example is not None and requested_variant == "all":
        raise RuntimeError("--example aceita apenas uma variante. Use --variant v1 ou --variant v2.")

    variants = build_prompt_variants(
        requested_variant=requested_variant,
        should_upload=should_upload,
        settings=settings,
    )

    if args.example is not None:
        variant = variants[0]
        if args.example < 1 or args.example > len(local_rows):
            raise RuntimeError(f"--example deve estar entre 1 e {len(local_rows)}.")
        detail = score_example(local_rows[args.example - 1], variant.prompt_reference)
        detail["index"] = args.example
        print_debug_example(detail, variant.label)
        return 0

    if args.debug:
        variant = variants[0]
        summary, details = evaluate_rows_locally(
            local_rows,
            variant.prompt_reference,
            limit=args.limit,
        )
        passed = print_summary(summary, variant.label)
        print_debug_summary(details, variant.label)
        return 0 if passed else 1

    if not should_upload:
        variant = variants[0]
        print(
            "LANGSMITH_API_KEY não configurada ou upload desabilitado. "
            "Executando apenas a avaliação local."
        )
        summary, _ = evaluate_rows_locally(local_rows, variant.prompt_reference)
        return 0 if print_summary(summary, variant.label) else 1

    client = Client()
    remote_rows = build_langsmith_examples(minimum_examples=20)
    dataset = ensure_langsmith_dataset(client, settings.langsmith_dataset_name, remote_rows)

    print(
        f"Dataset remoto: {dataset.name} ({len(remote_rows)} exemplos publicados no LangSmith)"
    )
    if getattr(dataset, "url", None):
        print(f"URL do dataset: {dataset.url}")
    if len(remote_rows) > len(local_rows):
        print(
            "Observação: o dataset remoto foi expandido de forma determinística para "
            "atingir o mínimo de 20 exemplos exigido pelo desafio, sem alterar o JSONL fonte."
        )

    variant_results: dict[str, bool] = {}
    for variant in variants:
        scores, comparison_url = evaluate_and_publish_variant(
            client=client,
            dataset=dataset,
            variant=variant,
        )
        passed = print_summary(scores, f"{variant.label} ({variant.source})")
        variant_results[variant.name] = passed
        if comparison_url:
            print(f"Comparação no LangSmith: {comparison_url}")

    if "v2" in variant_results:
        return 0 if variant_results["v2"] else 1
    return 0 if all(variant_results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

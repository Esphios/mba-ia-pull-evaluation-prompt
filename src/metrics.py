from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz

SECTION_ALIASES = {
    "title": ("## title", "## titulo", "titulo", "title:"),
    "user_story": (
        "## user story",
        "## historia do usuario",
        "user story",
        "historia do usuario",
    ),
    "context": ("## context", "## contexto", "contexto", "context:"),
    "acceptance_criteria": (
        "## acceptance criteria",
        "## criterios de aceitacao",
        "criterios de aceitacao",
        "acceptance criteria:",
    ),
    "edge_cases": (
        "## edge cases",
        "## casos de borda",
        "edge cases",
        "casos de borda",
    ),
    "assumptions": (
        "## assumptions / gaps",
        "## premissas / lacunas",
        "assumptions / gaps",
        "premissas / lacunas",
        "lacunas",
    ),
}

STOPWORDS = {
    "about",
    "after",
    "antes",
    "apos",
    "before",
    "cada",
    "com",
    "como",
    "comportamento",
    "criticas",
    "criticos",
    "contexto",
    "dado",
    "dados",
    "deve",
    "deveria",
    "entao",
    "exemplo",
    "essa",
    "esse",
    "funciona",
    "given",
    "have",
    "historia",
    "identificados",
    "input",
    "isso",
    "less",
    "mais",
    "muitas",
    "para",
    "problemas",
    "porque",
    "processo",
    "qualquer",
    "quando",
    "que",
    "quero",
    "retorna",
    "consegue",
    "sao",
    "sem",
    "should",
    "sistema",
    "story",
    "that",
    "then",
    "this",
    "titulo",
    "uma",
    "user",
    "users",
    "usuario",
    "usuarios",
    "bugs",
    "reportados",
    "vezes",
    "recebe",
    "apenas",
    "admins",
    "want",
    "when",
    "with",
    "criterios",
    "aceitacao",
    "principal",
    "normal",
    "outros",
    "mesmo",
    "campo",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    return re.sub(r"\s+", " ", ascii_text).strip()


def normalize_multiline_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower().replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in ascii_text.split("\n")]
    return "\n".join(lines)


def extract_answer(outputs: dict[str, Any]) -> str:
    return str(outputs.get("answer", "")).strip()


def has_any(text: str, options: tuple[str, ...]) -> bool:
    return any(option in text for option in options)


def bullet_count(answer: str) -> int:
    return len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+", answer))


def extract_keywords(text: str, *, limit: int = 12) -> list[str]:
    normalized = normalize_text(text)
    candidates = re.findall(r"[a-z0-9_:/.-]{4,}", normalized)
    keywords: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        candidate = candidate.strip(".,:;!?()[]{}'\"`")
        if not candidate:
            continue
        if candidate in STOPWORDS:
            continue
        if candidate.isdigit() and len(candidate) < 4:
            continue
        if candidate not in seen:
            seen.add(candidate)
            keywords.append(candidate)
        if len(keywords) >= limit:
            break

    return keywords


def extract_signals(text: str, *, limit: int = 12) -> list[str]:
    normalized = normalize_text(text)
    raw_signals = re.findall(
        r"last write wins|connection pool exhausted|gateway timeout|oom kill|n\+1|offline-first|"
        r"4g|"
        r"/[a-z0-9_:/.-]+|"
        r"\b\d+(?:[.,]\d+)?(?:%|px|mb|gb|ms|s)\b|"
        r"\b\d{3,}(?:[.,]\d+)?\b|"
        r"\b(?:ios|android|safari|chrome|postgres|redis|sql|xss|anr|mrr|csv|"
        r"timeout|webhook|checkout|gateway|api|http)\b",
        normalized,
    )

    signals: list[str] = []
    seen: set[str] = set()
    for signal in raw_signals:
        cleaned = signal.strip(".,:;!?()[]{}'\"`")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        signals.append(cleaned)
        if len(signals) >= limit:
            break

    return signals


def extract_issue_labels(text: str, *, limit: int = 8) -> list[str]:
    labels = re.findall(
        r"(?m)^\s*\d+\.\s*([a-z0-9 /_-]{3,50}?)(?:\s*-|:)",
        normalize_multiline_text(text),
    )
    cleaned: list[str] = []
    seen: set[str] = set()
    for label in labels:
        compact = " ".join(label.split())
        if not compact or compact in seen:
            continue
        seen.add(compact)
        cleaned.append(compact)
        if len(cleaned) >= limit:
            break
    return cleaned


def keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0

    normalized_answer = normalize_text(answer)
    hits = 0
    for keyword in keywords:
        ratio = fuzz.partial_ratio(keyword, normalized_answer)
        if ratio >= 86:
            hits += 1

    return hits / len(keywords)


def keyword_coverage_details(
    answer: str,
    keywords: list[str],
    *,
    threshold: int = 86,
) -> tuple[float, list[str], list[str]]:
    if not keywords:
        return 0.0, [], []

    normalized_answer = normalize_text(answer)
    matched: list[str] = []
    missing: list[str] = []

    for keyword in keywords:
        ratio = fuzz.partial_ratio(keyword, normalized_answer)
        if ratio >= threshold:
            matched.append(keyword)
        else:
            missing.append(keyword)

    coverage = len(matched) / len(keywords)
    return coverage, matched, missing


def preview_terms(items: list[str], *, limit: int = 5) -> str:
    if not items:
        return "nenhum"
    return ", ".join(items[:limit])


def has_placeholder_artifacts(text: str) -> bool:
    return bool(
        re.search(r"\[(?:todo|tbd)\]", text)
        or re.search(r"\b(?:todo|tbd):", text)
        or "lorem ipsum" in text
    )


def tone_score(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(outputs)
    text = normalize_text(answer)

    if not text:
        return {"score": 0.0, "comment": "Resposta vazia."}

    score = 0.0
    if ("como um" in text or "as a" in text) and ("eu quero" in text or "i want" in text):
        score += 0.45
    if "para que" in text or "so that" in text:
        score += 0.2
    if not has_placeholder_artifacts(text):
        score += 0.15
    if has_any(text, SECTION_ALIASES["acceptance_criteria"]) or has_any(
        text, SECTION_ALIASES["context"]
    ):
        score += 0.2

    missing_markers: list[str] = []
    if "como um" not in text and "as a" not in text:
        missing_markers.append("ator")
    if "eu quero" not in text and "i want" not in text:
        missing_markers.append("intenção")
    if "para que" not in text and "so that" not in text:
        missing_markers.append("valor")

    return {
        "score": round(min(score, 1.0), 4),
        "comment": (
            "Estrutura da user story com itens ausentes: "
            f"{preview_terms(missing_markers)}. "
            "Seção de contexto ou critérios presente: "
            f"{has_any(text, SECTION_ALIASES['acceptance_criteria']) or has_any(text, SECTION_ALIASES['context'])}. "
            f"Artefatos de placeholder: {has_placeholder_artifacts(text)}."
        ),
    }


def acceptance_criteria_score(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(outputs)
    text = normalize_text(answer)
    bullets = bullet_count(answer)
    scenario_markers = sum(
        marker in text for marker in ("dado", "quando", "entao", "given", "when", "then")
    )

    score = 0.0
    if has_any(text, SECTION_ALIASES["acceptance_criteria"]):
        score += 0.35
    if bullets >= 3:
        score += 0.35
    elif bullets == 2:
        score += 0.2
    elif bullets == 1:
        score += 0.1
    if scenario_markers >= 3:
        score += 0.2
    elif scenario_markers >= 2:
        score += 0.1
    if any(token in text for token in ("deve", "must", "nao deve", "must not")):
        score += 0.1

    return {
        "score": round(min(score, 1.0), 4),
        "comment": (
            f"Seção presente: {has_any(text, SECTION_ALIASES['acceptance_criteria'])}; "
            f"bullets: {bullets}; marcadores de cenário: {scenario_markers}; "
            f"linguagem normativa: {any(token in text for token in ('deve', 'must', 'nao deve', 'must not'))}."
        ),
    }


def user_story_format_score(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(outputs)
    text = normalize_text(answer)

    story_markers = [
        "como um" in text or "as a" in text,
        "eu quero" in text or "i want" in text,
        "para que" in text or "so that" in text,
    ]
    story_score = sum(story_markers) / len(story_markers)

    sections = (
        "title",
        "user_story",
        "context",
        "acceptance_criteria",
        "edge_cases",
        "assumptions",
    )
    section_hits = sum(has_any(text, SECTION_ALIASES[section]) for section in sections)
    section_score = section_hits / len(sections)
    missing_sections = [
        section for section in sections if not has_any(text, SECTION_ALIASES[section])
    ]

    score = (story_score * 0.55) + (section_score * 0.45)
    return {
        "score": round(min(score, 1.0), 4),
        "comment": (
            f"Seções ausentes: {preview_terms(missing_sections)}. "
            f"Marcadores da story presentes: ator={story_markers[0]}, intenção={story_markers[1]}, valor={story_markers[2]}."
        ),
    }


def completeness_score(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(outputs)
    bug_report = str(inputs.get("bug_report", ""))
    reference = str(reference_outputs.get("reference", ""))

    bug_keywords = extract_keywords(bug_report, limit=14)
    reference_keywords = extract_keywords(reference, limit=20)
    high_value_signals = extract_signals(bug_report, limit=14)
    issue_labels = extract_issue_labels(bug_report, limit=8)

    bug_coverage, _, missing_bug_keywords = keyword_coverage_details(answer, bug_keywords)
    reference_coverage, _, missing_reference_keywords = keyword_coverage_details(
        answer, reference_keywords
    )
    signal_coverage, _, missing_signals = keyword_coverage_details(answer, high_value_signals)

    context_bonus = 0.05 if has_any(normalize_text(answer), SECTION_ALIASES["context"]) else 0.0
    multi_issue_bonus = 0.0
    if bug_report.count("1.") and bug_report.count("2.") and "1." in answer:
        multi_issue_bonus = 0.05

    impact_bonus = 0.0
    normalized_bug = normalize_text(bug_report)
    impact_coverage = 0.0
    if "impacto" in normalized_bug or "impact:" in normalized_bug or "impact" in normalized_bug:
        impact_keywords = extract_keywords(bug_report.split("IMPACT", 1)[-1], limit=8)
        impact_coverage = keyword_coverage(answer, impact_keywords)
        if impact_coverage >= 0.5:
            impact_bonus = 0.05

    if issue_labels:
        issue_coverage, _, missing_issue_labels = keyword_coverage_details(answer, issue_labels)
    else:
        issue_coverage, missing_issue_labels = 0.0, []

    weighted_components: list[tuple[float, float]] = [
        (bug_coverage, 0.45),
        (reference_coverage, 0.05),
    ]

    if high_value_signals:
        weighted_components.append((signal_coverage, 0.20))
    else:
        weighted_components[0] = (weighted_components[0][0], weighted_components[0][1] + 0.20)

    if issue_labels:
        weighted_components.append((issue_coverage, 0.15))
    else:
        weighted_components[0] = (weighted_components[0][0], weighted_components[0][1] + 0.15)

    if impact_coverage > 0:
        weighted_components.append((impact_coverage, 0.10))
    else:
        weighted_components[0] = (weighted_components[0][0], weighted_components[0][1] + 0.10)

    total_weight = sum(weight for _, weight in weighted_components)
    weighted_score = sum(score * weight for score, weight in weighted_components) / total_weight

    detail_bonus = 0.0
    normalized_answer = normalize_text(answer)
    if (
        has_any(normalized_answer, SECTION_ALIASES["context"])
        and has_any(normalized_answer, SECTION_ALIASES["edge_cases"])
        and has_any(normalized_answer, SECTION_ALIASES["assumptions"])
        and bullet_count(answer) >= 6
    ):
        detail_bonus = 0.10

    score = min(
        weighted_score
        + context_bonus
        + multi_issue_bonus
        + impact_bonus
        + detail_bonus,
        1.0,
    )
    return {
        "score": round(score, 4),
        "comment": (
            f"bug={bug_coverage:.2f}, sinais={signal_coverage:.2f}, "
            f"problemas={issue_coverage:.2f}, referência={reference_coverage:.2f}; "
            f"termos do bug ausentes: {preview_terms(missing_bug_keywords)}; "
            f"sinais ausentes: {preview_terms(missing_signals)}; "
            f"rótulos de problema ausentes: {preview_terms(missing_issue_labels)}; "
            f"termos da referência ausentes: {preview_terms(missing_reference_keywords)}."
        ),
    }

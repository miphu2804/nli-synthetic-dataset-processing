CANONICAL_LABELS = {
    "0": "entailment",
    "entailment": "entailment",
    "1": "neutral",
    "neutral": "neutral",
    "2": "contradiction",
    "contradiction": "contradiction",
}

CANONICAL_LABEL_NAMES: frozenset[str] = frozenset(
    {"entailment", "neutral", "contradiction"}
)

CANONICAL_LABEL_NAMES_IN_ORDER: tuple[str, ...] = (
    "entailment",
    "neutral",
    "contradiction",
)


def canonical_label(label: str | int) -> str:
    key = str(label).strip().lower()
    return CANONICAL_LABELS.get(key, key)


def require_canonical_label(label: str | int) -> str:
    normalized = canonical_label(label)
    if normalized not in CANONICAL_LABEL_NAMES:
        raise ValueError(f"Unsupported NLI label: {label!r}")
    return normalized

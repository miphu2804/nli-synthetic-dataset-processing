NLI_LABEL_ALIASES = {
    "0": "entailment",
    "entailment": "entailment",
    "1": "neutral",
    "neutral": "neutral",
    "2": "contradiction",
    "contradiction": "contradiction",
}

SUPPORTED_NLI_LABELS: frozenset[str] = frozenset(
    {"entailment", "neutral", "contradiction"}
)

SUPPORTED_NLI_LABELS_IN_ORDER: tuple[str, ...] = (
    "entailment",
    "neutral",
    "contradiction",
)


def normalize_nli_label(label: str | int) -> str:
    key = str(label).strip().lower()
    return NLI_LABEL_ALIASES.get(key, key)


def require_supported_nli_label(label: str | int) -> str:
    normalized = normalize_nli_label(label)
    if normalized not in SUPPORTED_NLI_LABELS:
        raise ValueError(f"Unsupported NLI label: {label!r}")
    return normalized

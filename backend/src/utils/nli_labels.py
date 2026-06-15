CANONICAL_LABELS = {
    "0": "entailment",
    "entailment": "entailment",
    "1": "neutral",
    "neutral": "neutral",
    "2": "contradiction",
    "contradiction": "contradiction",
}


def canonical_label(label: str | int) -> str:
    key = str(label).strip().lower()
    return CANONICAL_LABELS.get(key, key)

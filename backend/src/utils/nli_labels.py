LABEL_ID_TO_NAME = {
    "0": "entailment",
    "1": "neutral",
    "2": "contradiction",
}

LABEL_NAMES: tuple[str, ...] = tuple(LABEL_ID_TO_NAME.values())
LABEL_NAME_TO_ID = {name: label_id for label_id, name in LABEL_ID_TO_NAME.items()}


def to_label_name(label: str | int) -> str:
    key = str(label).strip().lower()
    if key in LABEL_ID_TO_NAME:
        return LABEL_ID_TO_NAME[key]
    if key in LABEL_NAME_TO_ID:
        return key
    raise ValueError(f"Unsupported NLI label: {label!r}")

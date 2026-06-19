from collections import Counter
from pathlib import Path

from src.utils.nli_labels import CANONICAL_LABEL_NAMES_IN_ORDER, require_canonical_label
from src.utils.validation_aggregation.model_labels import _merge_model_labels


def compute_fleiss_kappa(
    model_label_paths: dict[str, str | Path],
    categories: list[str] | None = None,
) -> dict:
    """Compute Fleiss' Kappa inter-model agreement across the models' label files.

    Returns a dict with the kappa score, item/rater counts, the resolved categories, and per-category
    proportions. Raises if fewer than 2 models, no items, or labels fall outside the provided categories.
    """
    merged, label_columns = _merge_model_labels(model_label_paths)
    n_raters = len(label_columns)
    n_items = len(merged)
    if n_raters < 2:
        raise ValueError("Fleiss' Kappa requires at least 2 models (raters).")
    if n_items < 1:
        raise ValueError("Fleiss' Kappa requires at least 1 item.")

    item_labels = [
        [require_canonical_label(row[column]) for column in label_columns]
        for _, row in merged.iterrows()
    ]
    if categories is None:
        categories = list(CANONICAL_LABEL_NAMES_IN_ORDER)
    categories = _resolve_kappa_categories(item_labels, categories)
    kappa, per_category_proportion = _fleiss_kappa_from_counts(
        item_labels, categories, n_raters
    )

    return {
        "kappa": float(kappa),
        "n_items": n_items,
        "n_raters": n_raters,
        "categories": categories,
        "per_category_proportion": per_category_proportion,
    }


def _resolve_kappa_categories(
    item_labels: list[list[str]],
    categories: list[str] | None,
) -> list[str]:
    """Return the kappa category list: sorted observed labels when none given, else validate every label is allowed.

    Raises ValueError if an observed label falls outside the provided categories.
    """
    if categories is None:
        return sorted({label for labels in item_labels for label in labels})
    allowed = set(categories)
    unknown = sorted(
        {label for labels in item_labels for label in labels if label not in allowed}
    )
    if unknown:
        raise ValueError(
            f"Labels outside the provided categories: {', '.join(unknown)}"
        )
    return categories


def _fleiss_kappa_from_counts(
    item_labels: list[list[str]],
    categories: list[str],
    n_raters: int,
) -> tuple[float, dict[str, float]]:
    """Compute Fleiss' Kappa and per-category proportions from per-item label assignments.

    Builds the item-by-category count matrix, then kappa = (P_bar - P_e) / (1 - P_e), where P_bar is the
    mean per-item agreement and P_e the expected agreement from category marginals. Returns (kappa, proportions).
    """
    n_items = len(item_labels)
    counts = []
    for labels in item_labels:
        label_count = Counter(labels)
        counts.append([label_count.get(category, 0) for category in categories])

    p_i_values = [
        (sum(value * value for value in row) - n_raters) / (n_raters * (n_raters - 1))
        for row in counts
    ]
    p_bar = sum(p_i_values) / n_items

    per_category_proportion = {}
    for index, category in enumerate(categories):
        category_total = sum(row[index] for row in counts)
        per_category_proportion[category] = category_total / (n_items * n_raters)

    p_e = sum(value * value for value in per_category_proportion.values())
    kappa = 1.0 if (1 - p_e) == 0 else (p_bar - p_e) / (1 - p_e)
    return kappa, per_category_proportion

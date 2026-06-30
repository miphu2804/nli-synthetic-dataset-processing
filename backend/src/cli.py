import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.services.post_validation import (
    DEV_RATIO,
    GROUP_COLUMN,
    LABEL_COLUMN,
    MIN_JOINT_COUNT,
    PMI_THRESHOLD,
    SPLIT_SEED,
    TEST_RATIO,
    TRAIN_RATIO,
    ArtifactDetectionService,
    DatasetSplitService,
    ParaphraseService,
    ValidationAggregationService,
    VerdictFileCandidate,
    build_verdict_candidates,
    compute_fleiss_kappa,
    default_consensus_output_dir,
    discover_verdict_files,
    load_expected_labels,
)
from src.utils.project_paths import resolve_data_path
from src.utils.tabular_io import read_tabular, read_tabular_columns
from src.utils.validation_masking import write_masked_validation_dataset

DATASET_SUFFIXES = (".csv", ".parquet")
MASK_SEARCH_DIRS = (
    resolve_data_path("generated"),
    resolve_data_path("processed"),
    resolve_data_path("original"),
)
VERDICT_SEARCH_DIRS = (
    resolve_data_path("validation"),
    resolve_data_path("validated"),
)
VALIDATION_AGGREGATION_SERVICE = ValidationAggregationService()
ARTIFACT_DETECTION_SERVICE = ArtifactDetectionService()
PARAPHRASE_SERVICE = ParaphraseService()
DATASET_SPLIT_SERVICE = DatasetSplitService()


def read_dataset(path: Path) -> pd.DataFrame:
    return read_tabular(path)


def read_columns(path: Path) -> list[str]:
    return read_tabular_columns(path)


# --------------------------------------------------------------------------- #
# mask command
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DatasetCandidate:
    path: Path
    columns: list[str]


def discover_dataset_files(search_dirs: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for path in sorted(search_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in DATASET_SUFFIXES:
                candidates.append(path)
    return candidates


def build_dataset_candidates(paths: list[Path]) -> list[DatasetCandidate]:
    candidates: list[DatasetCandidate] = []
    for path in paths:
        try:
            columns = read_columns(path)
        except Exception:
            columns = []
        candidates.append(DatasetCandidate(path=path, columns=columns))
    return candidates


def infer_uid_column(columns: list[str]) -> str | None:
    if "source_uid" in columns:
        return "source_uid"
    if "uid" in columns:
        return "uid"
    return None


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(
        f"{input_path.stem}_validation_masked{input_path.suffix}"
    )


def render_candidates_table(
    console: Console,
    candidates: list[DatasetCandidate],
) -> None:
    table = Table(title="Validation Masking - Select Input Dataset")
    table.add_column("#", justify="right")
    table.add_column("Path")
    table.add_column("UID", style="cyan")
    table.add_column("Has label", justify="center")
    table.add_column("Columns")

    for index, candidate in enumerate(candidates, start=1):
        uid_column = infer_uid_column(candidate.columns) or "-"
        has_label = "yes" if "label" in candidate.columns else "no"
        table.add_row(
            str(index),
            str(candidate.path),
            uid_column,
            has_label,
            ", ".join(candidate.columns[:8]),
        )
    console.print(table)


def run_masking(
    input_path: Path,
    output_path: Path,
    uid_column: str,
    label_column: str,
) -> Path:
    dataframe = read_dataset(input_path)
    return write_masked_validation_dataset(
        dataframe,
        output_path=output_path,
        uid_column=uid_column,
        label_column=label_column,
    )


def _run_mask_command(args: argparse.Namespace, console: Console) -> int:
    search_dirs = [Path(item) for item in args.search_dir] or list(MASK_SEARCH_DIRS)
    input_path = Path(args.input).expanduser() if args.input else None

    if input_path is None:
        candidates = build_dataset_candidates(discover_dataset_files(search_dirs))
        if candidates:
            render_candidates_table(console, candidates)
            choice = IntPrompt.ask(
                "Choose dataset number",
                default=1,
                choices=[str(index) for index in range(1, len(candidates) + 1)],
            )
            input_path = candidates[choice - 1].path
        else:
            console.print(
                "[yellow]No CSV/parquet datasets found in search dirs.[/yellow]"
            )
            input_path = Path(Prompt.ask("Input dataset path")).expanduser()

    if not input_path.exists():
        console.print(f"[red]Input dataset not found:[/red] {input_path}")
        return 2

    columns = read_columns(input_path)
    uid_column = args.uid_column or infer_uid_column(columns)
    if uid_column is None:
        uid_column = Prompt.ask("UID column name", default="source_uid")

    output_path = (
        Path(args.output).expanduser()
        if args.output
        else default_output_path(input_path)
    )
    label_column = args.label_column

    console.print()
    console.print(f"[bold]Input:[/bold] {input_path}")
    console.print(f"[bold]Output:[/bold] {output_path}")
    console.print(f"[bold]UID column:[/bold] {uid_column}")
    console.print(f"[bold]Label column to drop:[/bold] {label_column}")
    if not args.yes and not Confirm.ask(
        "Create masked validation dataset?", default=True
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        return 1

    try:
        written_path = run_masking(
            input_path=input_path,
            output_path=output_path,
            uid_column=uid_column,
            label_column=label_column,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    masked_columns = read_columns(written_path)
    result_table = Table(title="Masked Dataset Created")
    result_table.add_column("Output")
    result_table.add_column("Columns")
    result_table.add_column("Label leaked?", justify="center")
    result_table.add_row(
        str(written_path),
        ", ".join(masked_columns),
        "yes" if label_column in masked_columns else "no",
    )
    console.print(result_table)
    return 0


# --------------------------------------------------------------------------- #
# aggregate command
# --------------------------------------------------------------------------- #
def render_verdict_candidates_table(
    console: Console,
    candidates: list[VerdictFileCandidate],
) -> None:
    table = Table(title="Verdict Files Discovered")
    table.add_column("#", justify="right")
    table.add_column("File")
    table.add_column("Model name")
    table.add_column("Valid?", justify="center")
    table.add_column("Columns")
    for index, candidate in enumerate(candidates, start=1):
        valid = "[green]yes[/green]" if candidate.is_valid else "[red]no[/red]"
        table.add_row(
            str(index),
            candidate.path.name,
            candidate.model_name,
            valid,
            ", ".join(candidate.columns[:6]),
        )
    console.print(table)


def run_aggregation(
    valid_candidates: list[VerdictFileCandidate],
    masked_dataset_path: Path,
    output_dir: Path,
    expected_labels: dict,
) -> dict:
    return VALIDATION_AGGREGATION_SERVICE.aggregate(
        valid_candidates=valid_candidates,
        masked_dataset_path=masked_dataset_path,
        output_dir=output_dir,
        expected_labels=expected_labels,
    )


def _resolve_verdicts_dir(args: argparse.Namespace, console: Console) -> Path | None:
    if args.verdicts_dir:
        return Path(args.verdicts_dir).expanduser()
    for verdict_dir in VERDICT_SEARCH_DIRS:
        if verdict_dir.exists():
            return verdict_dir
    raw = Prompt.ask("Path to directory containing model verdict files")
    return Path(raw).expanduser()


def _resolve_masked_input(args: argparse.Namespace, console: Console) -> Path | None:
    if args.masked_input:
        return Path(args.masked_input).expanduser()
    raw = Prompt.ask("Path to masked validation dataset")
    return Path(raw).expanduser()


def _resolve_expected_input(args: argparse.Namespace, console: Console) -> Path | None:
    if args.expected_input:
        return Path(args.expected_input).expanduser()
    raw = Prompt.ask("Path to original dataset with the expected_label column")
    return Path(raw).expanduser()


def _run_aggregate_command(args: argparse.Namespace, console: Console) -> int:
    verdicts_dir = _resolve_verdicts_dir(args, console)
    if verdicts_dir is None:
        return 2
    if not verdicts_dir.exists():
        console.print(f"[red]Verdicts directory not found:[/red] {verdicts_dir}")
        return 2

    candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
    valid_candidates = [c for c in candidates if c.is_valid]

    if candidates:
        render_verdict_candidates_table(console, candidates)

    if len(valid_candidates) != 3:
        console.print(
            f"[red]Need exactly 3 valid verdict files, found {len(valid_candidates)} "
            "(columns: source_uid, predicted_label, reason).[/red]"
        )
        return 2

    masked_input = _resolve_masked_input(args, console)
    if masked_input is None:
        return 2
    if not masked_input.exists():
        console.print(f"[red]Masked dataset not found:[/red] {masked_input}")
        return 2

    expected_input = _resolve_expected_input(args, console)
    if expected_input is None:
        return 2
    if not expected_input.exists():
        console.print(f"[red]Expected-label dataset not found:[/red] {expected_input}")
        return 2

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else verdicts_dir

    console.print()
    console.print(f"[bold]Verdicts dir:[/bold]  {verdicts_dir}")
    console.print(
        f"[bold]Models:[/bold]       {', '.join(c.model_name for c in valid_candidates)}"
    )
    console.print(f"[bold]Masked input:[/bold] {masked_input}")
    console.print(f"[bold]Expected input:[/bold] {expected_input}")
    console.print(f"[bold]Output dir:[/bold]   {output_dir}")

    if not args.yes and not Confirm.ask("Run aggregation?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return 1

    try:
        expected_labels = load_expected_labels(
            expected_input, args.uid_column, args.label_column
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        result = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=masked_input,
            output_dir=output_dir,
            expected_labels=expected_labels,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Aggregation Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Keep", str(result["keep"]))
    summary.add_row("Discard", str(result["discard"]))
    summary.add_row("Review", str(result["review"]))
    summary.add_row("Retained rows", str(result["retained_rows"]))
    summary.add_row("Review rows", str(result["review_rows"]))
    summary.add_row("Votes output", str(result["votes_output"]))
    summary.add_row("Validated dataset output", str(result["validated_output"]))
    summary.add_row("Review dataset output", str(result["review_output"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
# pmi command
# --------------------------------------------------------------------------- #
def run_pmi(
    input_path: Path,
    output_dir: Path,
    label_column: str,
    text_column: str,
    uid_column: str,
    pmi_threshold: float,
    min_joint_count: int,
) -> dict:
    return ARTIFACT_DETECTION_SERVICE.detect(
        input_path=input_path,
        output_dir=output_dir,
        label_column=label_column,
        text_column=text_column,
        uid_column=uid_column,
        pmi_threshold=pmi_threshold,
        min_joint_count=min_joint_count,
    )


def _run_pmi_command(args: argparse.Namespace, console: Console) -> int:
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        console.print(f"[red]Input dataset not found:[/red] {input_path}")
        return 2

    output_dir = (
        Path(args.output_dir).expanduser() if args.output_dir else input_path.parent
    )

    console.print(f"[bold]Input:[/bold]         {input_path}")
    console.print(f"[bold]Label column:[/bold]  {args.label_column}")
    console.print(f"[bold]Text column:[/bold]   {args.text_column}")
    console.print(f"[bold]PMI threshold:[/bold] {args.pmi_threshold}")
    console.print(f"[bold]Min count:[/bold]     {args.min_joint_count}")
    console.print(f"[bold]Output dir:[/bold]    {output_dir}")

    try:
        result = run_pmi(
            input_path=input_path,
            output_dir=output_dir,
            label_column=args.label_column,
            text_column=args.text_column,
            uid_column=args.uid_column,
            pmi_threshold=args.pmi_threshold,
            min_joint_count=args.min_joint_count,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="PMI Artifact Detection Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Artifact tokens", str(result["artifact_tokens"]))
    summary.add_row("Flagged rows (to paraphrase)", str(result["flagged_rows"]))
    summary.add_row("Tokens output", str(result["tokens_output"]))
    summary.add_row("Flagged rows output", str(result["rows_output"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
def run_consensus_pmi(
    valid_candidates: list[VerdictFileCandidate],
    masked_dataset_path: Path,
    expected_input_path: Path,
    output_dir: Path,
    uid_column: str,
    label_column: str,
    text_column: str,
    pmi_threshold: float,
    min_joint_count: int,
) -> dict:
    expected_labels = load_expected_labels(
        expected_input_path,
        uid_column,
        label_column,
    )
    aggregate_result = run_aggregation(
        valid_candidates=valid_candidates,
        masked_dataset_path=masked_dataset_path,
        output_dir=output_dir,
        expected_labels=expected_labels,
    )
    pmi_result = run_pmi(
        input_path=aggregate_result["validated_output"],
        output_dir=output_dir,
        label_column="label",
        text_column=text_column,
        uid_column=uid_column,
        pmi_threshold=pmi_threshold,
        min_joint_count=min_joint_count,
    )
    return {
        **aggregate_result,
        "pmi_tokens_output": pmi_result["tokens_output"],
        "pmi_rows_output": pmi_result["rows_output"],
        "pmi_total_rows": pmi_result["total_rows"],
        "artifact_tokens": pmi_result["artifact_tokens"],
        "flagged_rows": pmi_result["flagged_rows"],
    }


def _run_consensus_pmi_command(args: argparse.Namespace, console: Console) -> int:
    verdicts_dir = Path(args.verdicts_dir).expanduser()
    if not verdicts_dir.exists():
        console.print(f"[red]Verdicts directory not found:[/red] {verdicts_dir}")
        return 2
    masked_input = Path(args.masked_input).expanduser()
    if not masked_input.exists():
        console.print(f"[red]Masked dataset not found:[/red] {masked_input}")
        return 2
    expected_input = Path(args.expected_input).expanduser()
    if not expected_input.exists():
        console.print(f"[red]Expected-label dataset not found:[/red] {expected_input}")
        return 2

    candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
    valid_candidates = [candidate for candidate in candidates if candidate.is_valid]
    if candidates:
        render_verdict_candidates_table(console, candidates)
    if len(valid_candidates) != 3:
        console.print(
            f"[red]Need exactly 3 valid verdict files, found {len(valid_candidates)} "
            "(columns: source_uid, predicted_label, reason).[/red]"
        )
        return 2

    output_dir = (
        Path(args.output_dir).expanduser()
        if args.output_dir
        else default_consensus_output_dir(expected_input)
    )
    console.print(f"[bold]Verdicts dir:[/bold]  {verdicts_dir}")
    console.print(f"[bold]Masked input:[/bold] {masked_input}")
    console.print(f"[bold]Expected input:[/bold] {expected_input}")
    console.print(f"[bold]Output dir:[/bold]   {output_dir}")
    console.print(f"[bold]PMI threshold:[/bold] {args.pmi_threshold}")
    console.print(f"[bold]Min count:[/bold]     {args.min_joint_count}")
    if not args.yes and not Confirm.ask("Run consensus + PMI?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return 1

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = run_consensus_pmi(
            valid_candidates=valid_candidates,
            masked_dataset_path=masked_input,
            expected_input_path=expected_input,
            output_dir=output_dir,
            uid_column=args.uid_column,
            label_column=args.label_column,
            text_column=args.text_column,
            pmi_threshold=args.pmi_threshold,
            min_joint_count=args.min_joint_count,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Consensus + PMI Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Keep", str(result["keep"]))
    summary.add_row("Review", str(result["review"]))
    summary.add_row("Discard", str(result["discard"]))
    summary.add_row("PMI rows scored", str(result["pmi_total_rows"]))
    summary.add_row("Artifact tokens", str(result["artifact_tokens"]))
    summary.add_row("Flagged rows", str(result["flagged_rows"]))
    summary.add_row("Votes output", str(result["votes_output"]))
    summary.add_row("Validated output", str(result["validated_output"]))
    summary.add_row("Review output", str(result["review_output"]))
    summary.add_row("PMI tokens output", str(result["pmi_tokens_output"]))
    summary.add_row("PMI flagged rows output", str(result["pmi_rows_output"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
# kappa command
# --------------------------------------------------------------------------- #
KAPPA_THRESHOLD = 0.85


def run_kappa(verdicts_dir: Path) -> dict:
    candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
    valid_candidates = [c for c in candidates if c.is_valid]
    if len(valid_candidates) != 3:
        raise ValueError(
            f"Fleiss' Kappa requires exactly 3 valid verdict files, "
            f"found {len(valid_candidates)}."
        )
    model_prediction_paths = {
        candidate.model_name: candidate.path for candidate in valid_candidates
    }
    result = compute_fleiss_kappa(model_prediction_paths)
    result["models"] = list(model_prediction_paths.keys())
    return result


def _run_kappa_command(args: argparse.Namespace, console: Console) -> int:
    verdicts_dir = Path(args.verdicts_dir).expanduser()
    if not verdicts_dir.exists():
        console.print(f"[red]Verdicts directory not found:[/red] {verdicts_dir}")
        return 2

    candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
    valid_candidates = [c for c in candidates if c.is_valid]
    if candidates:
        render_verdict_candidates_table(console, candidates)

    if len(valid_candidates) != 3:
        console.print(
            f"[red]Need exactly 3 valid verdict files, found {len(valid_candidates)} "
            "(columns: source_uid, predicted_label, reason).[/red]"
        )
        return 2

    try:
        result = run_kappa(verdicts_dir)
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    kappa = result["kappa"]
    summary = Table(title="Fleiss' Kappa (Prompt Calibration)")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Kappa", f"{kappa:.4f}")
    summary.add_row("Items", str(result["n_items"]))
    summary.add_row("Raters (models)", str(result["n_raters"]))
    summary.add_row("Models", ", ".join(result["models"]))
    console.print(summary)
    if kappa >= KAPPA_THRESHOLD:
        console.print("[green]κ ≥ 0.85 → accepted[/green]")
    else:
        console.print("[yellow]κ < 0.85 → review disagreement evidence[/yellow]")
    return 0


# --------------------------------------------------------------------------- #
# apply-paraphrase command
# --------------------------------------------------------------------------- #
def run_apply_paraphrase(
    input_path: Path,
    flagged_rows_path: Path,
    paraphrases_path: Path,
    output_path: Path,
    revalidation_path: Path,
) -> dict:
    return PARAPHRASE_SERVICE.apply(
        input_path=input_path,
        flagged_rows_path=flagged_rows_path,
        paraphrases_path=paraphrases_path,
        output_path=output_path,
        revalidation_path=revalidation_path,
    )


def _run_apply_paraphrase_command(args: argparse.Namespace, console: Console) -> int:
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        console.print(f"[red]Validated dataset not found:[/red] {input_path}")
        return 2
    flagged_rows_path = Path(args.flagged_rows).expanduser()
    if not flagged_rows_path.exists():
        console.print(f"[red]Flagged rows file not found:[/red] {flagged_rows_path}")
        return 2
    paraphrases_path = Path(args.paraphrases).expanduser()
    if not paraphrases_path.exists():
        console.print(f"[red]Paraphrases file not found:[/red] {paraphrases_path}")
        return 2

    output_path = (
        Path(args.output).expanduser()
        if args.output
        else input_path.with_name("paraphrased_dataset.csv")
    )
    revalidation_path = output_path.with_name("paraphrase_revalidation_masked.csv")

    console.print(f"[bold]Input:[/bold]        {input_path}")
    console.print(f"[bold]Flagged rows:[/bold] {flagged_rows_path}")
    console.print(f"[bold]Paraphrases:[/bold]  {paraphrases_path}")
    console.print(f"[bold]Output:[/bold]       {output_path}")
    console.print(f"[bold]Revalidation:[/bold] {revalidation_path}")

    try:
        result = run_apply_paraphrase(
            input_path=input_path,
            flagged_rows_path=flagged_rows_path,
            paraphrases_path=paraphrases_path,
            output_path=output_path,
            revalidation_path=revalidation_path,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Paraphrase Apply Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Replaced rows", str(result["replaced_rows"]))
    summary.add_row("Paraphrased dataset output", str(result["output_path"]))
    summary.add_row("Revalidation queue", str(result["revalidation_path"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
# promote-paraphrase command
# --------------------------------------------------------------------------- #
def run_promote_paraphrase(
    input_path: Path,
    revalidation_input_path: Path,
    verdict_candidates: list[VerdictFileCandidate],
    expected_input_path: Path,
    output_path: Path,
    review_output_path: Path,
    votes_output_path: Path,
    uid_column: str,
    label_column: str,
) -> dict:
    return PARAPHRASE_SERVICE.promote(
        input_path=input_path,
        revalidation_input_path=revalidation_input_path,
        verdict_candidates=verdict_candidates,
        expected_input_path=expected_input_path,
        output_path=output_path,
        review_output_path=review_output_path,
        votes_output_path=votes_output_path,
        uid_column=uid_column,
        label_column=label_column,
    )


def _run_promote_paraphrase_command(
    args: argparse.Namespace,
    console: Console,
) -> int:
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        console.print(f"[red]Paraphrased dataset not found:[/red] {input_path}")
        return 2
    revalidation_input = Path(args.revalidation_input).expanduser()
    if not revalidation_input.exists():
        console.print(f"[red]Revalidation input not found:[/red] {revalidation_input}")
        return 2
    expected_input = Path(args.expected_input).expanduser()
    if not expected_input.exists():
        console.print(f"[red]Expected-label dataset not found:[/red] {expected_input}")
        return 2
    verdicts_dir = Path(args.verdicts_dir).expanduser()
    if not verdicts_dir.exists():
        console.print(f"[red]Verdicts directory not found:[/red] {verdicts_dir}")
        return 2

    candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
    valid_candidates = [candidate for candidate in candidates if candidate.is_valid]
    if candidates:
        render_verdict_candidates_table(console, candidates)
    if len(valid_candidates) != 3:
        console.print(
            f"[red]Need exactly 3 valid verdict files, found {len(valid_candidates)} "
            "(columns: source_uid, predicted_label, reason).[/red]"
        )
        return 2

    output_path = (
        Path(args.output).expanduser()
        if args.output
        else input_path.with_name("promoted_dataset.csv")
    )
    review_output_path = (
        Path(args.review_output).expanduser()
        if args.review_output
        else output_path.with_name("paraphrase_revalidation_review.csv")
    )
    votes_output_path = (
        Path(args.votes_output).expanduser()
        if args.votes_output
        else output_path.with_name("paraphrase_revalidation_votes.csv")
    )

    try:
        result = run_promote_paraphrase(
            input_path=input_path,
            revalidation_input_path=revalidation_input,
            verdict_candidates=valid_candidates,
            expected_input_path=expected_input,
            output_path=output_path,
            review_output_path=review_output_path,
            votes_output_path=votes_output_path,
            uid_column=args.uid_column,
            label_column=args.label_column,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Paraphrase Promotion Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Promoted rows", str(result["promoted_rows"]))
    summary.add_row("Revalidated rows", str(result["revalidated_rows"]))
    summary.add_row("Accepted rewrites", str(result["accepted_rewrites"]))
    summary.add_row("Review rewrites", str(result["review_rewrites"]))
    summary.add_row("Discarded rewrites", str(result["discarded_rewrites"]))
    summary.add_row("Promoted dataset output", str(result["output_path"]))
    summary.add_row("Review output", str(result["review_output_path"]))
    summary.add_row("Votes output", str(result["votes_output_path"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
# split command
# --------------------------------------------------------------------------- #
def run_split(
    input_path: Path,
    output_dir: Path,
    group_column: str,
    label_column: str,
    domain_column: str | None,
    train_ratio: float,
    dev_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict:
    return DATASET_SPLIT_SERVICE.split(
        input_path=input_path,
        output_dir=output_dir,
        group_column=group_column,
        label_column=label_column,
        domain_column=domain_column,
        train_ratio=train_ratio,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )


def _run_split_command(args: argparse.Namespace, console: Console) -> int:
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        console.print(f"[red]Input dataset not found:[/red] {input_path}")
        return 2
    output_dir = Path(args.output_dir).expanduser()

    console.print(f"[bold]Input:[/bold]        {input_path}")
    console.print(f"[bold]Output dir:[/bold]   {output_dir}")
    console.print(f"[bold]Group column:[/bold] {args.group_column}")
    console.print(f"[bold]Label column:[/bold] {args.label_column}")
    console.print(f"[bold]Domain column:[/bold] {args.domain_column or '-'}")
    console.print(
        "[bold]Ratios:[/bold]       "
        f"{args.train_ratio}:{args.dev_ratio}:{args.test_ratio}"
    )
    console.print(f"[bold]Seed:[/bold]         {args.seed}")

    try:
        result = run_split(
            input_path=input_path,
            output_dir=output_dir,
            group_column=args.group_column,
            label_column=args.label_column,
            domain_column=args.domain_column,
            train_ratio=args.train_ratio,
            dev_ratio=args.dev_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Grouped Split Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Strategy", str(result["strategy"]))
    summary.add_row("Domain status", str(result["domain_status"]))
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Total premise groups", str(result["total_groups"]))
    summary.add_row("Train rows", str(result["train_rows"]))
    summary.add_row("Dev rows", str(result["dev_rows"]))
    summary.add_row("Test rows", str(result["test_rows"]))
    summary.add_row("Train output", str(result["train_output"]))
    summary.add_row("Dev output", str(result["dev_output"]))
    summary.add_row("Test output", str(result["test_output"]))
    summary.add_row("Manifest output", str(result["manifest_output"]))
    console.print(summary)
    return 0


# --------------------------------------------------------------------------- #
# dispatch
# --------------------------------------------------------------------------- #
_COMMAND_HANDLERS = {
    "mask": _run_mask_command,
    "aggregate": _run_aggregate_command,
    "pmi": _run_pmi_command,
    "consensus-pmi": _run_consensus_pmi_command,
    "kappa": _run_kappa_command,
    "apply-paraphrase": _run_apply_paraphrase_command,
    "promote-paraphrase": _run_promote_paraphrase_command,
    "split": _run_split_command,
    # "lexical": _run_lexical_command,  # future
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    console = Console(quiet=args.quiet)
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args, console)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validation-cli",
        description=(
            "Deterministic validation pipeline: masking, multi-model consensus "
            "aggregation, and PMI artifact detection (ViLegalNLI)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    _add_mask_parser(subparsers)
    _add_aggregate_parser(subparsers)
    _add_pmi_parser(subparsers)
    _add_consensus_pmi_parser(subparsers)
    _add_kappa_parser(subparsers)
    _add_apply_paraphrase_parser(subparsers)
    _add_promote_paraphrase_parser(subparsers)
    _add_split_parser(subparsers)
    # _add_lexical_parser(subparsers)  # future
    return parser


def _add_mask_parser(subparsers: argparse._SubParsersAction) -> None:
    mask = subparsers.add_parser(
        "mask",
        help="Create a validation dataset with label values removed.",
    )
    mask.add_argument("--input", help="Input CSV/parquet dataset path.")
    mask.add_argument("--output", help="Output masked dataset path.")
    mask.add_argument("--uid-column", help="UID column. Defaults to source_uid or uid.")
    mask.add_argument(
        "--label-column",
        default="label",
        help="Label column to remove. Default: label.",
    )
    mask.add_argument(
        "--search-dir",
        action="append",
        default=[],
        help="Directory to scan when --input is omitted. Can be repeated.",
    )
    mask.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for scripted runs.",
    )
    mask.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_aggregate_parser(subparsers: argparse._SubParsersAction) -> None:
    aggregate = subparsers.add_parser(
        "aggregate",
        help="Aggregate three validator verdict files into keep/review/discard outputs.",
    )
    aggregate.add_argument(
        "--verdicts-dir",
        help="Directory containing model verdict CSV/parquet files (e.g. gpt4o.csv).",
    )
    aggregate.add_argument(
        "--masked-input",
        help="Path to masked validation dataset.",
    )
    aggregate.add_argument(
        "--expected-input",
        help="Original dataset (with the expected_label/label column) "
        "to score consensus against.",
    )
    aggregate.add_argument(
        "--uid-column",
        default="source_uid",
        help="UID column in the expected-label dataset. Default: source_uid.",
    )
    aggregate.add_argument(
        "--label-column",
        default="label",
        help="Expected-label column in the expected-label dataset. Default: label.",
    )
    aggregate.add_argument(
        "--output-dir",
        help="Directory for validation_votes.csv and validated_dataset.csv. "
        "Defaults to --verdicts-dir.",
    )
    aggregate.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for scripted runs.",
    )
    aggregate.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_pmi_parser(subparsers: argparse._SubParsersAction) -> None:
    pmi = subparsers.add_parser(
        "pmi",
        help="Flag label-leaking artifact tokens and the rows that carry them.",
    )
    pmi.add_argument(
        "--input",
        required=True,
        help="Path to a labeled dataset (CSV/parquet) with a settled label column.",
    )
    pmi.add_argument(
        "--label-column",
        default=LABEL_COLUMN,
        help="Label column to score against. Default: label "
        "(matches validated_dataset.csv).",
    )
    pmi.add_argument(
        "--text-column",
        default="hypothesis",
        help="Text column to tokenize. Default: hypothesis.",
    )
    pmi.add_argument(
        "--uid-column",
        default="source_uid",
        help="Row identifier column. Default: source_uid.",
    )
    pmi.add_argument(
        "--pmi-threshold",
        type=float,
        default=PMI_THRESHOLD,
        help="Minimum PMI for a (token, label) pair to count as an artifact. "
        "Default: 1.0. Tune per dataset.",
    )
    pmi.add_argument(
        "--min-joint-count",
        type=int,
        default=MIN_JOINT_COUNT,
        help="Minimum joint token-label count included in PMI. Default: 3.",
    )
    pmi.add_argument(
        "--output-dir",
        help="Directory for output CSVs. Defaults to the input file's directory.",
    )
    pmi.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_consensus_pmi_parser(subparsers: argparse._SubParsersAction) -> None:
    consensus = subparsers.add_parser(
        "consensus-pmi",
        help="Run consensus aggregation and PMI artifact detection in one step.",
    )
    consensus.add_argument(
        "--verdicts-dir",
        required=True,
        help="Directory containing exactly three model verdict CSV/parquet files.",
    )
    consensus.add_argument(
        "--masked-input",
        required=True,
        help="Path to masked validation dataset.",
    )
    consensus.add_argument(
        "--expected-input",
        required=True,
        help="Original dataset with trusted expected labels.",
    )
    consensus.add_argument(
        "--uid-column",
        default="source_uid",
        help="UID column in --expected-input. Default: source_uid.",
    )
    consensus.add_argument(
        "--label-column",
        default=LABEL_COLUMN,
        help="Expected-label column in --expected-input. Default: label.",
    )
    consensus.add_argument(
        "--text-column",
        default="hypothesis",
        help="Text column for PMI. Default: hypothesis.",
    )
    consensus.add_argument(
        "--pmi-threshold",
        type=float,
        default=PMI_THRESHOLD,
        help="Minimum PMI for a token-label artifact. Default: 1.0.",
    )
    consensus.add_argument(
        "--min-joint-count",
        type=int,
        default=MIN_JOINT_COUNT,
        help="Minimum joint token-label count included in PMI. Default: 3.",
    )
    consensus.add_argument(
        "--output-dir",
        help="Directory for aggregate and PMI outputs. Defaults to data/validated/<expected-input-stem>.",
    )
    consensus.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for scripted runs.",
    )
    consensus.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_kappa_parser(subparsers: argparse._SubParsersAction) -> None:
    kappa = subparsers.add_parser(
        "kappa",
        help="Compute Fleiss' Kappa inter-model agreement over calibration verdicts.",
    )
    kappa.add_argument(
        "--verdicts-dir",
        required=True,
        help="Directory containing model verdict CSV/parquet files (e.g. gpt4o.csv).",
    )
    kappa.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_apply_paraphrase_parser(subparsers: argparse._SubParsersAction) -> None:
    apply = subparsers.add_parser(
        "apply-paraphrase",
        help="Overwrite PMI-flagged hypotheses with paraphrased rewrites. "
        "Emits paraphrased_dataset.csv and paraphrase_revalidation_masked.csv.",
    )
    apply.add_argument(
        "--input",
        required=True,
        help="Validated dataset (e.g. validated_dataset.csv) to update.",
    )
    apply.add_argument(
        "--flagged-rows",
        required=True,
        help="CSV/parquet of PMI-flagged rows (e.g. pmi_flagged_rows.csv).",
    )
    apply.add_argument(
        "--paraphrases",
        required=True,
        help="CSV/parquet of paraphrased rows (source_uid + rewritten hypothesis).",
    )
    apply.add_argument(
        "--output",
        help="Output path. Defaults to paraphrased_dataset.csv next to --input.",
    )
    apply.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_promote_paraphrase_parser(subparsers: argparse._SubParsersAction) -> None:
    promote = subparsers.add_parser(
        "promote-paraphrase",
        help="Promote paraphrased rows that pass semantic revalidation.",
    )
    promote.add_argument(
        "--input",
        required=True,
        help="Paraphrased candidate dataset, e.g. paraphrased_dataset.csv.",
    )
    promote.add_argument(
        "--revalidation-input",
        required=True,
        help="Changed-row revalidation queue with blank labels, e.g. paraphrase_revalidation_masked.csv.",
    )
    promote.add_argument(
        "--verdicts-dir",
        required=True,
        help="Directory containing exactly three revalidation verdict files.",
    )
    promote.add_argument(
        "--expected-input",
        required=True,
        help="Trusted label dataset for the changed row UIDs.",
    )
    promote.add_argument(
        "--output",
        help="Output path. Defaults to promoted_dataset.csv next to --input.",
    )
    promote.add_argument(
        "--review-output",
        help="Review output path for non-promoted changed rows.",
    )
    promote.add_argument(
        "--votes-output",
        help="Vote table output path for revalidated changed rows.",
    )
    promote.add_argument(
        "--uid-column",
        default="source_uid",
        help="Row identifier column. Default: source_uid.",
    )
    promote.add_argument(
        "--label-column",
        default="label",
        help="Expected-label column in --expected-input. Default: label.",
    )
    promote.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


def _add_split_parser(subparsers: argparse._SubParsersAction) -> None:
    split = subparsers.add_parser(
        "split",
        help="Create deterministic grouped-stratified train/dev/test splits.",
    )
    split.add_argument(
        "--input",
        required=True,
        help="Final validated/promoted dataset path.",
    )
    split.add_argument(
        "--output-dir",
        required=True,
        help="Directory for train.csv, dev.csv, test.csv, and split_manifest.json.",
    )
    split.add_argument(
        "--group-column",
        default=GROUP_COLUMN,
        help="Grouping column that must not cross splits. Default: premise.",
    )
    split.add_argument(
        "--label-column",
        default=LABEL_COLUMN,
        help="Label column used for manifest distributions. Default: label.",
    )
    split.add_argument(
        "--domain-column",
        help="Optional domain/subdomain column to preserve alongside labels.",
    )
    split.add_argument(
        "--train-ratio",
        type=float,
        default=TRAIN_RATIO,
        help="Train split ratio. Default: 0.8.",
    )
    split.add_argument(
        "--dev-ratio",
        type=float,
        default=DEV_RATIO,
        help="Dev split ratio. Default: 0.1.",
    )
    split.add_argument(
        "--test-ratio",
        type=float,
        default=TEST_RATIO,
        help="Test split ratio. Default: 0.1.",
    )
    split.add_argument(
        "--seed",
        type=int,
        default=SPLIT_SEED,
        help="Deterministic group shuffle seed. Default: 13.",
    )
    split.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )


if __name__ == "__main__":
    raise SystemExit(main())

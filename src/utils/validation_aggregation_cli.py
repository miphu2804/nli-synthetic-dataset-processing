import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.utils.validation_aggregation import (
    attach_masked_text,
    build_validation_vote_table,
    compute_hypothesis_label_pmi,
)

DATASET_SUFFIXES = (".csv", ".parquet")
VERDICT_REQUIRED_COLUMNS = {"source_uid", "predicted_label", "reason"}
DEFAULT_SEARCH_DIRS = (
    Path("data/validation"),
    Path("data/validated"),
)


@dataclass(frozen=True)
class VerdictFileCandidate:
    path: Path
    columns: list[str]
    model_name: str
    is_valid: bool


def discover_verdict_files(search_dir: Path) -> list[Path]:
    if not search_dir.exists():
        return []
    return sorted(
        path
        for path in search_dir.iterdir()
        if path.is_file() and path.suffix.lower() in DATASET_SUFFIXES
    )


def build_verdict_candidates(paths: list[Path]) -> list[VerdictFileCandidate]:
    candidates = []
    for path in paths:
        try:
            columns = _read_columns(path)
        except Exception:
            columns = []
        is_valid = VERDICT_REQUIRED_COLUMNS.issubset(set(columns))
        candidates.append(
            VerdictFileCandidate(
                path=path,
                columns=columns,
                model_name=path.stem,
                is_valid=is_valid,
            )
        )
    return candidates


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
    min_joint_count: int,
) -> dict:
    model_label_paths = {
        candidate.model_name: candidate.path for candidate in valid_candidates
    }
    vote_table = build_validation_vote_table(model_label_paths)
    votes_output = output_dir / "validation_votes.csv"
    vote_table.to_csv(votes_output, index=False)

    masked_df = _read_dataset(masked_dataset_path)
    analysis_df = attach_masked_text(masked_df, vote_table)
    pmi_df = compute_hypothesis_label_pmi(
        analysis_df,
        label_column="consensus_label",
        text_column="hypothesis",
        min_joint_count=min_joint_count,
    )
    pmi_output = output_dir / "pmi_consensus.csv"
    pmi_df.to_csv(pmi_output, index=False)

    agreement_counts = vote_table["agreement_status"].value_counts().to_dict()
    return {
        "votes_output": votes_output,
        "pmi_output": pmi_output,
        "total_rows": len(vote_table),
        "unanimous": agreement_counts.get("unanimous", 0),
        "majority": agreement_counts.get("majority", 0),
        "review": agreement_counts.get("review", 0),
        "pmi_tokens": len(pmi_df),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    console = Console(quiet=args.quiet)

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

    if len(valid_candidates) < 2:
        console.print(
            "[red]Need at least 2 valid verdict files "
            "(columns: source_uid, predicted_label, reason).[/red]"
        )
        return 2

    masked_input = _resolve_masked_input(args, console)
    if masked_input is None:
        return 2
    if not masked_input.exists():
        console.print(f"[red]Masked dataset not found:[/red] {masked_input}")
        return 2

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else verdicts_dir

    console.print()
    console.print(f"[bold]Verdicts dir:[/bold]  {verdicts_dir}")
    console.print(
        f"[bold]Models:[/bold]       {', '.join(c.model_name for c in valid_candidates)}"
    )
    console.print(f"[bold]Masked input:[/bold] {masked_input}")
    console.print(f"[bold]Output dir:[/bold]   {output_dir}")
    console.print(f"[bold]PMI min count:[/bold] {args.min_joint_count}")

    if not args.yes and not Confirm.ask("Run aggregation and PMI?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return 1

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=masked_input,
            output_dir=output_dir,
            min_joint_count=args.min_joint_count,
        )
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        return 2

    summary = Table(title="Aggregation Complete")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total rows", str(result["total_rows"]))
    summary.add_row("Unanimous", str(result["unanimous"]))
    summary.add_row("Majority", str(result["majority"]))
    summary.add_row("Review (no majority)", str(result["review"]))
    summary.add_row("PMI tokens", str(result["pmi_tokens"]))
    summary.add_row("Votes output", str(result["votes_output"]))
    summary.add_row("PMI output", str(result["pmi_output"]))
    console.print(summary)
    return 0


def _resolve_verdicts_dir(args: argparse.Namespace, console: Console) -> Path | None:
    if args.verdicts_dir:
        return Path(args.verdicts_dir).expanduser()
    for default_dir in DEFAULT_SEARCH_DIRS:
        if default_dir.exists():
            return default_dir
    raw = Prompt.ask("Path to directory containing model verdict files")
    return Path(raw).expanduser()


def _resolve_masked_input(args: argparse.Namespace, console: Console) -> Path | None:
    if args.masked_input:
        return Path(args.masked_input).expanduser()
    raw = Prompt.ask("Path to masked validation dataset (for PMI text join)")
    return Path(raw).expanduser()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate multi-model validator verdicts and compute PMI artifact analysis "
            "as described in ViLegalNLI."
        )
    )
    parser.add_argument(
        "--verdicts-dir",
        help="Directory containing model verdict CSV/parquet files (e.g. gpt4o.csv).",
    )
    parser.add_argument(
        "--masked-input",
        help="Path to masked validation dataset for PMI text join.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for validation_votes.csv and pmi_consensus.csv. "
        "Defaults to --verdicts-dir.",
    )
    parser.add_argument(
        "--min-joint-count",
        type=int,
        default=3,
        help="Minimum joint token-label count included in PMI output. Default: 3.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for scripted runs.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress Rich output for tests or scripted runs.",
    )
    return parser


def _read_columns(path: Path) -> list[str]:
    if path.suffix.lower() == ".parquet":
        return list(pd.read_parquet(path, columns=[]).columns)
    return list(pd.read_csv(path, nrows=0).columns)


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


if __name__ == "__main__":
    raise SystemExit(main())

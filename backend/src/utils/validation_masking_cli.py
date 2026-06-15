import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.utils.validation_masking import write_masked_validation_dataset

DATASET_SUFFIXES = (".csv", ".parquet")
DEFAULT_SEARCH_DIRS = (
    Path("data/generated"),
    Path("data/processed"),
    Path("data/original"),
)


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
            columns = _read_columns(path)
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


def read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    console = Console(quiet=args.quiet)

    search_dirs = [Path(item) for item in args.search_dir] or list(DEFAULT_SEARCH_DIRS)
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

    columns = _read_columns(input_path)
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

    masked_columns = _read_columns(written_path)
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a validation dataset with label values removed."
    )
    parser.add_argument("--input", help="Input CSV/parquet dataset path.")
    parser.add_argument("--output", help="Output masked dataset path.")
    parser.add_argument(
        "--uid-column", help="UID column. Defaults to source_uid or uid."
    )
    parser.add_argument(
        "--label-column",
        default="label",
        help="Label column to remove. Default: label.",
    )
    parser.add_argument(
        "--search-dir",
        action="append",
        default=[],
        help="Directory to scan when --input is omitted. Can be repeated.",
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


if __name__ == "__main__":
    raise SystemExit(main())

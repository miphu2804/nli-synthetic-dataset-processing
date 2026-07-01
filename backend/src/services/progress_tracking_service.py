import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.schemas.generation_runtime_schema import (
    ActiveClaimSummary,
    ProgressVerificationResponse,
    RunProgressSnapshot,
)
from src.utils.project_paths import data_root, pipeline_root


@dataclass
class ActiveClaim:
    batch_id: str
    agent: str
    source_uids: list[str | int]


@dataclass
class RunState:
    done_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_claims: dict[str, ActiveClaim] = field(default_factory=dict)
    completed_batches: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_batches: dict[str, dict[str, Any]] = field(default_factory=dict)
    claim_count: int = 0


@dataclass
class _VerificationScan:
    """Raw findings collected in a single pass over a run's progress events, before they are judged into a verdict."""

    checked_agents: set[str] = field(default_factory=set)
    seen_done: dict[str, int] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)
    missing_batch_files: list[str] = field(default_factory=list)


class ProgressTrackingService:
    def __init__(self, pipeline_dir: Path | None = None) -> None:
        """Resolve the pipeline root and the data/ directory used for batch outputs."""
        self._pipeline_dir = (pipeline_dir or pipeline_root()).resolve()
        self._data_dir = self._derive_data_dir(self._pipeline_dir).resolve()

    def get_run_dir(self, run_id: str) -> Path:
        """Return the run's state directory under .pipeline/runs/{run_id}."""
        return self._pipeline_dir / "runs" / run_id

    def get_progress_path(self, run_id: str) -> Path:
        """Return the path to the run's append-only progress.jsonl log."""
        return self.get_run_dir(run_id) / "progress.jsonl"

    def get_outputs_dir(self, run_id: str) -> Path:
        """Return the run's batch outputs directory under data/batches/{run_id}."""
        return self._data_dir / "batches" / run_id

    def get_worker_artifacts_dir(self, run_id: str) -> Path:
        """Return the run's worker staging directory under the run state tree."""
        return self.get_run_dir(run_id) / "worker-artifacts"

    def resolve_output_file(self, run_id: str, file_name: str) -> Path:
        """Resolve a batch output file, preferring the current outputs dir and falling back to the legacy run/outputs location.

        Returns the current-location path even when neither exists, so callers can report it as missing.
        """
        output_path = self.get_outputs_dir(run_id) / file_name
        if output_path.exists():
            return output_path
        legacy_path = self.get_run_dir(run_id) / "outputs" / file_name
        if legacy_path.exists():
            return legacy_path
        return output_path

    def ensure_run_directories(self, run_id: str) -> None:
        """Create the run state directory and its batch outputs directory if they do not already exist."""
        run_dir = self.get_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self.get_outputs_dir(run_id).mkdir(parents=True, exist_ok=True)

    def ensure_worker_artifacts_dir(self, run_id: str) -> Path:
        """Create and return the run's worker-artifact staging directory."""
        self.ensure_run_directories(run_id)
        worker_artifacts_dir = self.get_worker_artifacts_dir(run_id)
        worker_artifacts_dir.mkdir(parents=True, exist_ok=True)
        return worker_artifacts_dir

    def cleanup_run(self, run_id: str) -> None:
        """Delete the run's state directory (.pipeline/runs/{run_id}) and everything under it."""
        shutil.rmtree(self.get_run_dir(run_id))

    def cleanup_outputs(self, run_id: str) -> None:
        """Delete the run's batch outputs directory if it exists."""
        outputs_dir = self.get_outputs_dir(run_id)
        if outputs_dir.exists():
            shutil.rmtree(outputs_dir)

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        """Read and parse all events from the run's progress.jsonl, returning an empty list when the log does not exist."""
        progress_path = self.get_progress_path(run_id)
        if not progress_path.exists():
            return []
        return [
            json.loads(line)
            for line in progress_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def append_event(
        self,
        run_id: str,
        agent: str,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an event to the run's progress log with a per-agent sequence id.

        Side effects: ensures run directories exist and writes one JSON line to progress.jsonl. Returns the written event.
        """
        self.ensure_run_directories(run_id)
        progress_path = self.get_progress_path(run_id)
        events = self.read_events(run_id)
        agent_events = [item for item in events if item["agent"] == agent]
        next_sequence = 0
        if agent_events:
            next_sequence = (
                max(self._extract_sequence(item["id"], agent) for item in agent_events)
                + 1
            )

        event_payload = {
            "id": f"{agent}-{next_sequence}",
            "event": event,
            "agent": agent,
        }
        if payload:
            event_payload.update(payload)
        serialized = json.dumps(
            event_payload, ensure_ascii=False, separators=(",", ":")
        )
        with progress_path.open("a", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
        return event_payload

    def build_run_state(self, run_id: str) -> RunState:
        """Replay the run's events into a RunState aggregating done/skipped rows, active claims, and completed/failed batches."""
        state = RunState()
        for event in self.read_events(run_id):
            event_type = event["event"]
            if event_type == "claim":
                state.claim_count += 1
                state.active_claims[event["batch_id"]] = ActiveClaim(
                    batch_id=event["batch_id"],
                    agent=event["agent"],
                    source_uids=event.get("source_uids", []),
                )
            elif event_type == "unclaim":
                state.active_claims.pop(event["batch_id"], None)
            elif event_type == "row.done":
                state.done_rows[self._uid_key(event["source_uid"])] = event
            elif event_type == "row.skip":
                state.skipped_rows[self._uid_key(event["source_uid"])] = event
            elif event_type == "batch.done":
                state.completed_batches[event["batch_id"]] = event
                state.active_claims.pop(event["batch_id"], None)
            elif event_type == "batch.fail":
                state.failed_batches[event["batch_id"]] = event
                state.active_claims.pop(event["batch_id"], None)
        return state

    def build_progress_snapshot(
        self,
        run_id: str,
        total_target_rows: int,
    ) -> RunProgressSnapshot:
        """Build a progress snapshot from the run state: done/skipped/claimed/pending row counts and active-claim summaries."""
        state = self.build_run_state(run_id)
        claimed_rows = sum(
            len(item.source_uids) for item in state.active_claims.values()
        )
        pending_rows = max(
            total_target_rows
            - len(state.done_rows)
            - len(state.skipped_rows)
            - claimed_rows,
            0,
        )
        return RunProgressSnapshot(
            run_id=run_id,
            total_target_rows=total_target_rows,
            done_rows=len(state.done_rows),
            skipped_rows=len(state.skipped_rows),
            claimed_rows=claimed_rows,
            pending_rows=pending_rows,
            completed_batches=len(state.completed_batches),
            failed_batches=len(state.failed_batches),
            active_claims=[
                ActiveClaimSummary(
                    batch_id=item.batch_id,
                    agent=item.agent,
                    source_uids=item.source_uids,
                )
                for item in state.active_claims.values()
            ],
        )

    def verify_progress_log(
        self,
        run_id: str,
        total_target_rows: int | None = None,
        agent_id: str | None = None,
        require_batch_files: bool = False,
    ) -> ProgressVerificationResponse:
        """Verify a run's progress log and return a verdict for duplicate/overlapping rows, missing batch files, and count mismatches.

        When agent_id is given only that agent's events are checked; total_target_rows enables the row-count ceiling check.
        """
        scan = self._scan_events(run_id, agent_id, require_batch_files)

        duplicate_done_source_uids = [
            uid for uid, count in scan.seen_done.items() if count > 1
        ]
        done_skip_overlap = [uid for uid in scan.seen_done if uid in scan.skipped]

        count_mismatches: list[str] = []
        if total_target_rows is not None:
            accounted_rows = len(set(scan.seen_done)) + len(
                scan.skipped - set(scan.seen_done)
            )
            if accounted_rows > total_target_rows:
                count_mismatches.append(
                    f"accounted_rows={accounted_rows} exceeds total_target_rows={total_target_rows}"
                )

        ok = not any(
            [
                duplicate_done_source_uids,
                done_skip_overlap,
                scan.missing_batch_files,
                count_mismatches,
            ]
        )
        return ProgressVerificationResponse(
            ok=ok,
            run_id=run_id,
            checked_agents=sorted(scan.checked_agents),
            duplicate_done_source_uids=duplicate_done_source_uids,
            done_skip_overlap_source_uids=done_skip_overlap,
            missing_batch_files=scan.missing_batch_files,
            count_mismatches=count_mismatches,
            active_claims=list(self.build_run_state(run_id).active_claims.keys()),
        )

    def _scan_events(
        self,
        run_id: str,
        agent_id: str | None,
        require_batch_files: bool,
    ) -> _VerificationScan:
        """Make one pass over the run's events collecting raw verification findings into a _VerificationScan.

        Tallies row.done/row.skip uids and, when require_batch_files is true,
        records batch.done files that are missing on disk. Events from other
        agents are skipped when agent_id is set.
        """
        scan = _VerificationScan()
        for event in self.read_events(run_id):
            current_agent = event["agent"]
            if agent_id and current_agent != agent_id:
                continue
            scan.checked_agents.add(current_agent)
            if event["event"] == "row.done":
                uid_key = self._uid_key(event["source_uid"])
                scan.seen_done[uid_key] = scan.seen_done.get(uid_key, 0) + 1
            if event["event"] == "row.skip":
                scan.skipped.add(self._uid_key(event["source_uid"]))
            if (
                require_batch_files
                and event["event"] == "batch.done"
                and event.get("file")
                and not self.resolve_output_file(run_id, event["file"]).exists()
            ):
                scan.missing_batch_files.append(event["file"])
        return scan

    @staticmethod
    def _extract_sequence(event_id: str, agent: str) -> int:
        """Parse the numeric sequence suffix from an '{agent}-{n}' event id; return -1 if it does not match the agent prefix."""
        prefix = f"{agent}-"
        if not event_id.startswith(prefix):
            return -1
        return int(event_id[len(prefix) :])

    @staticmethod
    def _uid_key(source_uid: str | int) -> str:
        """Return the normalized string key for a source_uid so int/str values compare consistently."""
        return str(source_uid)

    @staticmethod
    def _derive_data_dir(pipeline_dir: Path) -> Path:
        """Derive the data/ directory for batch artifacts."""
        if pipeline_dir.resolve() == pipeline_root().resolve():
            return data_root()
        candidates = [pipeline_dir, *pipeline_dir.parents]
        for path in candidates:
            if path.name == ".pipeline":
                return path.parent / "data"
        return Path("data")

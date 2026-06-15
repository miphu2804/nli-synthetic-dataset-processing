import hashlib
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


class ProgressTrackingService:
    def __init__(self, pipeline_dir: Path | None = None) -> None:
        self._pipeline_dir = (pipeline_dir or Path(".pipeline")).resolve()
        self._data_dir = self._derive_data_dir(self._pipeline_dir).resolve()

    def get_run_dir(self, run_id: str) -> Path:
        return self._pipeline_dir / "runs" / run_id

    def get_progress_path(self, run_id: str) -> Path:
        return self.get_run_dir(run_id) / "progress.jsonl"

    def get_outputs_dir(self, run_id: str) -> Path:
        return self._data_dir / "batches" / run_id

    def resolve_output_file(self, run_id: str, file_name: str) -> Path:
        output_path = self.get_outputs_dir(run_id) / file_name
        if output_path.exists():
            return output_path
        legacy_path = self.get_run_dir(run_id) / "outputs" / file_name
        if legacy_path.exists():
            return legacy_path
        return output_path

    def ensure_run_directories(self, run_id: str) -> None:
        run_dir = self.get_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self.get_outputs_dir(run_id).mkdir(parents=True, exist_ok=True)

    def cleanup_run(self, run_id: str) -> None:
        shutil.rmtree(self.get_run_dir(run_id))

    def cleanup_outputs(self, run_id: str) -> None:
        outputs_dir = self.get_outputs_dir(run_id)
        if outputs_dir.exists():
            shutil.rmtree(outputs_dir)

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
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
        self.ensure_run_directories(run_id)
        progress_path = self.get_progress_path(run_id)
        events = self.read_events(run_id)
        agent_events = [item for item in events if item["agent"] == agent]
        previous_hash = "0"
        next_sequence = 0
        if agent_events:
            previous_hash = self._event_hash(agent_events[-1])
            next_sequence = (
                max(self._extract_sequence(item["id"], agent) for item in agent_events)
                + 1
            )

        event_payload = {
            "id": f"{agent}-{next_sequence}",
            "event": event,
            "agent": agent,
            "prev_hash": previous_hash,
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
        events = self.read_events(run_id)
        previous_hashes: dict[str, str] = {}
        seen_done: dict[str, int] = {}
        skipped: set[str] = set()
        checked_agents: set[str] = set()
        broken_hashes: list[dict[str, Any]] = []
        missing_batch_files: list[str] = []
        count_mismatches: list[str] = []

        for event in events:
            current_agent = event["agent"]
            if agent_id and current_agent != agent_id:
                continue
            checked_agents.add(current_agent)
            expected_hash = previous_hashes.get(current_agent, "0")
            if event["prev_hash"] != expected_hash:
                broken_hashes.append(
                    {
                        "id": event["id"],
                        "agent": current_agent,
                        "expected_prev_hash": expected_hash,
                        "actual_prev_hash": event["prev_hash"],
                    }
                )
            previous_hashes[current_agent] = self._event_hash(event)
            if event["event"] == "row.done":
                uid_key = self._uid_key(event["source_uid"])
                seen_done[uid_key] = seen_done.get(uid_key, 0) + 1
            if event["event"] == "row.skip":
                skipped.add(self._uid_key(event["source_uid"]))
            if (
                require_batch_files
                and event["event"] == "batch.done"
                and event.get("file")
                and not self.resolve_output_file(run_id, event["file"]).exists()
            ):
                missing_batch_files.append(event["file"])

        duplicate_done_source_uids = [
            uid for uid, count in seen_done.items() if count > 1
        ]
        done_skip_overlap = [uid for uid in seen_done if uid in skipped]

        if total_target_rows is not None:
            accounted_rows = len(set(seen_done)) + len(skipped - set(seen_done))
            if accounted_rows > total_target_rows:
                count_mismatches.append(
                    f"accounted_rows={accounted_rows} exceeds total_target_rows={total_target_rows}"
                )

        ok = not any(
            [
                broken_hashes,
                duplicate_done_source_uids,
                done_skip_overlap,
                missing_batch_files,
                count_mismatches,
            ]
        )
        return ProgressVerificationResponse(
            ok=ok,
            run_id=run_id,
            checked_agents=sorted(checked_agents),
            broken_hashes=broken_hashes,
            duplicate_done_source_uids=duplicate_done_source_uids,
            done_skip_overlap_source_uids=done_skip_overlap,
            missing_batch_files=missing_batch_files,
            count_mismatches=count_mismatches,
            active_claims=list(self.build_run_state(run_id).active_claims.keys()),
        )

    @staticmethod
    def _extract_sequence(event_id: str, agent: str) -> int:
        prefix = f"{agent}-"
        if not event_id.startswith(prefix):
            return -1
        return int(event_id[len(prefix) :])

    @staticmethod
    def _event_hash(event: dict[str, Any]) -> str:
        serialized = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _uid_key(source_uid: str | int) -> str:
        return str(source_uid)

    @staticmethod
    def _derive_data_dir(pipeline_dir: Path) -> Path:
        candidates = [pipeline_dir, *pipeline_dir.parents]
        for path in candidates:
            if path.name == ".pipeline":
                return path.parent / "data"
        return Path("data")

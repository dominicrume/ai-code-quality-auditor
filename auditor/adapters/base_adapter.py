"""Base contract every AI workflow adapter implements."""
import json
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class BaseAdapter(ABC):
    name: str
    run_id: str
    raw_root: Path
    work_dir: Path

    # A class-level default, not just an annotation. The live adapters
    # (claude_code, cursor_agent) never set this — they have no replay
    # source — and an annotation alone creates no attribute, so
    # `self.replay_dir` in _persist raised AttributeError for exactly the
    # conditions the study captured live.
    replay_dir: Path | None = None

    def _persist(self, codebase, interaction_log, raw_events) -> Path:
        dest = self.raw_root / self.run_id / self.name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "codebase.json").write_text(json.dumps(codebase, indent=2))
        (dest / "interaction_log.json").write_text(json.dumps(interaction_log, indent=2))
        (dest / "raw_stream.json").write_text(json.dumps(raw_events, indent=2))
        code_copy = dest / "code"
        if code_copy.exists():
            shutil.rmtree(code_copy)
        source = self.replay_dir if self.replay_dir is not None else self.work_dir
        if source.exists():
            shutil.copytree(source, code_copy)
        return dest

    @abstractmethod
    def generate(self, spec: dict) -> tuple[dict, list[dict]]:
        """Return (codebase, interaction_log).

        codebase: {"files": {path: content}, "manifest": [feature_ids...]}
        interaction_log: list of events with at minimum a "type" key.
        """


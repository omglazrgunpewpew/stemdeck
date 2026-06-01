from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.models import Job


@dataclass
class SeparationResult:
    """What a separation backend hands back to the pipeline.

    stem_paths maps canonical STEM_NAMES to the WAV a backend produced for
    each (only the stems it actually emitted). cleanup_paths are intermediate
    files/dirs the backend left behind that collect() should remove after
    moving the stems into jobs/<id>/stems/ -- this is what keeps collect()
    ignorant of any backend's on-disk layout."""

    backend: str
    model: str
    stem_paths: dict[str, Path] = field(default_factory=dict)
    cleanup_paths: list[Path] = field(default_factory=list)


@runtime_checkable
class SeparationBackend(Protocol):
    """Shape every separation backend implements. separate() owns progress,
    cancellation, and subprocess registration via the job (see _set / set_proc
    in the Demucs backend).

    runtime_checkable so a backend's conformance can be asserted in tests
    (isinstance), keeping the contract enforced rather than purely advisory."""

    name: str
    model: str

    def separate(self, job: Job, source: Path, job_dir: Path) -> SeparationResult: ...

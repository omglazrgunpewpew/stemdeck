from __future__ import annotations

from pathlib import Path

from app.core import config
from app.core.models import Job
from app.pipeline.separators import KNOWN_SEPARATOR_BACKENDS, SeparationBackend, SeparationResult
from app.pipeline.separators.demucs import DemucsBackend


def _make_backend(name: str) -> SeparationBackend:
    """Resolve the configured backend name to an instance. Validated here (at
    job-separation time) rather than at import so a misconfigured
    STEMDECK_SEPARATOR_BACKEND doesn't stop the server from booting."""
    if name not in KNOWN_SEPARATOR_BACKENDS:
        raise RuntimeError(f"unknown separation backend: {name}")
    if name == "demucs":
        return DemucsBackend()
    # Unreachable while demucs is the only known backend, but keeps the
    # membership guard above honest if a name is added to the set without a
    # matching branch here.
    raise RuntimeError(f"no constructor wired for separation backend: {name}")


def separate(job: Job, source: Path, job_dir: Path) -> SeparationResult:
    """Dispatch separation to the configured backend (only demucs today)."""
    backend = _make_backend(config.SEPARATOR_BACKEND)
    return backend.separate(job, source, job_dir)

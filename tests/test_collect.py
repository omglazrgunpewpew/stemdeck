from __future__ import annotations

from pathlib import Path

import pytest

from app.core.models import Job
from app.pipeline.collect import collect
from app.pipeline.separators import SeparationResult


def _stem_file(d: Path, name: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.wav"
    p.write_bytes(b"RIFF")
    return p


def test_collect_moves_valid_stems_in_canonical_order(tmp_path: Path):
    job = Job(id="abcdefabcdef")
    job_dir = tmp_path / job.id
    src = job_dir / "raw"
    # Insertion order deliberately not canonical -- collect should reorder.
    result = SeparationResult(
        backend="demucs",
        model="htdemucs_6s",
        stem_paths={
            "drums": _stem_file(src, "drums"),
            "vocals": _stem_file(src, "vocals"),
            "bass": _stem_file(src, "bass"),
        },
    )

    found = collect(job, result, job_dir)

    assert found == ["vocals", "drums", "bass"]  # STEM_NAMES order
    for name in found:
        assert (job_dir / "stems" / f"{name}.wav").is_file()


def test_collect_ignores_unknown_stem_names(tmp_path: Path):
    job = Job(id="abcdefabcdef")
    job_dir = tmp_path / job.id
    src = job_dir / "raw"
    result = SeparationResult(
        backend="demucs",
        model="htdemucs_6s",
        stem_paths={
            "vocals": _stem_file(src, "vocals"),
            "kazoo": _stem_file(src, "kazoo"),
        },
    )

    found = collect(job, result, job_dir)

    assert found == ["vocals"]
    assert not (job_dir / "stems" / "kazoo.wav").exists()


def test_collect_raises_when_no_valid_stems(tmp_path: Path):
    job = Job(id="abcdefabcdef")
    job_dir = tmp_path / job.id
    job_dir.mkdir(parents=True)  # runner always creates job_dir before collect
    result = SeparationResult(backend="demucs", model="htdemucs_6s", stem_paths={})

    with pytest.raises(RuntimeError, match="no stems produced"):
        collect(job, result, job_dir)


def test_collect_removes_cleanup_paths(tmp_path: Path):
    job = Job(id="abcdefabcdef")
    job_dir = tmp_path / job.id
    src = job_dir / "htdemucs_6s"
    result = SeparationResult(
        backend="demucs",
        model="htdemucs_6s",
        stem_paths={"vocals": _stem_file(src, "vocals")},
        cleanup_paths=[src],
    )

    collect(job, result, job_dir)

    assert not src.exists()

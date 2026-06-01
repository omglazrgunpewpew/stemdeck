from __future__ import annotations

from pathlib import Path

import pytest

from app.core.models import Job, JobCancelled
from app.core.registry import _procs, get_proc
from app.pipeline import separate as separate_module
from app.pipeline.separators import SeparationBackend, SeparationResult
from app.pipeline.separators.demucs import DemucsBackend


@pytest.fixture(autouse=True)
def _isolate_procs():
    """The proc-cleanup tests touch the global registry _procs dict; isolate it
    so a stale entry from another module can't mask a regression here."""
    _procs.clear()
    yield
    _procs.clear()


# --- backend selection -------------------------------------------------------


def test_default_backend_selects_demucs(monkeypatch):
    monkeypatch.setattr(separate_module.config, "SEPARATOR_BACKEND", "demucs")
    backend = separate_module._make_backend(separate_module.config.SEPARATOR_BACKEND)
    assert isinstance(backend, DemucsBackend)
    assert backend.name == "demucs"


def test_explicit_demucs_backend_selects_demucs():
    assert isinstance(separate_module._make_backend("demucs"), DemucsBackend)


def test_unknown_backend_raises_clear_error():
    with pytest.raises(RuntimeError, match="unknown separation backend: bogus"):
        separate_module._make_backend("bogus")


def test_demucs_backend_satisfies_protocol():
    assert isinstance(DemucsBackend(model="htdemucs_6s", device="cpu"), SeparationBackend)


def test_separate_dispatches_to_backend_and_passes_through_result(tmp_path: Path, monkeypatch):
    """The dispatcher hands (job, source, job_dir) to the resolved backend and
    returns the backend's SeparationResult unchanged."""
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    sentinel = SeparationResult(backend="demucs", model="m", stem_paths={}, cleanup_paths=[])
    seen: dict = {}

    class _StubBackend:
        name = "demucs"
        model = "m"

        def separate(self, j, s, d):
            seen["args"] = (j, s, d)
            return sentinel

    def fake_make_backend(name):
        seen["name"] = name
        return _StubBackend()

    monkeypatch.setattr(separate_module, "_make_backend", fake_make_backend)
    monkeypatch.setattr(separate_module.config, "SEPARATOR_BACKEND", "demucs")

    result = separate_module.separate(job, source, tmp_path)

    assert result is sentinel
    assert seen["args"] == (job, source, tmp_path)
    assert seen["name"] == "demucs"  # dispatcher resolved the configured backend


# --- Demucs backend ----------------------------------------------------------


class _FakeStderr:
    def __init__(self, text: str) -> None:
        self._chars = list(text)

    def read(self, _n: int = 1) -> str:
        return self._chars.pop(0) if self._chars else ""


class _FakePopen:
    """Stand-in for subprocess.Popen that streams canned stderr and exits with
    a configurable return code without touching the real demucs CLI."""

    def __init__(self, cmd, *, stderr_text: str, returncode: int, sink: dict) -> None:
        self.args = cmd
        self.stderr = _FakeStderr(stderr_text)
        self._final = returncode
        self.returncode = None
        sink["cmd"] = cmd

    def poll(self):
        return self.returncode

    def wait(self):
        self.returncode = self._final
        return self.returncode

    def terminate(self):
        self.returncode = -15


def _patch_popen(monkeypatch, *, stderr_text: str, returncode: int) -> dict:
    sink: dict = {}

    def fake_popen(cmd, *_a, **_k):
        return _FakePopen(cmd, stderr_text=stderr_text, returncode=returncode, sink=sink)

    monkeypatch.setattr("app.pipeline.separators.demucs.subprocess.Popen", fake_popen)
    return sink


def _make_demucs_output(job_dir: Path, model: str, source: Path, stems: list[str]) -> None:
    out = job_dir / model / source.stem
    out.mkdir(parents=True)
    for name in stems:
        (out / f"{name}.wav").write_bytes(b"RIFF")


def test_demucs_command_uses_model_device_outdir_source(tmp_path: Path, monkeypatch):
    sink = _patch_popen(monkeypatch, stderr_text="100%\n", returncode=0)
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")
    _make_demucs_output(tmp_path, "htdemucs_6s", source, ["vocals", "drums"])

    backend = DemucsBackend(model="htdemucs_6s", device="cpu")
    backend.separate(job, source, tmp_path)

    cmd = sink["cmd"]
    assert "-n" in cmd and cmd[cmd.index("-n") + 1] == "htdemucs_6s"
    assert "-d" in cmd and cmd[cmd.index("-d") + 1] == "cpu"
    assert "-o" in cmd and cmd[cmd.index("-o") + 1] == str(tmp_path)
    assert cmd[-1] == str(source)


def test_demucs_success_returns_result_with_stem_and_cleanup_paths(tmp_path: Path, monkeypatch):
    _patch_popen(monkeypatch, stderr_text="50%\n100%\n", returncode=0)
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")
    _make_demucs_output(tmp_path, "htdemucs_6s", source, ["vocals", "drums", "bass"])

    backend = DemucsBackend(model="htdemucs_6s", device="cpu")
    result: SeparationResult = backend.separate(job, source, tmp_path)

    assert result.backend == "demucs"
    assert result.model == "htdemucs_6s"
    assert set(result.stem_paths) == {"vocals", "drums", "bass"}
    assert all(p.is_file() for p in result.stem_paths.values())
    assert result.cleanup_paths == [tmp_path / "htdemucs_6s"]


def test_demucs_nonzero_exit_raises_with_detail(tmp_path: Path, monkeypatch):
    _patch_popen(monkeypatch, stderr_text="CUDA out of memory\n", returncode=1)
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    backend = DemucsBackend(model="htdemucs_6s", device="cpu")
    with pytest.raises(RuntimeError, match="demucs failed: CUDA out of memory"):
        backend.separate(job, source, tmp_path)


def test_demucs_cancellation_raises_jobcancelled(tmp_path: Path, monkeypatch):
    _patch_popen(monkeypatch, stderr_text="10%\n", returncode=-15)
    job = Job(id="abcdefabcdef")
    job.cancel_requested = True
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    backend = DemucsBackend(model="htdemucs_6s", device="cpu")
    with pytest.raises(JobCancelled):
        backend.separate(job, source, tmp_path)


def test_demucs_clears_registered_proc_after_success(tmp_path: Path, monkeypatch):
    """Cancellation invariant: the proc must be deregistered once separation
    finishes, so a later POST /cancel never terminates a stale/reused handle."""
    _patch_popen(monkeypatch, stderr_text="100%\n", returncode=0)
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")
    _make_demucs_output(tmp_path, "htdemucs_6s", source, ["vocals"])

    DemucsBackend(model="htdemucs_6s", device="cpu").separate(job, source, tmp_path)

    assert get_proc(job.id) is None


def test_demucs_clears_registered_proc_after_failure(tmp_path: Path, monkeypatch):
    _patch_popen(monkeypatch, stderr_text="boom\n", returncode=1)
    job = Job(id="abcdefabcdef")
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    with pytest.raises(RuntimeError):
        DemucsBackend(model="htdemucs_6s", device="cpu").separate(job, source, tmp_path)

    assert get_proc(job.id) is None

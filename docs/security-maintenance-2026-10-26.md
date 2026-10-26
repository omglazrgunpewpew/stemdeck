# Dependency Security Maintenance

> ⚠ Verify before relying on: The Intel macOS graph still resolves torch 2.2.2, and `pip-audit` reports critical PYSEC-2025-41. The finding concerns `torch.load(..., weights_only=True)` and is fixed in torch 2.6.0. In the pinned `beat-this` 1.1.0 source, this mode is used for a local checkpoint path. Its normal fallback loads from a fixed HTTPS URL through `torch.hub.load_state_dict_from_url`, whose torch 2.2.2 default is `weights_only=False`. StemDeck has no request input for `STEMDECK_BEAT_MODEL`, but the deployment environment can override the checkpoint path. Confirm the override and local checkpoint remain controlled when assessing this residual. PyPI has no torch 2.6.0 macOS x86-64 wheel, so the current Intel build cannot take the patched release through a published wheel.

## Scope And Invariants

Update the compatible Python dependency floors and Rust lockfile while preserving Python >=3.11,<3.14, Intel macOS wheel constraints, Torch/Torchaudio behavior, desktop APIs, model licensing and all data and application behavior. The Intel macOS Torch finding remains a documented residual under the owner's direction to follow upstream's current platform policy. Work targets the personal fork only.

## Acceptance

Resolve patched versions without weakening security or platform constraints. Preserve declaration floors for code installed without the lockfile. Run required lint, formatting, backend tests and relevant desktop checks, or record exact unavailable commands and compensating remote gates. Freeze the final candidate with target and merge-base evidence, obtain fresh independent review, then satisfy remote checks and exact-head review before normal merge.

## Approved Compatibility Change

On October 26, the owner selected "Raise the minimum to Python 3.11 (Recommended)" after the resolver confirmed that the patched Pillow and Filelock releases require Python >=3.11. The supported range is now >=3.11,<3.14. Existing Python 3.12 build workflows and Intel macOS dependency constraints retain their contracts.

## Audit Findings

- Linux Python 3.11 and 3.12 graphs pass `pip-audit` with the exact 32 ignore entries from `.github/workflows/ci.yml`: no unignored findings, 24 findings ignored by existing policy in each graph.
- Intel macOS Python 3.11 and 3.12 graphs report torch 2.2.2 for PYSEC-2025-41, fixed in 2.6.0, and PYSEC-2024-259. The latter maps to disputed CVE-2024-48063 about `torch.distributed.rpc.RemoteModule`. No new ignore entries were added. See the [PyTorch advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6) and [PyTorch security policy](https://github.com/pytorch/pytorch/security/policy).
- Source review: `beat_this.inference.load_checkpoint` uses `torch.load(..., weights_only=True)` before its missing-file fallback. StemDeck supplies the environment setting `STEMDECK_BEAT_MODEL`, defaulting to `final0`, and no request input sets it. PyTorch 2.2.2's `torch.hub.load_state_dict_from_url` defaults to `weights_only=False`. The fixed fallback URL is `https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp`.
- Wheel availability: PyPI lists torch 2.6.0 macOS ARM64 wheels but no macOS x86-64 wheel. It lists torch 2.2.2 macOS x86-64 wheels. See [torch 2.6.0 files](https://pypi.org/project/torch/2.6.0/#files) and [torch 2.2.2 files](https://pypi.org/project/torch/2.2.2/#files).
- Canonical upstream main was inspected at `5f9405ca68ac31b31ae07ac416141d4d1f7b5f3a`. Its `pyproject.toml` retains Intel macOS Torch/Torchaudio 2.2.x and NumPy<2 constraints, its macOS runtime-pack script still accepts Python 3.10-3.13, and its CI ignore list does not suppress PYSEC-2025-41 or PYSEC-2024-259. This branch keeps the Intel platform policy and applies the owner-approved Python 3.11 minimum.
- The initial `pip-audit` dependency-resolution attempt for the Linux-target requirements file ran on Windows and could not resolve `nvidia-nccl-cu12==2.21.5`. The pinned Linux graph was then audited with `pip-audit --no-deps --disable-pip`, which passed with the existing policy. The Linux CI audit remains the full resolver gate.
- `cargo check --locked --manifest-path desktop/src-tauri/Cargo.toml` cannot complete on this host because the Visual Studio linker cannot find `msvcrt.lib` (LNK1104). `cargo fmt --check`, locked Cargo metadata, and `cargo tree -i rustls` provide local coverage. The Windows CI `rust-check` remains the build gate.

## Native CI Follow-Up

- The hosted Windows `rust-check` at candidate `e98c25709ffba75baa5a5249a85298ceb821036c` failed in `tauri-runtime-wry 2.11.4` with two distinct `ICoreWebView2Environment` types. The hosted Linux `check` failed in the same crate because its `available_monitors` and `primary_monitor` trait methods had return types inconsistent with the resolved `tauri-runtime`.
- The lockfile paired `tauri 2.11.1` and `tauri-runtime-wry 2.11.4` with `tauri-runtime 2.12.0`. The `tauri-runtime-wry 2.11.4` crate metadata requires `tauri-runtime ^2.11.3` and selects WebView2 0.38 and Windows 0.61. The `tauri-runtime 2.12.0` metadata selects WebView2 0.39 and Windows 0.62.
- The follow-up lock update aligns `tauri`, `tauri-runtime`, and `tauri-runtime-wry` at 2.12.0. Their resolved native backend now uses `tauri-runtime-wry 2.12.0`, `wry 0.57.1`, `tao 0.37.2`, WebView2 0.39.1, and Windows Core 0.62.2. This addresses the mismatched crate families shown in the hosted logs without changing application source or manifest APIs.
- Local validation for this follow-up: `cargo fetch --locked`, `cargo fmt --manifest-path desktop/src-tauri/Cargo.toml --check`, locked metadata, and inverse dependency trees pass. A local native compile remains unavailable because `msvcrt.lib` is missing. The hosted Linux Rust check and Windows `rust-check` passed on dependency candidate `eff380151a3c11ac3335161356340e1e21ab060d`. The platform-specific macOS and Windows check workflows still need passing results on the runner-selection candidate.

## Fork Native Runner Follow-Up

- The native macOS and Windows check workflows on dependency candidate `eff380151a3c11ac3335161356340e1e21ab060d` remained queued because the personal fork has no registered self-hosted runners, confirmed by the GitHub runner API.
- Both native check workflows now select GitHub-hosted runners only when `github.repository` is `omglazrgunpewpew/stemdeck`: `macos-latest` for macOS ARM64 and `windows-latest` for Windows x64. The canonical repository retains the original self-hosted runner label arrays, the existing pull-request guard, empty token permissions, commands, and workflow triggers.
- GitHub's [hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) documents `macos-latest` as ARM64 and `windows-latest` as x64. This fallback runs build and check commands only. It does not sign, package, or upload releases.
- The workflow change requires fresh hosted `macos-check` and `windows-check` results on its exact candidate before merge. Existing dependency-candidate results do not validate these runner-selection edits.

## Validation

- `uv lock --check`: passed.
- `uv tool run --from ruff ruff check app/ tests/`: passed.
- `uv tool run --from ruff ruff format --check app/ tests/`: passed.
- `bash -n scripts/macos/make-runtime-pack.sh`: passed.
- `.venv/Scripts/pytest.exe tests/ -q --color=no` on Python 3.12: 1098 passed, 3 skipped, 4 warnings.
- `cargo fmt --manifest-path desktop/src-tauri/Cargo.toml --check`: passed.
- `cargo metadata --locked --manifest-path desktop/src-tauri/Cargo.toml --no-deps --format-version 1`: passed.
- `cargo tree --locked --manifest-path desktop/src-tauri/Cargo.toml -i rustls`: confirms rustls 0.23.46.

The macOS runtime builder rejects Python 3.13 for Intel builds because the retained Torch, torchaudio and NumPy lines publish Intel wheels only through Python 3.12. Apple Silicon keeps Python 3.13 support. This matches the existing dependency constraints.

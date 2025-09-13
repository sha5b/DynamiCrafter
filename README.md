<!--
File: README.md
Purpose: Minimal quick-start installation using uv for this fork. Torch is installed via a dedicated script to match your CUDA.
Connected to: `pyproject.toml` (uv-managed deps), `scripts/install_torch.py` (PyTorch installer), `uv.lock` (resolved versions), runtime entry points like `gradio_app.py` and `scripts/*`.
-->

# DynamiCrafter — Quick Install with uv

This fork is configured for uv-managed environments. Core Python dependencies are declared in `pyproject.toml` and locked in `uv.lock`. PyTorch/XFormers are intentionally excluded and must be installed with the provided helper script to match your system (CUDA or CPU).

For usage guides, models, training, and examples, see the upstream documentation:
- Upstream repo: https://github.com/Doubiiu/DynamiCrafter

## Prerequisites
- Windows 10/11
- NVIDIA GPU + recent driver for CUDA builds (optional)
- uv package manager installed (https://docs.astral.sh/uv/)

## 1) Create and sync the environment
From the repo root:

```powershell
# Ensure the exact interpreter required by this project is available
uv python install 3.8.5

# Create/sync the project environment from pyproject.toml and uv.lock
uv sync --frozen
```

Notes:
- The project pins Python to 3.8.5 via `pyproject.toml`.
- `uv sync --frozen` uses `uv.lock` for fully reproducible versions.

## 2) Install PyTorch (CUDA or CPU)
Use the helper script to detect CUDA and install matching wheels. You can also force a tag:

```powershell
# Auto-detect CUDA and install torch/torchvision/torchaudio with fallbacks
uv run --no-sync python scripts/install_torch.py

# Optional: force a specific wheel tag (cu118 | cu121 | cpu)
uv run --no-sync python scripts/install_torch.py --tag cu118

# Optional: clean reinstall or install MSVC runtime if needed on Windows
uv run --no-sync python scripts/install_torch.py --reinstall --install-vcredist
```

Tips:
- Use `--no-sync` with `uv run` so uv does not attempt to re-resolve/replace CUDA wheels.
- The script pins versions known to work on Python 3.8 by default and verifies CUDA availability after install.

## 3) Verify installation
```powershell
uv run --no-sync python -c "import torch, torch.cuda as c; print('torch', torch.__version__, 'cuda', torch.version.cuda, 'available', c.is_available())"
```

If `available` is `True` and a CUDA version is shown, your GPU build is working. Otherwise, the CPU build is in use.

## Next steps
- For inference, training, and demos, follow the instructions in the upstream README: https://github.com/Doubiiu/DynamiCrafter
- Launch commands (examples) will work when run via `uv run --no-sync ...` using this environment.

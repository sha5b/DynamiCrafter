"""
File: scripts/install_torch.py
Purpose: Detect CUDA automatically and install matching PyTorch wheels (CUDA or CPU) for DynamiCrafter's venv.
Connected to: Run directly via the venv Python, e.g. .\.venv\Scripts\python scripts\install_torch.py --reinstall

Notes:
- This script prefers CUDA 11.8 wheels and pins versions known to work on Python 3.8.5 by default:
  torch==2.0.0, torchvision==0.15.1, torchaudio==2.0.1
- Falls back across tags: cu121 -> cu118 -> cpu (or cu118 -> cpu), based on detection.
- If you prefer different versions, override with --torch-version/--torchvision-version/--torchaudio-version.
- After install, it verifies CUDA availability and prints diagnostics.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()


def detect_cuda_version() -> Optional[Tuple[int, int]]:
    """Return (major, minor) if CUDA is detected via nvidia-smi, else None."""
    nvsmi = shutil.which("nvidia-smi") or os.environ.get("NVIDIA_SMI") or os.environ.get("NVSMI_PATH")
    if not nvsmi:
        return None
    code, out, _ = run([nvsmi])
    if code != 0:
        return None
    m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", out)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def map_cuda_to_tag(ver: Optional[Tuple[int, int]]) -> str:
    """Map CUDA version to PyTorch wheel tag ('cu122','cu121','cu118','cpu')."""
    if ver is None:
        return "cpu"
    major, minor = ver
    if major >= 12:
        return "cu121"
    if major == 11:
        return "cu118"
    return "cpu"


def index_url_for_tag(tag: str) -> str:
    return "https://download.pytorch.org/whl/cpu" if tag == "cpu" else f"https://download.pytorch.org/whl/{tag}"


def check_nvcuda() -> tuple[bool, str]:
    try:
        import ctypes  # noqa: F401
        ctypes.WinDLL("nvcuda.dll")
        return True, "nvcuda.dll load: OK"
    except Exception as e:
        return False, f"nvcuda.dll load: FAIL: {e}"


VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


def check_vcredist() -> tuple[bool, str]:
    try:
        import ctypes  # noqa: F401
        try:
            ctypes.WinDLL("vcruntime140_1.dll")
            return True, "MSVC runtime: vcruntime140_1.dll load OK"
        except Exception:
            ctypes.WinDLL("vcruntime140.dll")
            ctypes.WinDLL("msvcp140.dll")
            return True, "MSVC runtime: vcruntime140/msvcp140 load OK"
    except Exception as e:
        return False, f"MSVC runtime load: FAIL: {e}"


def ensure_pip_available() -> None:
    print("Ensuring pip is available (using ensurepip)…")
    code, out, err = run([sys.executable, "-m", "ensurepip", "--upgrade"])
    if out:
        print(out)
    if code != 0 and err:
        print(err, file=sys.stderr)
    code, out, err = run([sys.executable, "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"])
    if out:
        print(out)
    if code != 0 and err:
        print(err, file=sys.stderr)


def current_torch_summary() -> Tuple[Optional[str], Optional[str]]:
    try:
        import importlib.metadata as md
        version = md.version("torch")
    except Exception:
        version = None
    cuda = None
    try:
        import torch  # type: ignore
        cuda = getattr(torch.version, "cuda", None)
    except Exception:
        pass
    return version, cuda


def uninstall_torch() -> int:
    cmd = [sys.executable, "-m", "pip", "uninstall", "-y", "torch", "torchvision", "torchaudio"]
    print("Uninstalling existing PyTorch packages if present…")
    code, out, err = run(cmd)
    print(out)
    if code != 0 and "not installed" not in (out + err).lower():
        print(err, file=sys.stderr)
    return 0


def install_torch(tag: str, tv: Optional[str], ttv: Optional[str], tau: Optional[str]) -> int:
    url = index_url_for_tag(tag)
    pkgs: list[str] = []
    pkgs.append(f"torch=={tv}" if tv else "torch")
    pkgs.append(f"torchvision=={ttv}" if ttv else "torchvision")
    pkgs.append(f"torchaudio=={tau}" if tau else "torchaudio")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *pkgs, "--index-url", url]
    print("Installing PyTorch with:", " ".join(cmd))
    code, out, err = run(cmd)
    print(out)
    if code != 0:
        print(err, file=sys.stderr)
    return code


def try_install_with_fallbacks(primary_tag: str, tv: Optional[str], ttv: Optional[str], tau: Optional[str]) -> tuple[bool, str]:
    if primary_tag == "cu122":
        candidates = ["cu122", "cu121", "cu118", "cpu"]
    elif primary_tag == "cu121":
        candidates = ["cu121", "cu118", "cpu"]
    elif primary_tag == "cu118":
        candidates = ["cu118", "cpu"]
    else:
        candidates = ["cpu"]
    last = "cpu"
    for tag in candidates:
        last = tag
        code = install_torch(tag, tv, ttv, tau)
        if code == 0:
            return True, tag
        print(f"Install failed for tag={tag}. Trying next fallback…")
    return False, last


def verify_torch(expect_cuda: bool) -> tuple[bool, str]:
    try:
        import torch as t  # type: ignore
        import torch.cuda as tc  # type: ignore
    except Exception as e:
        return False, f"Failed to import torch/torch.cuda: {e}"

    # Help Windows locate dependent DLLs
    try:
        torclib = Path(t.__file__).parent / "lib"
        if torclib.exists() and hasattr(os, "add_dll_directory") and os.name == "nt":
            os.add_dll_directory(str(torclib))
    except Exception:
        pass

    ver = getattr(t, "__version__", "?")
    cuda_ver = getattr(getattr(t, "version", object()), "cuda", None)
    ok = tc.is_available()
    dev = None
    if ok:
        try:
            dev = tc.get_device_name(0)
        except Exception:
            dev = "(unavailable)"

    report = (
        "Verification:\n"
        f"  torch={ver} path={getattr(t, '__file__', '?')}\n"
        f"  torch.version.cuda={cuda_ver} cuda_available={ok}\n"
        f"  device={dev}"
    )
    if expect_cuda:
        return (cuda_ver is not None) and ok, report
    else:
        return (cuda_ver is None) and (not ok), report


def main() -> None:
    parser = argparse.ArgumentParser(description="Install PyTorch with correct CUDA wheels for DynamiCrafter")
    parser.add_argument("--tag", choices=["cpu", "cu118", "cu121", "cu122"], help="Override detected wheel tag")
    parser.add_argument("--reinstall", action="store_true", help="Uninstall any existing torch/vision/audio first")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be installed, do not execute")
    parser.add_argument("--install-vcredist", action="store_true", help="Install MSVC 2015–2022 (x64) if missing")
    parser.add_argument("--torch-version", dest="tv", help="Override torch version (default: 2.0.0 for Python 3.8)")
    parser.add_argument("--torchvision-version", dest="ttv", help="Override torchvision version (default: 0.15.1 for Python 3.8)")
    parser.add_argument("--torchaudio-version", dest="tau", help="Override torchaudio version (default: 2.0.1 for Python 3.8)")
    args = parser.parse_args()

    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version.splitlines()[0]}")

    # Default versions for Python 3.8 (DynamiCrafter reference env)
    tv = args.tv
    ttv = args.ttv
    tau = args.tau
    if sys.version_info < (3, 9):
        tv = tv or "2.0.0"
        ttv = ttv or "0.15.1"
        tau = tau or "2.0.1"

    ensure_pip_available()

    if args.reinstall:
        uninstall_torch()

    print("Detecting CUDA with nvidia-smi…")
    ver = detect_cuda_version()
    if ver:
        print(f"Detected CUDA Version: {ver[0]}.{ver[1]}")
    else:
        print("No CUDA detected or nvidia-smi unavailable. Defaulting to CPU wheels.")

    auto_tag = map_cuda_to_tag(ver)
    tag = args.tag or auto_tag
    print(f"Resolved wheel tag: {tag} (auto={auto_tag})")

    ok_vc, msg_vc = check_vcredist()
    print(msg_vc)
    if not ok_vc and args.install_vcredist:
        print("Attempting to install Microsoft Visual C++ 2015–2022 (x64) Redistributable silently…")
        try:
            tmpdir = tempfile.mkdtemp(prefix="torch_vc_")
            exe_path = os.path.join(tmpdir, "vc_redist.x64.exe")
            print(f"Downloading MSVC redistributable from {VC_REDIST_URL} …")
            urllib.request.urlretrieve(VC_REDIST_URL, exe_path)
            print(f"Saved to {exe_path}")
            code, out, err = run([exe_path, "/quiet", "/norestart"])
            if out:
                print(out)
            if code != 0 and err:
                print(err, file=sys.stderr)
        except Exception as e:
            print(f"Failed to install MSVC redistributable: {e}")

    if args.dry_run:
        print("Dry run: skipping installation.")
        return

    ok, used = try_install_with_fallbacks(tag, tv, ttv, tau)
    if ok:
        print(f"PyTorch installation succeeded using tag={used}.")
        expect_cuda = used.startswith("cu")
        v_ok, v_report = verify_torch(expect_cuda)
        print(v_report)
        if not v_ok and expect_cuda:
            ok_nv, msg_nv = check_nvcuda()
            print(msg_nv)
            print(
                "If CUDA is still unavailable, check: 1) NVIDIA driver installed and up-to-date, "
                "2) MSVC 2015–2022 (x64) Redistributable installed."
            )
        print("Tip: Launch using .\\.venv\\Scripts\\python or 'uv run --no-sync' to avoid uv replacing CUDA wheels.")
    else:
        print("PyTorch installation failed after trying all fallbacks.")
        sys.exit(1)


if __name__ == "__main__":
    main()

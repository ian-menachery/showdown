"""Build and run the postflop-solver bridge as a separate process (DECISIONS 29, 38, 40)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRIDGE_DIR = ROOT / "bridges" / "postflop"
EXTERNAL = ROOT / "data" / "external" / "postflop-solver"
SOLVER_DIR = EXTERNAL / "solver"
TARGET_DIR = EXTERNAL / "target"
EXE = TARGET_DIR / "release" / "showdown-postflop-bridge.exe"
SOLVER_COMMIT = "9d1509fe5077d019825f833eed04b16d342dfda1"
TOOLCHAIN = "1.100.0-x86_64-pc-windows-gnu"
CARGO_BIN = Path.home() / ".cargo" / "bin"
RUSTFLAGS = "-A dangerous_implicit_autorefs"
"""Rust 1.100 denies this lint, which the 2023 solver trips; Ian chose to allow it (Gate S4)."""


class BridgeError(RuntimeError):
    """The bridge is missing, failed, or timed out."""


def build() -> Path:
    """Build the bridge with the pinned toolchain against the pinned solver checkout."""
    if not SOLVER_DIR.is_dir():
        raise BridgeError(
            f"{SOLVER_DIR} is missing: clone b-inary/postflop-solver there at {SOLVER_COMMIT}"
        )
    head = subprocess.run(
        ["git", "-C", str(SOLVER_DIR), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if head != SOLVER_COMMIT:
        raise BridgeError(f"the solver checkout is at {head or '?'}, not {SOLVER_COMMIT}")
    cargo = CARGO_BIN / ("cargo.exe" if os.name == "nt" else "cargo")
    if not cargo.exists():
        raise BridgeError(f"{cargo} is missing: install Rust {TOOLCHAIN} (DECISIONS 38)")
    env = {
        **os.environ,
        "PATH": f"{CARGO_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
        "RUSTFLAGS": RUSTFLAGS,
    }
    command = [str(cargo), f"+{TOOLCHAIN}", "build", "--release", "--quiet"]
    command += ["--target-dir", str(TARGET_DIR)]
    proc = subprocess.run(command, cwd=BRIDGE_DIR, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not EXE.exists():
        raise BridgeError("cargo build failed:\n" + proc.stderr[-2000:])
    return EXE


def binary_sha256() -> str:
    if not EXE.exists():
        raise BridgeError(f"{EXE} is missing: run `showdown postflop build`")
    return hashlib.sha256(EXE.read_bytes()).hexdigest()


def solve(spec: dict, *, timeout: float = 1800.0, cache: Path | None = None) -> dict:
    """Run one solve. With `cache`, reuse a result for the same spec and the same binary."""
    key = None
    if cache is not None:
        text = json.dumps(spec, sort_keys=True) + binary_sha256()
        key = cache / (hashlib.sha256(text.encode()).hexdigest() + ".json")
        if key.exists():
            return json.loads(key.read_text(encoding="utf-8"))
    if not EXE.exists():
        raise BridgeError(f"{EXE} is missing: run `showdown postflop build`")
    try:
        proc = subprocess.run(
            [str(EXE)], input=json.dumps(spec), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as error:
        raise BridgeError(f"the solve took longer than {timeout:g} s") from error
    if proc.returncode != 0:
        raise BridgeError("the bridge failed:\n" + proc.stderr[-2000:])
    result = json.loads(proc.stdout)
    if key is not None:
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text(json.dumps(result), encoding="utf-8")
    return result

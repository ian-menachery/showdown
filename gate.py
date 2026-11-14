#!/usr/bin/env python3
"""The definition of done. If this exits zero, stop working.

Stdlib only, no make, no shell (make is not installed on this machine). Run it
with plain `py gate.py`: when the repo-local .venv exists, every tool runs under
that interpreter, so the dependencies do not have to be installed globally
(DECISIONS 10).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
PY = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command at the repo root, capturing output, never raising."""
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def _output(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout + proc.stderr).strip()


def ruff_check() -> tuple[bool, str]:
    proc = _run([PY, "-m", "ruff", "check", "src", "tests"])
    return proc.returncode == 0, _output(proc)


def ruff_format() -> tuple[bool, str]:
    proc = _run([PY, "-m", "ruff", "format", "--check", "src", "tests"])
    return proc.returncode == 0, _output(proc)


def pytest_with_coverage() -> tuple[bool, str]:
    """Tests plus the coverage floor.

    The floor lives in pyproject's `fail_under`, so pytest's exit code already
    carries it. `-rs` prints skip reasons: a skipped oracle test never counts
    toward a gate pass (DECISIONS 6).
    """
    proc = _run([PY, "-m", "pytest", "-rs", "--cov=showdown", "--cov-report=term-missing"])
    return proc.returncode == 0, _output(proc)


def clean_tree() -> tuple[bool, str]:
    """Fails on uncommitted changes, or if HEAD has not been pushed."""
    status = _run(["git", "status", "--porcelain"])
    if status.returncode != 0:
        return False, _output(status)
    if status.stdout.strip():
        return False, "working tree is dirty. Commit or stash:\n" + status.stdout.rstrip()

    fetch = _run(["git", "fetch", "origin"])
    if fetch.returncode != 0:
        return False, "git fetch origin failed:\n" + _output(fetch)

    head = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if head.returncode != 0:
        return False, "could not determine the current branch:\n" + _output(head)
    branch = head.stdout.strip()

    ahead = _run(["git", "log", f"origin/{branch}..HEAD", "--oneline"])
    if ahead.returncode != 0:
        return False, f"could not compare HEAD against origin/{branch}:\n" + _output(ahead)
    if ahead.stdout.strip():
        return False, (
            f"HEAD is ahead of origin/{branch}. Push before claiming done:\n"
            + ahead.stdout.rstrip()
        )

    return True, ""


TARGETS = (
    ("ruff check src tests", ruff_check),
    ("ruff format --check src tests", ruff_format),
    ("pytest --cov=showdown (floor 80%)", pytest_with_coverage),
    ("clean-tree", clean_tree),
)


def main() -> int:
    print(f"python: {PY}")
    for name, target in TARGETS:
        ok, detail = target()
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            if detail:
                print()
                for line in detail.splitlines():
                    print(f"      {line}")
            print()
            print(f"GATE FAIL at: {name}")
            return 1

    print()
    print("GATE PASS. Stop here. New ideas go in SCOPE's Open questions or an amendment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

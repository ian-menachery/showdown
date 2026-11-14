"""Phase 0 smoke test: the package and its two pinned runtime deps import."""

import importlib


def test_package_imports() -> None:
    import showdown

    assert showdown.__version__


def test_runtime_dependencies_import() -> None:
    for name in ("pokerkit", "eval7"):
        assert importlib.import_module(name)

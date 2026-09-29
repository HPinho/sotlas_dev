#!/usr/bin/env python3
"""Canonical Sotlas LSP entrypoint.

The language server implementation historically imports ``bootstrap`` as a
standalone module. Install the same target-profile contract used by the
production compiler before loading that implementation so IDE diagnostics,
project discovery and the compiler agree on ``target``/``barecore`` syntax.
"""
from __future__ import annotations

from pathlib import Path
import sys

_SOTLAS_COMPILE_DIR = str(Path(__file__).resolve().parent)
if _SOTLAS_COMPILE_DIR not in sys.path:
    sys.path.insert(0, _SOTLAS_COMPILE_DIR)

try:
    from . import bootstrap as _bootstrap
    from .target_profile import install as _install_target_profile
except ImportError:
    import bootstrap as _bootstrap
    from target_profile import install as _install_target_profile

_install_target_profile(_bootstrap)
# The implementation retains its standalone ``from bootstrap import ...``
# contract. Pin that name to the already configured module before importing it.
sys.modules["bootstrap"] = _bootstrap

try:
    from ._lsp_server import *  # noqa: F401,F403
except ImportError:
    from _lsp_server import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())

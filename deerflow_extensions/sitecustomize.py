"""
sitecustomize.py — Auto-loaded by CPython at startup (dev mode only).

Ensures deerflow_extensions is on sys.path and applies all
TopicGuardrail patches via patch_manager.apply_all().

NOTE: Uses "deerflow_extensions.patch_manager" (not bare "patch_manager")
to share the same sys.modules key with app.py's injection block,
so _APPLIED idempotency guard works across both call sites.
"""

import sys as _sys
import os as _os

_my_dir = _os.path.dirname(_os.path.realpath(__file__))
_parent = _os.path.dirname(_my_dir)
if _parent not in _sys.path:
    _sys.path.insert(0, _parent)

from deerflow_extensions.patch_manager import apply_all
apply_all()

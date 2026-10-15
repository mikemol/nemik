"""nemik:W518: the architecture's read-only claims name the `store` module, not any name ending in it.

nemik.cachestore keeps the build's own caches (never a queue) and its load()/save() tripped two claims
that grep for `store.load(` and `store.save(` as substrings. The claims now match the module; these hold
them to still catching the real thing.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
LOAD = re.compile(r"(?<![A-Za-z0-9_])store\.load\s?\(")


def _claims() -> ModuleType:
    """checks/claims.py, which is a script and not a package."""
    spec = importlib.util.spec_from_file_location(
        "claims", ROOT / "checks" / "claims.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_real_store_module_is_still_caught() -> None:
    assert LOAD.search("data = store.load(path)")
    assert LOAD.search("mikemol.pathsforward.store.load (path)")
    assert LOAD.search("x = (store.load(p))")


def test_a_name_ending_in_store_is_not_the_store_module() -> None:
    assert not LOAD.search("cachestore.load(directory)")
    assert not LOAD.search("datastore.load(x)")


def test_the_claims_hold_on_the_current_source() -> None:
    claims = _claims()
    claims.single_writer_boundary()
    claims.nemik_never_writes_a_queue()

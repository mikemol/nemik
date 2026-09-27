import os
import shutil

import pytest

from nemik.witnesses import witness

pytestmark = pytest.mark.skipif(shutil.which("opa") is None, reason="opa not installed")


def test_file_witness_true_false(tmp_path) -> None:
    p = tmp_path / "flag"
    q = f'input.file["{p}"].exists'
    assert witness(q)[0] == "false"
    p.write_text("")
    verdict, doc, _ = witness(q)
    assert verdict == "true"
    assert doc["file"][str(p)] == {"exists": True}


def test_pid_witness_sees_live_and_gone() -> None:
    live = f'not input.pid["localhost/{os.getpid()}"].alive'
    assert witness(live)[0] == "false"
    assert witness('not input.pid["localhost/999999999"].alive')[0] == "true"


def test_pid_reuse_guard_treats_other_starttime_as_gone() -> None:
    assert witness(f'not input.pid["localhost/{os.getpid()}@1"].alive')[0] == "true"


def test_unobservable_fact_is_undefined_not_false() -> None:
    verdict, _, missing = witness('not input.pid["otherhost/1"].alive')
    assert verdict == "undefined" and missing == ['pid["otherhost/1"]']
    assert witness('input.nosuch["x"].ok')[0] == "undefined"

"""nemik:W157/W113: the operator's calendars, read host-side as event occurrences.

For each configured collection the KF6 Akonadi helper (W147) exports one .ics into a private temp
directory (0700, the file 0600); mtools' `mikemol-ics` (W157 step 1, lossless) expands it to
per-occurrence records over a window; the file is deleted before returning. The Google credential
never leaves KWallet, the event text never goes to the export, metrics or nemik-serve (operator
2026-09-28), and nothing here prints an event.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from nemik.vtodo import DEFAULT_HELPER

KEEP = ("uid", "start", "end", "all_day", "summary", "recurrence_id")


def occurrences(collections: dict[str, str], *, start: str, window: str = "14d",
                helper: Path = DEFAULT_HELPER, ics: str = "mikemol-ics") -> list[dict]:
    """[{label, uid, start, end, all_day, summary, recurrence_id}] for every collection, by start.

    `collections` maps a short label (what waypoints cite as cal:<label>/<uid>) to the Akonadi
    collection name. A collection that fails to export or parse raises: a silent gap would read as
    a free day.
    """
    tmp = Path(tempfile.mkdtemp(prefix="nemik-cal-"))  # mkdtemp is 0700
    try:
        out: list[dict] = []
        for label, name in sorted(collections.items()):
            f = tmp / f"{label}.ics"
            subprocess.run([str(helper), "--export-calendar", name, "--out", str(f)],
                           check=True, capture_output=True)
            text = subprocess.run([ics, "--from", start, "--window", window, "--json", str(f)],
                                  check=True, capture_output=True, text=True).stdout
            for line in text.splitlines():
                rec = json.loads(line)
                if rec.get("kind") == "occurrence":
                    out.append({"label": label, **{k: rec.get(k) for k in KEEP}})
            f.unlink()
        return sorted(out, key=lambda r: (r["start"] or "", r["label"], r["uid"] or ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

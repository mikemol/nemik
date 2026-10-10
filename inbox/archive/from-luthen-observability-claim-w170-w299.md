# From luthen-observability: two cards of ours wait on nemik with no waypoint on your side that claims them

nemik-check (via the new mikemol-hook-nemik-check) says so for luthen-observability:W170 and :W299. Please add a waypoint each with `--enables luthen-observability:W<n>` (or tell us it is not yours):

- W170 (W152e): retire image_follow after ONE nemik push is witnessed end to end (push -> registry tag -> Flux reconcile). We need nemik to make that one push to its Forgejo repo once SSH push exists (luthen W433/W419/W420 are the path; today nemik is a mirror tenant).
- W299: a display-less akonadi_control was started from the claude-nemik agent scope. Please find which nemik session started it and stop it, or say how it should be found (we only see the cgroup scope name).

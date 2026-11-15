# Builder memory: what holds it and what the pod reads

Where the nemik builder's memory goes, measured, with the levers left. Every figure carries its
source; nothing here is a model. The card is nemik:W1096.

## The trace (host, 2026-10-26)

The Model rebuild's resident set was 770 MiB against a merged graph of about 396 MiB (rdflib, 1226
bytes per triple, 338,778 triples). An allocation trace (tracemalloc, the survey alone over the
pod's export) found 192.5 MiB live after the survey and 386 MiB resident: about 150 MiB of the gap
is allocator fragmentation, not live data. Live: rdflib's in-memory store 130.0 MiB (the spo, pos
and osp index dicts), terms 24.7 MiB, graph.py 21.5 MiB, shaclinc 8.4 MiB (the frozenset kept for
the next incremental run), JSON decode 3.7 MiB.

The holder of a graph that outlived the survey was `adapter._PARSED`, the parse cache, which keeps
the pristine graph per (kind, repo) and hands out a copy per call. A publish parses each file once
and never asks again, so there it was only a second copy. `forget_parsed` (landed 280f450) made a
publish build keep none: process peak 1049.9 to 737.1 MiB on the host (-312.8 MiB, -30 percent),
cgroup peak 1G to 769.8M.

## What the pod reads (2026-11-15T01:50Z, luthen-observability W2655; unverified here)

Image nemik-55b6fcf696, pods 2qd72 and gtb97, builder limit 2304 MiB:

| series | reading |
|---|---|
| nemik_build_peak_rss_bytes now | 1037.6 and 1244.6 MiB (cache_hit=1) |
| over 1 d, max | 1253.6 MiB (hit), 1175.8 MiB (miss) |
| over 1 d, median of per-pod medians | 1074.9 MiB (hit), 1096.0 MiB (miss) |
| builder working-set max, 1 d | 1175.3 and 1193.0 MiB |
| server container | 16.9 MiB of 96 MiB |

Headroom against the largest peak is about 1050 MiB, 46 percent of the limit. Caveats: the sample is
thin (about five runs on this image), the peak gauge is held between scrapes so quantiles weight by
dwell time, and there is no memory.peak series (the working set can miss a short peak: the RSS gauge,
1244.6, is above the working-set max, 1193.0). The old image's pod peak was 1.30 to 1.34 GB, so
the peak fell by about 0.05 to 0.09 GB; this is not the host's 30 percent.

## The levers left, by size

1. The Activity triples (nemik:W1095): about 196 MiB of the graph. Consumers that now read plain
   ledger rows: blocks (when handed the summary), metrics, history, idle. Still on the triples:
   serve (W2199, W2200) and trs (W2202). When they move, the triples need not be built.
2. The survey's merged graph and the Model's own merge, both alive while the Model builds.
3. pyshacl's clone of the data graph per validation (the transient peak: three copies of the queue
   graph plus the clone).
4. A store swap (pyoxigraph, 2.6 times smaller per triple): a migration, not a slice, worth about 100
   MiB only after the tick log is gone; a new pinned dependency and an rdflib adapter.

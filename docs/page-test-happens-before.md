# The page tests: who runs, and what orders them (nemik:W1060)

The symptom: a browser test fails with `Uncaught ReferenceError: popLater is not defined`, rarely,
only under load, and it passes alone. This note is the argument, from the code, for why, and for
what makes the failure impossible. It is not a measurement: the failure refused three gate runs
in three stacks and showed once in nine loaded runs, and 70 later loaded runs passed, which proves
nothing either way.

## The actors

| Actor | What it does | Where |
|---|---|---|
| pytest process (one per test target, one per shard) | picks a port, starts the server, drives the browser | tests/webpage.py `served`, `open_page` |
| `nemik-serve` subprocess | builds the model, binds a socket, answers GETs | src/nemik/serve.py `main`, `handler` |
| the server's threads | `ThreadingHTTPServer`: the main thread accepts, one thread per request | serve.py |
| Chromium and its page | parses `index.html`, fetches 11 classic scripts, runs one inline script | src/nemik/web/index.html |
| other test targets in the same gate | run concurrently (`--jobs`), each with its own server and port picks | Bazel |
| the host scheduler and the kernel's port allocator | decide who runs, and who gets a free port | the OS |

## The ordering each relied on, and whether anything enforced it

1. **Pick a port, then bind it.** `served` bound port 0, read the number, closed the socket, then
   started the server on that number. Nothing orders the close before another process's bind. Any
   process can take the port in the gap: another target's pick, or a connection whose ephemeral
   source port is that number. Not enforced.
2. **Connect succeeded, so our server is up.** A connect to the number proves that *some* process
   listens there. It says nothing about whose. Not enforced.
3. **The loop gave up silently.** After 100 tries the loop fell through and the test went on.
   Not enforced (fixed in 9fc2f60: it now raises).
4. **The server outlives the page load.** If the listener is another test's server, it is stopped
   when that test ends, at any point in our page's load. Not enforced, and not ours to enforce.

## The interleaving

1. Target A binds port 0, reads port P, closes. (Gap opens.)
2. Target B does the same and the kernel hands it P, or a Chromium connection of target C uses P as
   its source port, or B's server binds P first.
3. A starts `nemik-serve --port P`: it cannot bind P (address in use), exits with the error on its
   stderr (which was `/dev/null` until 9fc2f60).
4. A's connect loop connects to P and succeeds: it is B's listener.
5. A's page loads from B's server. B's test ends, B stops its server.
6. Chromium fetches at most six resources at once, and the scripts are requested in document
   order. Scripts 1 to 6 (three vendor files, graph, render, queue) were requested first and
   answered; the later ones (viewstate, panels, **cards**, wasm) are requested as slots free, and
   are refused once B's server is gone.
7. `popLater` is a function declaration at the top level of `cards.js`, hoisted, so it is undefined
   only if `cards.js` did not run at all. I found no top-level statement of the inline script before
   line 192 that evaluates a name from a later script (the calls at lines 142 and 181 are inside
   functions, and line 190 reads `popClose` inside an arrow), so line 192 (`addEventListener("mouseleave", popLater)`)
   is the first place the missing script is named. The page error names `popLater` and not the
   script because that is the first *use*, not the first *loss*.

This explains: rare (needs the gap and a collision), only under load (more concurrent pickers and
more time in the gap), passes alone (nobody to collide with), always the same name (first use),
and differing tests (any page test is exposed, since all three fixtures used the same pattern).

What it does not yet show: a trace of an actual failing run. The harness now records the failed
requests (9fc2f60), so the first recurrence will say which request was refused; if that is not a
later script, this argument is wrong and the card stays open.

## Why cards.js and not another asset: by time, not by path

A foreign server serves every page path alike until its own test ends and it is torn down, so the
loss is by time. Chromium fetches at most six scripts at once, in document order; the first six
(three vendor files, graph, render, queue) are answered, and the last four (viewstate, panels,
cards, wasm) are the ones refused. The page errors with the first *use* of a missing name, and the
first load-time use among those four is `popLater`.

This is checked by running the page, not by reading it (tests/test_page_load_order.py, W1069): with
all four refused, or with cards.js alone refused, the first error is `popLater is not defined`; with
cards.js served and the other three refused, it is not. A line scan of the inline script, tried first
to prove "no earlier use", failed on strings, template literals, comments and arrow bodies, which is
why the proof is a browser run. What the test does not cover: a failing run of the full page tests,
which is still untraced.

## The explicit ordering that replaces the assumed ones

`nemik-serve --port 0` binds the socket itself and writes `listening <port>` to stdout after the
bind and before it serves. The test reads that line. Therefore:

- The port is never held by anyone but the process that bound it: there is no gap (1).
- The URL is the address of *our* listener, by construction: the line comes from the process that
  holds the socket (2).
- A server that cannot bind writes no such line and exits; the read returns end of file and the
  test fails with its stderr (3).
- No other test's server can be the one the page talks to (4).

## The witness

`tests/test_serve_port.py` forces the interleaving rather than sampling it:

- A decoy takes the picked port in the gap; the old check (a connect) still succeeds. This is the
  old failure, deterministic.
- A server told to bind a port a decoy holds does not say it listens, and the read returns end of
  file.
- A server on port 0 says `listening` and a real port.

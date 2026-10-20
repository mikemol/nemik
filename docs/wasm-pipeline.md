# Python to Codon to wasm (nemik:W813, for the goal W812)

Operator, 2026-10-20: the page's JS that is being extracted is to be rewritten in Python, compiled
by Codon to wasm, as the way the web interface and the CLI tools share code, "since the rest of the
tooling is supposed to already be codon-ready". This is the spike: does the path exist, and what does
it need.

## It works

Three exported Python functions, built with the pinned Codon (the one `test_codon_pin` stages) and
called from node. Each ran and returned the right answer:

| Function | Uses | Result |
|---|---|---|
| `mix(a, b) = a*b + 1` | integers only | `mix(3, 4) = 13` |
| `total(n)`: sum of a list comprehension of squares | list allocation | `total(5) = 30` |
| `spread(n)`: a dict keyed by `"card-" + str(i % 7)`, sorted | str, dict, sorted | `spread(20) = 706` (7 keys, first of length 6) |

## The path

    codon build --release -o X.ll X.py          # @export keeps the function; IR, not a binary
    llc -mtriple=wasm64-unknown-unknown -mcpu=generic -filetype=obj -o X.o X.ll
    wasm-ld -mwasm64 --no-entry --export=FN --export=__heap_base --allow-undefined --gc-sections -o X.wasm X.o

- `@export` on a function keeps it in the IR; `--lib` writes a native shared object instead, so it is
  not used. Codon's IR carries x86 CPU attributes (`znver3` and a long feature list): `llc` ignores
  them with a warning per attribute, so its stderr is discarded.
- wasm64 (memory64), because Codon's lengths and pointers are 64-bit. Node 26 loads it with no flag.
  Integers cross the boundary as `BigInt`.
- `llc`, `clang` and `wasm-ld` are LLVM 23 under `/usr/lib/llvm/23/bin` on this host.

## The runtime the module imports

Everything the three programs needed from outside is this list, all `env.*`, all small:

| Import | What it does | Shim |
|---|---|---|
| `seq_alloc`, `seq_alloc_atomic` (size) | allocate | bump from `__heap_base`, 16-aligned, `memory.grow` as needed |
| `seq_realloc` (ptr, old, new) | grow a block | allocate and copy the smaller of the two |
| `memset`, `memcpy`, `bcmp` | libc | loops over the module's memory |
| `seq_alloc_exc`, `seq_throw` | raise a Python exception | allocate; throw a JS error |
| `seq_personality`, `seq_init` | unwinding, start-up | a stub returning 0; nothing, since no `main` runs |

There is no garbage collector: Codon's runtime uses Boehm and the shim is a bump allocator, so a
call that allocates leaks until the page resets the heap (set `top` back to `__heap_base` between
calls that return plain numbers, or copy the result out first).

## Not yet shown

1. A real browser: memory64 is in Chrome and Firefox now but its reach is a decision (W814): the
   fallback is wasm32, which the IR may retarget to since Codon's sizes are explicit `i64`.
2. A pinned toolchain for the gate: the host's LLVM 23 is not hermetic. The choices are a Bazel
   LLVM, or committing the built `.wasm` with its hash and a rebuild check, as the vendored wheels do.
3. Passing structured data (a list of cards with edges) in and out: flat arrays of integers and
   one string table are the likely shape, not Python objects.
4. Exceptions that are caught inside wasm (`seq_personality` is a stub), floats, and the cost of
   the module's size (the three above are small; `dict` and `str` pulled most of it).
5. What is pure enough to move: W815's inventory.

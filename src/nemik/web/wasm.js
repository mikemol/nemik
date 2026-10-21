// nemik:W820 (goal W812): the page's way into the Python core compiled to wasm.
//
// chains.wasm is src/nemik/core/chains.py through Codon (docs/wasm-pipeline.md). It is a wasm64
// (memory64) module: Chrome and Firefox now, Safari when it ships, no fallback (nemik:W814). The
// module imports the few runtime symbols Codon's IR calls; they are supplied here with a bump
// allocator (there is no collector, so a call that allocates leaks until its mark is restored).
//
// A classic script: NemikWasm.instantiate(bytes) gives the module's functions, synchronously once
// the bytes are fetched. index.html fetches chains.wasm and keeps the result.
const NemikWasm = (() => {
  const PAGE = 65536n;

  function runtime() {
    const state = { memory: null, top: 0n };
    const bytes = () => new Uint8Array(state.memory.buffer);
    const grow = end => {
      const have = BigInt(state.memory.buffer.byteLength);
      if (end > have) state.memory.grow((end - have + PAGE - 1n) / PAGE);
    };
    const alloc = size => {
      const at = (state.top + 15n) & ~15n;
      state.top = at + (size > 0n ? size : 1n);
      grow(state.top);
      return at;
    };
    const env = {
      seq_alloc: alloc,
      seq_alloc_atomic: alloc,
      seq_alloc_uncollectable: alloc,
      seq_alloc_atomic_uncollectable: alloc,
      // Codon's runtime signature is seq_realloc(ptr, new size, old size)
      seq_realloc: (p, size, old) => {
        const at = alloc(size);
        bytes().copyWithin(Number(at), Number(p), Number(p + (old < size ? old : size)));
        return at;
      },
      memset: (p, c, n) => { bytes().fill(Number(c) & 255, Number(p), Number(p + n)); return p; },
      memcpy: (d, s, n) => { bytes().copyWithin(Number(d), Number(s), Number(s + n)); return d; },
      bcmp: (a, b, n) => {
        const u = bytes();
        for (let i = 0; i < Number(n); i++) if (u[Number(a) + i] !== u[Number(b) + i]) return 1;
        return 0;
      },
      seq_alloc_exc: () => alloc(64n),
      seq_throw: () => { throw new Error("the Codon core raised an exception"); },
      seq_personality: () => 0,
      seq_init: () => {},
      // number formatting asks the locale for C strings; the core's are C-locale: "." and none
      seq_locale_decimal_point: () => state.statics.point,
      seq_locale_thousands_sep: () => state.statics.empty,
      seq_locale_grouping: () => state.statics.empty,
    };
    // a NUL-terminated string in module memory, allocated before any call so a call's mark spares it
    const cstring = text => {
      const at = alloc(BigInt(text.length + 1));
      bytes().set([...text].map(c => c.charCodeAt(0)).concat(0), Number(at));
      return at;
    };
    return { state, env, alloc, cstring };
  }

  // The longest chains of a graph of cards (core/chains.py). `ids` are the cards in the order to
  // visit them, `deps` are [prerequisite, dependent] pairs of ids; a pair naming an unknown card is
  // dropped. Returns {length, up, down, paths}, each a Map from id (paths only for cards on a
  // longest chain), as the core computes them.
  function chainsFor(instance, rt) {
    return (ids, deps) => {
      const index = new Map(ids.map((id, i) => [id, i]));
      const pairs = deps.filter(([a, b]) => index.has(a) && index.has(b));
      const mark = rt.state.top;
      const depsAt = rt.alloc(BigInt(Math.max(1, pairs.length * 2) * 8));
      const outAt = rt.alloc(BigInt(Math.max(1, ids.length * 3) * 8));
      const flat = new BigInt64Array(rt.state.memory.buffer, Number(depsAt), Math.max(1, pairs.length * 2));
      pairs.forEach(([a, b], k) => { flat[2 * k] = BigInt(index.get(a)); flat[2 * k + 1] = BigInt(index.get(b)); });
      const length = Number(instance.exports.chains(BigInt(ids.length), BigInt(pairs.length), depsAt, outAt));
      const out = new BigInt64Array(rt.state.memory.buffer, Number(outAt), Math.max(1, ids.length * 3));
      const up = new Map(), down = new Map(), paths = new Map();
      ids.forEach((id, i) => {
        up.set(id, Number(out[3 * i]));
        down.set(id, Number(out[3 * i + 1]));
        if (out[3 * i + 2] > 0n) paths.set(id, Number(out[3 * i + 2]));
      });
      rt.state.top = mark;
      return { length, up, down, paths };
    };
  }

  function instantiate(bytes) {
    const rt = runtime();
    const module = new WebAssembly.Module(bytes);
    // a runtime symbol this file does not supply fails when called, naming itself
    for (const need of WebAssembly.Module.imports(module)) {
      if (need.kind === "function" && !(need.name in rt.env)) {
        rt.env[need.name] = () => { throw new Error(`the page does not supply ${need.name}`); };
      }
    }
    const instance = new WebAssembly.Instance(module, { env: rt.env });
    rt.state.memory = instance.exports.memory;
    rt.state.top = instance.exports.__heap_base.value;
    rt.state.statics = { point: rt.cstring("."), empty: rt.cstring("") };
    // Codon sets up the module's globals inside main(); nothing else calls it, so it runs once here
    instance.exports.main(0, 0n);
    return { chains: chainsFor(instance, rt) };
  }

  return { instantiate };
})();

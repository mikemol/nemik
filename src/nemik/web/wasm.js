// nemik:W820 (goal W812): the page's way into the Python core compiled to wasm.
//
// core.wasm is src/nemik/core (chains, treemap) through Codon (docs/wasm-pipeline.md). It is a wasm64
// (memory64) module: Chrome and Firefox now, Safari when it ships, no fallback (nemik:W814). The
// module imports the few runtime symbols Codon's IR calls; they are supplied here with a bump
// allocator (there is no collector, so a call that allocates leaks until its mark is restored).
//
// A classic script: NemikWasm.instantiate(bytes) gives the module's functions, synchronously once
// the bytes are fetched. index.html fetches core.wasm and keeps the result.
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
      // the C math library the core links against: the JS Math, so the page agrees with itself
      pow: (a, b) => Math.pow(a, b),
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

  // The enables forest of the open cards (core/treemap.py tree_of), in the shape the page's old
  // treeOf returned: Maps by id for the open cards only. `nodes` carry id and state; `edges` carry
  // source, target and kind ("enables" or "waits"); an edge naming an unknown card is dropped. Cards
  // are numbered in ascending id order, which is the order the core breaks ties in.
  function treeFor(instance, rt) {
    return (nodes, edges) => {
      const ids = nodes.map(n => n.id).sort();
      const index = new Map(ids.map((id, i) => [id, i]));
      const shut = new Set(nodes.filter(n => n.state === "done" || n.state === "dropped").map(n => n.id));
      const used = edges.filter(e => index.has(e.source) && index.has(e.target));
      const n = ids.length, m = used.length, words = k => Math.max(1, k);
      const mark = rt.state.top;
      const openAt = rt.alloc(BigInt(words(n) * 8));
      const edgeAt = rt.alloc(BigInt(words(3 * m) * 8));
      const outAt = rt.alloc(BigInt(words(3 * n) * 8));
      const flags = new BigInt64Array(rt.state.memory.buffer, Number(openAt), words(n));
      ids.forEach((id, i) => { flags[i] = shut.has(id) ? 0n : 1n; });
      const flat = new BigInt64Array(rt.state.memory.buffer, Number(edgeAt), words(3 * m));
      used.forEach((e, k) => {
        flat[3 * k] = BigInt(index.get(e.source));
        flat[3 * k + 1] = BigInt(index.get(e.target));
        flat[3 * k + 2] = e.kind === "waits" ? 1n : 0n;
      });
      instance.exports.tree(BigInt(n), BigInt(m), openAt, edgeAt, outAt);
      const out = new BigInt64Array(rt.state.memory.buffer, Number(outAt), words(3 * n));
      const parent = new Map(), kids = new Map(), weight = new Map(), own = new Map(), roots = [];
      const up = new Array(n), mass = new Array(n);
      ids.forEach((id, i) => {
        up[i] = Number(out[3 * i]);
        mass[i] = Number(out[3 * i + 1]);
        if (!shut.has(id)) kids.set(id, []);
      });
      ids.forEach((id, i) => {
        if (shut.has(id)) return;
        parent.set(id, up[i] < 0 ? null : ids[up[i]]);
        weight.set(id, mass[i]);
        own.set(id, Number(out[3 * i + 2]));
        if (up[i] < 0) roots.push(id); else kids.get(ids[up[i]]).push(id);
      });
      rt.state.top = mark;
      return { parent, kids, weight, own, roots, ids, index, up, mass };
    };
  }

  // The ordered strip treemap of such a forest (core/treemap.py ordered_treemap), as the page's old
  // orderedTreemap returned it: a Map from id to {x, y, w, h, depth}, plus head for a frame with room.
  // Cards the no-room case reaches only as points inside a collapsed frame are left out, as before.
  function cellsFor(instance, rt) {
    return (tree, order, rect, pad = 4, head = 3 * pad) => {
      const n = tree.ids.length;
      const ranked = order.filter(id => tree.index.has(id)).map(id => tree.index.get(id));
      const k = ranked.length, words = c => Math.max(1, c);
      const mark = rt.state.top;
      const parentAt = rt.alloc(BigInt(words(n) * 8));
      const weightAt = rt.alloc(BigInt(words(n) * 8));
      const orderAt = rt.alloc(BigInt(words(k) * 8));
      const geoAt = rt.alloc(48n);
      const outAt = rt.alloc(BigInt(words(7 * n) * 8));
      const buf = rt.state.memory.buffer;
      const parents = new BigInt64Array(buf, Number(parentAt), words(n));
      const weights = new BigInt64Array(buf, Number(weightAt), words(n));
      tree.up.forEach((p, i) => { parents[i] = BigInt(p); weights[i] = BigInt(tree.mass[i]); });
      const ranks = new BigInt64Array(buf, Number(orderAt), words(k));
      ranked.forEach((card, i) => { ranks[i] = BigInt(card); });
      new Float64Array(buf, Number(geoAt), 6).set([rect.x, rect.y, rect.w, rect.h, pad, head]);
      instance.exports.cells(BigInt(n), BigInt(k), parentAt, weightAt, orderAt, geoAt, outAt);
      const out = new Float64Array(rt.state.memory.buffer, Number(outAt), words(7 * n));
      const cells = new Map();
      const point = new Set();
      const placed = i => out[7 * i] === 1;
      // parents come before their kids only by chance of id order, so find the points in one pass
      tree.ids.forEach((id, i) => {
        if (placed(i) && (out[7 * i + 3] <= 0 || out[7 * i + 4] <= 0)) point.add(id);
      });
      tree.ids.forEach((id, i) => {
        if (!placed(i)) return;
        const above = tree.parent.get(id);
        if (above && point.has(above)) return;
        const cell = { x: out[7 * i + 1], y: out[7 * i + 2], w: out[7 * i + 3], h: out[7 * i + 4], depth: out[7 * i + 5] };
        if (tree.kids.get(id).length && cell.w > 0 && cell.h > 0) cell.head = out[7 * i + 6];
        cells.set(id, cell);
      });
      rt.state.top = mark;
      return cells;
    };
  }

  // A repo's hue in degrees (core/text.py repo_hue): the name crosses as its UTF-16 code units.
  function hueFor(instance, rt) {
    return name => {
      const mark = rt.state.top;
      const at = rt.alloc(BigInt(Math.max(1, name.length) * 8));
      const codes = new BigInt64Array(rt.state.memory.buffer, Number(at), Math.max(1, name.length));
      for (let i = 0; i < name.length; i++) codes[i] = BigInt(name.charCodeAt(i));
      const hue = Number(instance.exports.hue(BigInt(name.length), at));
      rt.state.top = mark;
      return hue;
    };
  }

  // The WCAG luminance of a CSS colour (core/text.py luminance): the first three numbers in the
  // string are its red, green and blue, as the page's old luminance read them; none reads as 0.
  function lightFor(instance) {
    return css => {
      const m = String(css).match(/\d+(\.\d+)?/g);
      if (!m) return 0;
      const [r, g, b] = m.slice(0, 3).map(Number);
      return instance.exports.light(r, g, b);
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
    return { chains: chainsFor(instance, rt), treeOf: treeFor(instance, rt), orderedTreemap: cellsFor(instance, rt), repoHue: hueFor(instance, rt), luminance: lightFor(instance) };
  }

  return { instantiate };
})();

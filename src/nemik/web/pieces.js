// nemik:W2260 (split from panels.js): the page's piece cache. A static build publishes hashes.json and
// graph.json's pieces (graph/<repo>.json and graph/_fleet.json, W414/W415); the page refetches only the
// pieces whose hash moved. panels.js's sourceGraph asks pieceFetcher for the one function that reads a piece.
const pieceCache = {};  // path -> {hash, doc}
window.__pieceFetches = [];  // the paths fetched, in order: what a browser test counts
window.__pieceFailures = [];  // the paths whose fetch failed (nemik:W2260): the next round asks for each again

// The piece reader for one source: base is its URL prefix, hashes its hashes.json.
function pieceFetcher(base, hashes) {
  return path => {  // nemik:W1140: the cache holds the PROMISE, so rounds that overlap share one fetch
    const key = base + path;
    if (!pieceCache[key] || pieceCache[key].hash !== hashes[path]) {
      window.__pieceFetches.push(key);
      const entry = pieceCache[key] = {hash: hashes[path], doc: fetch(base + path).then(r => r.json())};
      // a failed piece is asked for again; the failure is recorded (nemik:W2260) so a test tells a retry
      // from a duplicate, and only the entry that failed is dropped: a late failure of an old fetch must
      // not delete the newer entry a moved hash put there
      entry.doc.catch(() => { window.__pieceFailures.push(key); if (pieceCache[key] === entry) delete pieceCache[key]; });
    }
    return pieceCache[key].doc;
  };
}

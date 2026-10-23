// nemik:W900 (W899): the graph as SVG, drawn from cytoscape's own geometry, so a PDF made from it holds
// vector paths and text and no picture of the canvas. Only public calls: position, width, height,
// boundingBox, midpoint, style, sourceEndpoint, targetEndpoint, controlPoints. Not drawn: the rings of a
// card on a longest chain (a background image), and the selection overlay.
const SVG_PAD = 20;
const ARROW_LEN = 7;

const svgEsc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const num = x => Math.round(x * 100) / 100;

// Opacity goes on each shape's own fill and stroke, never on a group: a group's opacity prints as a
// transparency group per element, which made the first vector PDF 23 MB.
const svgOpacity = ele => ele.numericStyle("opacity");

// A box (a repo, a tile) or a card: its outline in the card's own colours and shape.
function svgNode(n) {
  const p = n.position(), w = n.width(), h = n.height(), o = svgOpacity(n);
  const fill = n.style("background-color"), fo = n.numericStyle("background-opacity");
  const bw = n.numericStyle("border-width"), bc = n.style("border-color"), bs = n.style("border-style");
  const dash = bs === "dashed" ? ' stroke-dasharray="4 3"' : bs === "dotted" ? ' stroke-dasharray="1 2"' : "";
  const paint = `fill="${fill}" fill-opacity="${num(fo * o)}" stroke="${bw ? bc : "none"}" stroke-opacity="${num(o)}" ` +
    `stroke-width="${bw}"${dash}`;
  const x = p.x - w / 2, y = p.y - h / 2;
  const shape = n.style("shape");
  let out;
  if (shape === "diamond") {
    out = `<polygon points="${num(p.x)},${num(y)} ${num(x + w)},${num(p.y)} ${num(p.x)},${num(y + h)} ${num(x)},${num(p.y)}" ${paint}/>`;
  } else {
    const r = shape === "round-rectangle" ? 4 : 0;
    out = `<rect x="${num(x)}" y="${num(y)}" width="${num(w)}" height="${num(h)}" rx="${r}" ${paint}/>`;
  }
  const label = n.style("label");
  if (label) {
    const top = n.isParent();
    const ty = top ? y + 2 : p.y;
    out += `<text x="${num(p.x)}" y="${num(ty)}" text-anchor="middle" dominant-baseline="${top ? "hanging" : "central"}" ` +
      `font-family="${svgEsc(n.style("font-family"))}" font-size="${n.numericStyle("font-size")}" ` +
      `font-weight="${n.style("font-weight")}" fill="${n.style("color")}" fill-opacity="${num(o)}">${svgEsc(label)}</text>`;
  }
  return out;
}

// The arrowhead at the end of an edge: a triangle, or the bar of a tee, along the edge's last direction.
function svgArrow(e, from, to, o) {
  const kind = e.style("target-arrow-shape");
  if (kind === "none") return "";
  const dx = to.x - from.x, dy = to.y - from.y, d = Math.hypot(dx, dy) || 1;
  const ux = dx / d, uy = dy / d, len = ARROW_LEN * e.numericStyle("arrow-scale");
  const bx = to.x - ux * len, by = to.y - uy * len, nx = -uy * len / 2, ny = ux * len / 2;
  const color = e.style("target-arrow-color");
  if (kind === "tee") {
    return `<line x1="${num(to.x + nx)}" y1="${num(to.y + ny)}" x2="${num(to.x - nx)}" y2="${num(to.y - ny)}" ` +
      `stroke="${color}" stroke-opacity="${num(o)}" stroke-width="2"/>`;
  }
  return `<polygon points="${num(to.x)},${num(to.y)} ${num(bx + nx)},${num(by + ny)} ${num(bx - nx)},${num(by - ny)}" ` +
    `fill="${color}" fill-opacity="${num(o)}"/>`;
}

function svgEdge(e) {
  const a = e.sourceEndpoint(), b = e.targetEndpoint(), o = svgOpacity(e);
  // A bezier edge reports no control points; the curve is a quadratic through its midpoint m at t = 1/2,
  // whose control point is c = 2m - (a + b) / 2 (a straight edge gives c on the chord).
  const m = e.midpoint();
  const cps = e.controlPoints() || [{ x: 2 * m.x - (a.x + b.x) / 2, y: 2 * m.y - (a.y + b.y) / 2 }];
  const d = cps.length === 1 ? `M${num(a.x)},${num(a.y)} Q${num(cps[0].x)},${num(cps[0].y)} ${num(b.x)},${num(b.y)}`
    : `M${num(a.x)},${num(a.y)}` + cps.map(c => ` L${num(c.x)},${num(c.y)}`).join("") + ` L${num(b.x)},${num(b.y)}`;
  const pattern = e.pstyle("line-dash-pattern").value;
  const dash = e.style("line-style") === "dashed" && pattern && pattern.length ? ` stroke-dasharray="${pattern.join(" ")}"` : "";
  const last = cps.length ? cps[cps.length - 1] : a;
  return `<path d="${d}" fill="none" stroke="${e.style("line-color")}" stroke-opacity="${num(o)}" ` +
    `stroke-width="${e.numericStyle("width")}"${dash}/>${svgArrow(e, last, b, o)}`;
}

// The whole graph as one SVG document string, in the graph's own coordinates (zoom 1, no pan).
function graphSvg(g) {
  const shown = g.elements().filter(x => x.style("display") !== "none");
  const bb = shown.boundingBox({ includeLabels: true, includeOverlays: false });
  const x0 = bb.x1 - SVG_PAD, y0 = bb.y1 - SVG_PAD, w = bb.w + 2 * SVG_PAD, h = bb.h + 2 * SVG_PAD;
  const parents = shown.nodes(":parent").sort((p, q) => p.ancestors().length - q.ancestors().length);
  const leaves = shown.nodes().filter(n => !n.isParent());
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${num(x0)} ${num(y0)} ${num(w)} ${num(h)}" width="${num(w)}" height="${num(h)}">` +
    parents.map(svgNode).join("") + shown.edges().map(svgEdge).join("") + leaves.map(svgNode).join("") + "</svg>";
}

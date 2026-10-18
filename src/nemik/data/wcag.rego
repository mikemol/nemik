# nemik:W646: WCAG contrast over the view's colour tokens, judged per theme (W466, W645).
#
# input = {theme: {token: {"lum": relative luminance}}} for "light" and "dark" (nemik.wcagfacts.facts).
# The facts are measurements and this is the judgement: which token pairs matter and how much
# contrast each needs. A pair under its bar is a violation; there is no waiver.
#
# Not judged for contrast: --done and --dropped, which are de-emphasised states on purpose. The
# non-colour mark each state carries (1.4.1, W659) is judged below from input.marks.
package wcag

import rego.v1

# 1.4.3 Contrast (Minimum): text needs 4.5:1 against what it sits on.
text_pairs := [
	{"fg": "--ink", "bg": "--bg"},
	{"fg": "--ink", "bg": "--panel"},
	{"fg": "--muted", "bg": "--bg"},
	{"fg": "--muted", "bg": "--panel"},
]

# 1.4.11 Non-text Contrast: a component or its state mark needs 3:1 against its surroundings.
component_pairs := [
	{"fg": "--ready", "bg": "--panel"},
	{"fg": "--working", "bg": "--panel"},
	{"fg": "--blocked", "bg": "--panel"},
	{"fg": "--other", "bg": "--panel"},
	{"fg": "--interrupt", "bg": "--panel"},
	{"fg": "--unclaimed", "bg": "--panel"},
	{"fg": "--edge", "bg": "--bg"},
	{"fg": "--ring-fleet", "bg": "--bg"},
	{"fg": "--ring-repo", "bg": "--bg"},
	{"fg": "--ring-view", "bg": "--bg"},
]

themes := ["light", "dark"]

# The contrast ratio of two relative luminances, lighter over darker.
ratio(a, b) := r if {
	hi := max([a, b])
	lo := min([a, b])
	r := (hi + 0.05) / (lo + 0.05)
}

violations contains v if {
	some theme in themes
	some p in text_pairs
	r := ratio(input[theme][p.fg].lum, input[theme][p.bg].lum)
	r < 4.5
	v := {"criterion": "1.4.3", "theme": theme, "fg": p.fg, "bg": p.bg, "ratio": r, "min": 4.5}
}

violations contains v if {
	some theme in themes
	some p in component_pairs
	r := ratio(input[theme][p.fg].lum, input[theme][p.bg].lum)
	r < 3
	v := {"criterion": "1.4.11", "theme": theme, "fg": p.fg, "bg": p.bg, "ratio": r, "min": 3}
}

# 2.4.7 Focus Visible: a rule that removes a selector's outline needs a :focus or :focus-visible
# rule for the same base selector, or keyboard focus is invisible there. input.focus comes from
# nemik.wcagfacts.focus.
violations contains v if {
	some selector in input.focus.removed
	not replaced(selector)
	v := {
		"criterion": "2.4.7",
		"selector": selector,
		"why": "outline removed with no :focus or :focus-visible rule for the same selector",
	}
}

replaced(selector) if selector in input.focus.styled

# 1.4.1 Use of Colour: colour is not the only way to tell the card states apart. input.marks
# (nemik.wcagfacts.marks) lists, per state, the marks the page draws besides its fill: a label
# glyph, a border style, a shape. One state may carry none, the baseline the others differ from;
# two states with none differ by colour alone, and each is reported.
unmarked := {state | some state, kinds in input.marks; count(kinds) == 0}

violations contains v if {
	count(unmarked) > 1
	some state in unmarked
	v := {
		"criterion": "1.4.1",
		"state": state,
		"why": "no mark but its colour, and another state has none either",
	}
}

# 2.5.8 Target Size (Minimum): a pointer target is at least 24 by 24 CSS pixels, or sits where a
# 24 px circle centred on it meets no other target and no other undersized target's circle.
# input.targets is a list of {"name", "x", "y", "w", "h"} boxes read off the rendered page
# (tests/test_wcag_render.py); it is judged by target_violations, apart from violations, because it
# needs a browser. Not judged: a link inside a sentence, a control the user agent sizes, a target
# with an equivalent larger one on the page.
min_side := 24

target_violations contains v if {
	some i, t in input.targets
	undersized(t)
	some j, o in input.targets
	i != j
	crowded(t, o)
	v := {"criterion": "2.5.8", "target": t.name, "w": t.w, "h": t.h}
}

undersized(t) if t.w < min_side

undersized(t) if t.h < min_side

# t's 24 px circle meets o's box, or o is undersized too and the two circles meet.
crowded(t, o) if {
	cx := t.x + t.w / 2
	cy := t.y + t.h / 2
	dx := max([o.x - cx, 0, cx - (o.x + o.w)])
	dy := max([o.y - cy, 0, cy - (o.y + o.h)])
	dx * dx + dy * dy < 144
}

crowded(t, o) if {
	undersized(o)
	cx := t.x + t.w / 2
	cy := t.y + t.h / 2
	ox := o.x + o.w / 2
	oy := o.y + o.h / 2
	(cx - ox) * (cx - ox) + (cy - oy) * (cy - oy) < 576
}

# 2.4.3 Focus Order: Tab visits controls in a meaningful order. input.targets is in the order Tab
# visits them (document order; the page uses no positive tabindex), each with its box. Judged by
# order_violations: a step to the next control must not jump up a line, nor go left along the same
# line, because that is the reverse of the reading order.
line := 12

order_violations contains v if {
	some i, a in input.targets
	b := input.targets[i + 1]
	b.y + b.h / 2 < a.y + a.h / 2 - line
	v := {"criterion": "2.4.3", "from": a.name, "to": b.name, "why": "focus moves up a line"}
}

order_violations contains v if {
	some i, a in input.targets
	b := input.targets[i + 1]
	abs((b.y + b.h / 2) - (a.y + a.h / 2)) <= line
	b.x + b.w < a.x
	v := {"criterion": "2.4.3", "from": a.name, "to": b.name, "why": "focus moves left along a line"}
}

# 4.1.2 Name, Role, Value: every control has an accessible name. 2.5.3 Label in Name: when it shows
# text, the name contains it. input.names is a list of {"target", "accessible", "visible"} read off
# the rendered page (tests/test_wcag_render.py): the name the browser computes from aria-label, the
# labels and the text, and the letters and digits the control shows (a glyph or an aria-hidden span
# is decoration, not a label). Judged by name_violations, apart from violations, as target sizes are.
name_violations contains v if {
	some t in input.names
	trim_space(t.accessible) == ""
	v := {"criterion": "4.1.2", "target": t.target, "why": "no accessible name"}
}

name_violations contains v if {
	some t in input.names
	trim_space(t.visible) != ""
	not contains(lower(t.accessible), lower(trim_space(t.visible)))
	v := {
		"criterion": "2.5.3",
		"target": t.target,
		"why": "the accessible name does not contain the visible text",
	}
}

# A pair whose token the page does not define cannot be judged and is reported, not skipped.
unjudged contains u if {
	some theme in themes
	some p in array.concat(text_pairs, component_pairs)
	some name in [p.fg, p.bg]
	not input[theme][name]
	u := {"theme": theme, "token": name}
}

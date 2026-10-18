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

# A pair whose token the page does not define cannot be judged and is reported, not skipped.
unjudged contains u if {
	some theme in themes
	some p in array.concat(text_pairs, component_pairs)
	some name in [p.fg, p.bg]
	not input[theme][name]
	u := {"theme": theme, "token": name}
}

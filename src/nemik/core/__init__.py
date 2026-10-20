# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""core: the pure functions the CLI and the web view share (nemik:W818, W812).

Operator, 2026-10-20: the web and the CLI are facades over one body of code. The CLI runs these
functions natively; the page runs the same source compiled by Codon to wasm. So a function here
takes and returns plain data (lists, dicts, strings, numbers), imports nothing but its siblings, and
compiles under the pinned Codon, which test_codon_census holds. rdflib, paths, git and processes
belong to the facades.
"""

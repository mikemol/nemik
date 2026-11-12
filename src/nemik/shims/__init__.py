# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Mike Mol
"""Thin CPython entry shims over modules that compile under the pinned Codon (nemik:W2125).

The Codon census (tools/codon_census.py) reads the top-level modules of nemik and nemik.core, so a
module here is outside the compiled set by construction. A shim holds only what Codon cannot do and
the process needs to start (for example `sys.executable`, which Codon's sys lacks), passes it to the
compiled module as an explicit parameter, and adds no logic of its own.
"""

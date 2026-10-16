# Refused: format-named-reference-integer-document

**An example, not an entry.** This tree is `tests/fixtures/example-entry/` with one change: `dialect` references the integer-format document by `formatVersion` `"2.0.0"`.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

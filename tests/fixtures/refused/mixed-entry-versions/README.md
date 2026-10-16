# Refused: mixed-entry-versions

**An example, not an entry.** This tree is `tests/fixtures/shared-pair-entry/` with one change: the first entry, `example.fx-named`, is of entry format version 2 while the second is of version 3: a mixed release.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

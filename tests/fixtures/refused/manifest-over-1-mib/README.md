# Refused: manifest-over-1-mib

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `manifest.json` is 1,048,577 bytes: the same row, after a run of spaces.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

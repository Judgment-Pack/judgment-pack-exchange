# Refused: preset-row-with-output-digest

**An example, not an entry.** This tree is `tests/fixtures/preset-entry/` with one change: the preset's manifest row has an `outputDigest`.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

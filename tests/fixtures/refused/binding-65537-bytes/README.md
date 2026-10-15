# Refused: binding-65537-bytes

**An example, not an entry.** This tree is `tests/fixtures/unbound-entry/` with one change: `binding.json` is 65,537 bytes: the same document, after a run of spaces.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

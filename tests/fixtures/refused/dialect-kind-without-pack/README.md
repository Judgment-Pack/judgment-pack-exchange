# Refused: dialect-kind-without-pack

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: an entry of kind `dialect` has no `pack`.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

# Refused: source-kinds-not-the-documents

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `sourceKinds` names `selected-file` too, a kind none of the document's sources is.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

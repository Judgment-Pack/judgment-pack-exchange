# Refused: artifact-version-differs

**An example, not an entry.** This tree is `tests/fixtures/named-entry/` with one change: `artifact.version` is `"0.2.0"`; the document's `version` is `"0.1.0"`.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

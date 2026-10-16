# Refused: artifact-content-changed

**An example, not an entry.** This tree is `tests/fixtures/shared-pair-entry/` with one change: the second entry, `example.fx-named-copy`, holds other canonical content under the same `artifact` pair, its `dialect.digest` and the manifest following its bytes.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

Every identifier, record and key in this tree is synthetic, as in the tree it changes, and no live
service was asked.

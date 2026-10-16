# Refused: artifact-content-changed-across-releases

**An example, not an entry.** This tree is `tests/fixtures/named-entry/` with one change: the tree holds an earlier release of its catalog, `releases/v0.1.0/`, whose entry `example.fx-withdrawn`, since withdrawn, published the same `artifact` pair with other canonical content.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

Every identifier, record and key in this tree is synthetic, as in the tree it changes, and no live
service was asked.

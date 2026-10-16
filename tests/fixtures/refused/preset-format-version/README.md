# Refused: preset-format-version

**An example, not an entry.** This tree is `tests/fixtures/preset-entry/` with one change: the preset's `dialect` references its document by `formatVersion` `"3.0.0"`.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

Every identifier, record and key in this tree is synthetic, as in the tree it changes, and no live
service was asked.

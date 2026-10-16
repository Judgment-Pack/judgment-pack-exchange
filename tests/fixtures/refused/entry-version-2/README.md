# Refused: entry-version-2

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `entryVersion` is `2`, entry format version 2.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.

Every identifier, record and key in this tree is synthetic, as in the tree it changes, and no live
service was asked.

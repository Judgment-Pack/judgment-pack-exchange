# Refused: manifest-fixtures-out-of-order

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a second fixture, `again`, and the row's fixture lists in the reverse of `entry.json`'s order.
`tests/test_entries.py` requires the format to refuse it, saying: the manifest's fixtures do not name the entry's fixtures, in its order. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

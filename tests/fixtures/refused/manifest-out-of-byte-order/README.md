# Refused: manifest-out-of-byte-order

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a second entry, `example.a-first`, and the two rows in the reverse of their ids' byte order.
`tests/test_entries.py` requires the format to refuse it, saying: manifest: not in id byte order. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

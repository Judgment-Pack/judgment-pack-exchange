# Refused: manifest-1025-rows

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `manifest.json` has 1,025 rows: the entry's and 1,024 others.
`tests/test_entries.py` requires the format to refuse it, saying: manifest: 1025 rows, more than 1,024. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

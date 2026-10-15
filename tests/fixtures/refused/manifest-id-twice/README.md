# Refused: manifest-id-twice

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row is listed twice.
`tests/test_entries.py` requires the format to refuse it, saying: manifest: an id is listed twice. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

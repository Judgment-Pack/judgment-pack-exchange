# Refused: manifest-row-without-fixtures

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row has no `fixtures`.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: missing fixtures. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

# Refused: manifest-files-two-names

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture holds and lists `case.json` and `preparation.json` alone.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0].fixtures[0]: files lists 2 names, not 3 to 5. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

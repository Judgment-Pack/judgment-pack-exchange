# Refused: manifest-files-six-names

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture's list gives six names, `case.json` and `sources.json` twice.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0].fixtures[0]: files lists 6 names, not 3 to 5. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

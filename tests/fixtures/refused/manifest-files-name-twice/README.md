# Refused: manifest-files-name-twice

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture's list gives `case.json` twice.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0].fixtures[0]: files names a file twice. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

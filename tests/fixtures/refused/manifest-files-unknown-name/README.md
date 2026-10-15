# Refused: manifest-files-unknown-name

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture holds and lists `notes.json`.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0].fixtures[0]: files names notes.json, which no fixture holds. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

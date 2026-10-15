# Refused: fixture-file-not-listed

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture holds `notes.json`, which its list does not name.
`tests/test_entries.py` requires the format to refuse it, saying: fixtures/valid holds notes.json, which the manifest's file list does not name. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

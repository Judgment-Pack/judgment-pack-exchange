# Refused: fixture-listed-file-missing

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture's list names `sources.json`, which it does not hold.
`tests/test_entries.py` requires the format to refuse it, saying: fixtures/valid has no sources.json, which the manifest's file list names. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

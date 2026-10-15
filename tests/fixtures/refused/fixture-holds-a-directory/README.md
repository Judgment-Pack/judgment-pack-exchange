# Refused: fixture-holds-a-directory

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture holds a directory, `extra/`.
`tests/test_entries.py` requires the format to refuse it, saying: fixtures/valid holds extra, which is not a file. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

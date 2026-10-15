# Refused: description-4097-characters

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `description` is 4097 characters.
`tests/test_entries.py` requires the format to refuse it, saying: entry: description is not a string of 1 to 4096 characters. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

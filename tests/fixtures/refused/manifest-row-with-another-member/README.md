# Refused: manifest-row-with-another-member

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row adds `title`.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: unknown member title. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

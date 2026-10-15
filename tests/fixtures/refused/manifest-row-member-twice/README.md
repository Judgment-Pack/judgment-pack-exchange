# Refused: manifest-row-member-twice

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row gives `id` twice.
`tests/test_entries.py` requires the format to refuse it, saying: manifest.json: a member name is given twice. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

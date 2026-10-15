# Refused: manifest-id-malformed

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row's `id` is `Example.fx-metadata`, with an upper-case letter.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: id is not of the entry id form. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

# Refused: compatibility-with-another-member

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility` adds `gateway`.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: unknown member gateway. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

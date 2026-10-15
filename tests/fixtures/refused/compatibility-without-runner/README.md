# Refused: compatibility-without-runner

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility` names `desk` alone.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: missing runner. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

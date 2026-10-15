# Refused: fixture-unbound-source-without-binding

**An example, not an entry.** This tree is `tests/fixtures/unbound-entry/` with one change: the fixture of the unbound example neither holds nor lists `binding.json`.
`tests/test_entries.py` requires the format to refuse it, saying: fixtures/valid: binding.json is required: the dialect has an unbound source. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

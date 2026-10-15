# Refused: fixture-binding-without-unbound-source

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the fixture holds and lists `binding.json`, and the dialect's one source names its profile.
`tests/test_entries.py` requires the format to refuse it, saying: fixtures/valid: binding.json is refused: the dialect has no unbound source. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

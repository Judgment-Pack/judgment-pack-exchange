# Refused: verification-runner-leading-zero

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a verification record whose `runner` is `v0.011.0`.
`tests/test_entries.py` requires the format to refuse it, saying: verification[0]: runner is not a release tag. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

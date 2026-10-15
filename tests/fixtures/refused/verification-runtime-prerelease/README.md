# Refused: verification-runtime-prerelease

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a verification record whose `runtime` is `v0.32.0-rc.1`.
`tests/test_entries.py` requires the format to refuse it, saying: verification[0]: runtime is not a release tag. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

# Refused: compatibility-runner-two-spaces

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility.runner` is `>=v0.11.0  <v0.12.0`, with two spaces.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: runner is not a release tag or a range. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.

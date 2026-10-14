# Entries

This directory holds the Exchange's entries, one directory each: `entries/<publisher>/<name>/`. It
holds none yet.

An entry is a dialect, the reusable translation between a system and a pack, with what a reader
needs to check it. Its files:

- `entry.json`, the closed record of what the entry is, who wrote it, its licence, and the sentence
  its author asserts;
- `dialect.json`, the dialect document in RFC 0018's format;
- `fixtures/<name>/`, the recorded source records of each fixture and `preparation.json`, the exact
  canonical bytes the dialect must produce from them;
- `README.md`, what the dialect is for, in the publisher's words.

[`manifest.json`](../manifest.json) at the root pins each entry by the digests of its `entry.json`
and `dialect.json`. The whole format is in [`docs/entry-format.md`](../docs/entry-format.md), and
the way to add an entry is in [`CONTRIBUTING.md`](../CONTRIBUTING.md). A worked example, which is
not an entry, is under [`tests/fixtures/example-entry/`](../tests/fixtures/example-entry/).

# Entries

This directory holds the Exchange's entries, one directory each: `entries/<publisher>/<name>/`. It
holds three research presets, `judgmentpack.company-research`,
`judgmentpack.people-at-company` and `judgmentpack.procurement-opportunity`.

An entry is a dialect, the reusable translation between a system and a pack, with what a reader
needs to check it: of kind `dialect`, written against a pack, with fixtures; or of kind `preset`, an
input recipe without a pack or fixtures, which a desk pairs with a pack locally before any run. Its
files:

- `entry.json`, the closed record of what the entry is, its kind, who wrote it, its licence, and the
  sentence its author asserts;
- `dialect.json`, the dialect document in an integer format of RFC 0018 or a named format of RFC
  0021, for an entry of direction `input` or `both`; for a named format, `entry.json` carries the
  document's `artifact` pair, which no later release may publish with other content;
- `output.json`, the output dialect in RFC 0018 §10's form, for an entry of direction `output` or
  `both`; output fixtures are held by their digests only until the gateway publishes policy vectors;
- `fixtures/<name>/`, for kind `dialect`, the recorded source records of each fixture and
  `preparation.json`, the exact canonical bytes the dialect must produce from them;
- `README.md`, what the dialect is for, in the publisher's words.

[`manifest.json`](../manifest.json) at the root names each entry's kind and pins it by the digests of
its `entry.json` and of each document it holds. The whole format is in
[`docs/entry-format.md`](../docs/entry-format.md), and the way to add an entry is in
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Worked examples, which are not entries, are under
[`tests/fixtures/example-entry/`](../tests/fixtures/example-entry/) and
[`tests/fixtures/preset-entry/`](../tests/fixtures/preset-entry/).

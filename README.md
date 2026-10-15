# Judgment Pack Exchange

A dialect is a pack's terms spoken in a system's: the rules that derive a pack's facts and evidence
from the records a system holds, or its arguments from a disposition. The Exchange holds dialects
as the gateway's [catalog](https://github.com/Judgment-Pack/judgment-pack-gateway/tree/main/catalog)
holds bindings: each one as a pinned entry, with its licence, its author, and fixtures that a
second reader can check.

There are no entries yet. This repository holds the layout, the tests that will hold every entry to
it, and the contribution rules.

## What an entry establishes, and what it does not

An entry establishes one thing: that its author asserts these rules derive these facts and this
evidence-availability from records of that shape, or these arguments from that disposition, and
asserts nothing about any record's truth. That assertion stands under the Exchange's review. An
entry says nothing about whether a record is true, whether a system is reachable or authorised, or
whether a decision made with the dialect is sound.

## The entry format in brief

An entry is a directory `entries/<publisher>/<name>/`:

- `entry.json`: a closed object naming the entry (`id`, `title`, `direction`), the pack it was
  written against, the digest of each document it holds, what it requires, its source kinds, licence, author, the
  assertion above, its fixtures and its verifications;
- `dialect.json`: the dialect document (the input side), for direction `input` and `both`;
- `output.json`: the output dialect (RFC 0018 §10, the output side), for direction `output` and
  `both`; an entry of direction `both` holds the two documents, each with its own digest. Output
  fixtures are held by their digests only until the gateway publishes policy vectors;
- `fixtures/<name>/`: recorded source records and `preparation.json`, the canonical bytes the
  dialect must produce from them;
- `README.md`: what the dialect is for.

`manifest.json` at the root pins every entry by the SHA-256 of its `entry.json` and of each document it holds,
`dialect.json` and `output.json`, and lists each fixture's files.
The format is written out in [`docs/entry-format.md`](docs/entry-format.md); what a release of a
catalog is, and what a consumer verifies before it imports an entry, in
[`docs/release-contract.md`](docs/release-contract.md); and how this repository cuts a release, in
[`docs/releasing.md`](docs/releasing.md). The dialect's own
format is [RFC 0018](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0018-dialect.md);
the Exchange's design is recorded in
[RFC 0019](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md),
a Draft, which defines the entry format (§3) and the release contract (§7) that these pages follow.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short:

- one entry per pull request;
- fixtures are required, and a test runs the specification's preparation verifier over each;
- a material entry gets the review the specification's
  [governance](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/GOVERNANCE.md) sets
  for material changes;
- no credentials, tokens or personal data in any file: CI refuses recognised credential shapes and
  local paths, a maintainer must refuse credentials and personal data in every file before merge,
  and the scan's silence proves nothing;
- commits are signed off under the Developer Certificate of Origin.

To run the tests, check out the specification at the commit `ci.yml` pins into `.spec/` and run
`python -m unittest discover -s tests -v`. Without `.spec/` the preparation-verifier test is
skipped and says so.

## Licence

Apache License 2.0, see [`LICENSE`](LICENSE). An entry carries its own SPDX licence in `entry.json`.

# The entry format

This is the entry format as the maintainer fixed it for both the Exchange's RFC and this
repository. The RFC ([`rfcs/0019-exchange.md`](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md)
in the specification repository, in progress) is normative when it lands; until then this page and
the tests in [`tests/`](../tests/) are what the repository holds an entry to, and where they differ
from the RFC once it lands, the RFC is right and this page is a bug.

An **entry** is one directory `entries/<publisher>/<name>/` holding, as separate files with these
names:

- `entry.json` — a closed JSON object: `entryVersion` (`1`); `id` (`<publisher>.<name>`, lower-case
  letters, digits, `-` and `.`); `title`; `direction` (`"input"`, `"output"` or `"both"`); `pack` (an
  object: `id`, the pack's id, and either `versions`, a version range, or `digests`, an array of the
  pack digests the dialect was written against); `dialect` (an object: `path`, always
  `dialect.json`; `dialectVersion`; `digest`, the SHA-256 of the dialect document's canonical bytes
  as RFC 0018 defines them); `requires` (an object, members optional: `inputProfile` by digest,
  `connectionProfile` by digest, `platform` by catalog binding name for an output dialect);
  `sourceKinds` (the kinds the dialect's sources use, from RFC 0018's list); `licence` (an SPDX
  identifier); `author` (a handle or organisation name as the author chooses to be named; never
  required to be a personal name); `assertion` (the one fixed sentence the format gives: that the
  author asserts these rules derive these facts and this evidence-availability from records of that
  shape, or these arguments from that disposition, and asserts nothing about any record's truth);
  `fixtures` (an array of `{name, path, preparationDigest}`); `verification` (an array, empty until
  verified, of `{date, runner, runtime, readers, result}` where `readers` names the preparation
  verifiers that agreed and `result` is `"agree"`).
- `dialect.json` — the dialect document in RFC 0018's format.
- `fixtures/<name>/` — for each fixture, the recorded source records (as the Runner retains them)
  and `preparation.json`, the exact canonical bytes the dialect must produce from them; for a
  `research` source, the research record held by digest.
- `README.md` — what the dialect is for, in the publisher's words; no credentials, no personal
  data.

The repository root holds `manifest.json`, an array of `{id, path, entryDigest, dialectDigest}`
pinning each entry by the SHA-256 of its `entry.json` and `dialect.json` bytes, in `id` order; a
test holds every entry to the manifest and every fixture to its `preparationDigest` by running the
specification's preparation verifier over it. What a published entry establishes is the author's
assertion above, under the Exchange's review; nothing about truth. Credentials, tokens and personal
data are refused by a test before anything is merged.

## How this repository's tests read the format

These are choices the tests make where the format above leaves a spelling open; the RFC settles
them.

- A digest is written `sha256:` and 64 lower-case hexadecimal digits, as the specification writes
  them. `dialect.digest` is the digest of the dialect document's `canon` bytes (RFC 0018 §1);
  `entryDigest`, `dialectDigest` and `preparationDigest` are of the files' bytes, as they lie.
- A fixture directory holds `case.json`, `sources.json` (optional, absent for a case-only fixture),
  `profiles.json` and `preparation.json`: the files the specification's preparation verifier reads,
  with `dialect.json` from the entry.
- A fixture's `path` is relative to the entry directory.
- A fixture whose source kind the specification's verifier defines and cannot recompute (`kind-unread`) is skipped by the verifier test with a reason naming the kind; such a fixture is held by its digests only.
- A fixture whose dialect names a `dialectVersion` the verifier does not implement (version 3 today, with the `research` kind) is skipped by the verifier test with a reason naming the version; version-3 fixtures are held by digests until the verifier implements version 3. Any other refusal, `input-malformed` included, is a failure.

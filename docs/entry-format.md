# The entry format

This page mirrors the entry format of
[RFC 0019](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md) §3,
"The entry format", as revised on 2026-10-15 (judgment-pack-spec#163). The RFC defines the format and
this repository enforces it: this page and the tests in [`tests/`](../tests/) are what the
repository holds an entry to, and where they differ from the RFC, the RFC is right and this page is a
bug. The format is that of any catalog, a repository in it with a manifest a desk can read, and
exists for reuse between installations. What a release of a catalog is, and what a consumer checks
before import, is [the release contract](release-contract.md) (RFC 0019 §7).

An **entry** is one directory `entries/<publisher>/<name>/` holding, as separate files with these
names:

- `entry.json` — a closed JSON object: `entryVersion` (`1`); `id` (`<publisher>.<name>`, lower-case
  letters, digits, `-` and `.`); `title`; `direction` (`"input"`, `"output"` or `"both"`); `pack` (an
  object: `id`, the pack's id, an absolute URI as Core §4 makes it, and either `versions`, a version range, or `digests`, an array of the
  pack digests the dialect was written against); `dialect` (an object: `path`, always
  `dialect.json`; `dialectVersion`; `digest`, the SHA-256 of the dialect document's canonical bytes
  as RFC 0018 defines them; required for direction `input` and `both`, absent for `output`);
  `output` (an object: `path`, always `output.json`; `outputVersion`; `digest`, the SHA-256 of the
  output document's canonical bytes as RFC 0018 §10 defines them; required for direction `output`
  and `both`, absent for `input`); `requires` (an object, members optional: `inputProfile` by digest,
  `connectionProfile` by digest, `platform` by catalog binding name for an output dialect);
  `sourceKinds` (the kinds the dialect's sources use, from RFC 0018's list); `licence` (an SPDX
  identifier); `author` (a handle or organisation name as the author chooses to be named; never
  required to be a personal name); `assertion` (the one fixed sentence the format gives: that the
  author asserts these rules derive these facts and this evidence-availability from records of that
  shape, or these arguments from that disposition, and asserts nothing about any record's truth);
  `fixtures` (an array of `{name, path, preparationDigest}`); `verification` (an array, empty until
  verified, of `{date, runner, runtime, readers, result}` where `readers` names the preparation
  verifiers that agreed and `result` is `"agree"`).
- `dialect.json` — the dialect document in RFC 0018's format; present exactly when `entry.json`
  has a `dialect` member.
- `output.json` — the output dialect in RFC 0018 §10's form; present exactly when `entry.json` has
  an `output` member.
- `fixtures/<name>/` — for each fixture, the recorded source records (as the Runner retains them)
  and `preparation.json`, the exact canonical bytes the dialect must produce from them; for a
  `research` source, the research record held by digest.
- `README.md` — what the dialect is for, in the publisher's words; no credentials, no personal
  data.

The repository root holds `manifest.json`, an array of `{id, path, entryDigest, dialectDigest,
outputDigest}` pinning each entry by the SHA-256 of its `entry.json`, `dialect.json` and
`output.json` bytes, in `id` order; `dialectDigest` is present exactly when the entry has a dialect
document and `outputDigest` exactly when it has an output document; a
test holds every entry to the manifest and every fixture to its `preparationDigest` by running the
specification's preparation verifier over it. Each row also lists its fixtures' files
([the manifest](#the-manifest)). What a published entry establishes is the author's assertion above,
under the review of the catalog that holds the entry; nothing about truth. CI refuses recognised
credential shapes and local paths; a maintainer must refuse credentials and personal data in every
file of an entry before merge, recipe literals and receipt metadata included; and the scan's silence
proves nothing.

## Authoring metadata

`description`, `compatibility` and `upgrade` are optional members of `entry.json`, included in its
`entryDigest` when present. `description` says what the entry is for; `compatibility` names the desk
and runner releases its author says it fits; `upgrade` gives review notes keyed by the previous
entry's digest, the manifest's `entryDigest`, not a dialect digest. These are authoring statements,
not verification records or permissions. The RFC marks their six rows of the table below, their
bounds and the compatibility-range grammar as its 2026-10-15 revision's proposal until this
repository enforces them; its tests enforce them since judgment-pack-exchange#6.

Authors should account for verification records changing `entryDigest`: an upgrade note may need to
name each intermediate entry digest, even when the dialect is unchanged. An absent `compatibility`
makes no compatibility statement; an absent `upgrade`, or no note for the previous digest, supplies
no upgrade guidance. None of these absences approves an import or an upgrade
([the release contract](release-contract.md#compatibility-is-advice)).

## The members

Every member and nested object of `entry.json` has a type, a requiredness, a grammar or a set of
allowed values, and a bound:

| Member | Type | Required | Grammar, allowed values and bound |
| --- | --- | --- | --- |
| `entryVersion` | integer | yes | `1` |
| `id` | string | yes | `^[a-z0-9]+(\.[a-z0-9-]+)+$`, 3 to 128 characters, equal to the entry's path under `entries/` with `/` read as `.`: `entries/<publisher>/<name>/` holds the id `<publisher>.<name>` |
| `title` | string | yes | 1 to 200 characters |
| `description` | string | no | 1 to 4096 characters |
| `compatibility` | object, closed | no | exactly `desk` and `runner` |
| `compatibility.desk` | string | with `compatibility` | 1 to 64 characters; a release tag or range, as [defined below](#release-tags-and-compatibility-ranges), naming the releases of any desk that reads catalogs |
| `compatibility.runner` | string | with `compatibility` | 1 to 64 characters; a release tag or a range of release tags, as [defined below](#release-tags-and-compatibility-ranges) |
| `upgrade` | object keyed by entry digest | no | 1 to 32 members; each key a `sha256:` digest of a previous `entry.json`'s stored bytes, each value a note below |
| `upgrade.<entryDigest>` | string | for each key in `upgrade` | 1 to 2048 characters: notes for review when moving from that entry digest to this entry |
| `direction` | string | yes | `input`, `output` or `both` |
| `pack` | object, closed | yes | `id`, and exactly one of `versions` and `digests` |
| `pack.id` | string | yes | an absolute URI (Core §4), at most 2048 characters |
| `pack.versions` | string | exactly one of the two | 1 to 64 characters, in the pack's own versioning; a range syntax is an unresolved question (2) |
| `pack.digests` | array of strings | exactly one of the two | 1 to 16 `sha256:` digests |
| `dialect` | object, closed | for `input` and `both`; absent for `output` | `path`, `dialectVersion` and `digest` |
| `dialect.path` | string | with `dialect` | the literal `dialect.json` |
| `dialect.dialectVersion` | integer | with `dialect` | 2 or more, equal to the dialect document's `version` |
| `dialect.digest` | string | with `dialect` | a `sha256:` digest |
| `output` | object, closed | for `output` and `both`; absent for `input` | `path`, `outputVersion` and `digest` |
| `output.path` | string | with `output` | the literal `output.json` |
| `output.outputVersion` | integer | with `output` | 1 or more, equal to the integer the output document's own `outputVersion` spells |
| `output.digest` | string | with `output` | a `sha256:` digest |
| `requires` | object, closed | yes | its members optional |
| `requires.inputProfile` | string | no | a `sha256:` digest |
| `requires.connectionProfile` | string | no | a `sha256:` digest |
| `requires.platform` | string | no | `^[a-z][a-z0-9-]*$`, at most 64 characters |
| `sourceKinds` | array of strings | yes | 1 to 16, distinct (empty for `output`), each a kind RFC 0018 lists for the document's `dialectVersion` (§4 there); a `dialectVersion` above 3 is read with version 3's list until a later RFC defines more |
| `licence` | string | yes | one SPDX licence identifier matching `[A-Za-z0-9][A-Za-z0-9.+-]*`, or a `LicenseRef-` form of that grammar; no compound licence expressions; at most 64 characters |
| `author` | string | yes | 1 to 100 characters |
| `assertion` | string | yes | the fixed sentence (below), byte for byte |
| `fixtures` | array of closed objects | yes | 1 to 64 (empty for `output`) |
| `fixtures[].name` | string | yes | `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 64 characters, distinct within the entry |
| `fixtures[].path` | string | yes | `fixtures/<name>` |
| `fixtures[].preparationDigest` | string | yes | a `sha256:` digest |
| `verification` | array of closed objects | yes | at most 32; empty until verified |
| `verification[].date` | string | yes | `YYYY-MM-DD` |
| `verification[].runner` | string | yes | a release tag, in the grammar below |
| `verification[].runtime` | string | yes | a release tag, in the grammar below |
| `verification[].readers` | array of strings | yes | 1 to 8, each `<repository>/<path>@<commit>`, at most 200 characters |
| `verification[].result` | string | yes | `agree` |

`entry.json` and `README.md` are each at most 64 KiB, and a fixture directory at most 16 MiB;
`dialect.json` is bounded as RFC 0018 §12 bounds a verifier's inputs. Every object is closed: a
member the table does not list is refused. A member name given twice in one object is refused, as
Core §2.1 refuses one. The 64 KiB file bound governs even when every member is within its individual
bound; the maxima are not a promise that all maximum-length values fit together.

## Release tags and compatibility ranges

A **release tag** has the form `^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`, as a
verification record's tags do: a lower-case `v` and three integers in ASCII digits, with no leading
zeroes, and nothing before or after. `v0.10.0` is one; `v0.010.0`, `0.10.0`, `v0.10` and
`v0.10.0-rc.1` are not. Tags are ordered by their three integer components, so `v0.9.0` is below
`v0.10.0`. A catalog's own releases are tags in this grammar ([the release contract](release-contract.md)).

A **compatibility value** is either one such tag, naming that release alone, or two comparisons: `>=`
followed by the lower tag and `<` followed by the upper tag, with exactly one space between them,
`>=v0.10.0 <v0.11.0`, for example. The lower bound is inclusive and the upper bound exclusive, and
the upper bound must exceed the lower. No other range syntax is admitted.

## The manifest

`manifest.json` is at most 1 MiB (1,048,576 bytes) and contains at most 1,024 rows. Each row is a
closed object with exactly `id`, `path`, `entryDigest`, `fixtures`, and `dialectDigest` and
`outputDigest` when the entry's direction requires them. Duplicate member names are refused. Rows
have distinct `id` values and are ordered by those ids as byte strings (their UTF-8 bytes). The `id`
has the grammar and bound in the members' table; each digest has the form given below. The row's
`path` is exactly `entries/<publisher>/<name>`, without a trailing slash: split `id` at its first `.`
for `<publisher>` and `<name>`, leaving any further dots in `<name>`. A path that differs, or an
entry whose `id` differs from the row's, is refused. There is exactly one row per entry directory in
the release's tree and one entry per row.

The row's `fixtures` is an array of closed `{name, files}` objects, one per fixture in `entry.json`
in the same order (empty for an output-only entry). Each `name` equals that fixture's name, and
`files` is an array of 3 to 5 distinct strings listing its complete file set by basename.
`case.json`, `profiles.json` and `preparation.json` are required; `sources.json` is optional;
`binding.json` is required exactly when the entry's dialect has an unbound source. No other file is
admitted in a fixture directory. A consumer knows from this list which files to fetch under
`<path>/fixtures/<name>/` over any transport; a listed file that cannot be fetched is a failure, not
an absent optional file. The list equals the file set in the release's tree.

## How the format is spelled

- **The assertion.** `assertion` is exactly this sentence: "The author asserts that these rules
  derive these facts and this evidence-availability from records of that shape, or these arguments
  from that disposition, and asserts nothing about any record's truth."
- **Two documents.** An entry's `direction` follows from the documents it holds: `input` holds
  `dialect.json`, `output` holds `output.json`, and `both` holds both, each with its own digest in
  `entry.json` and in `manifest.json`; a document the direction does not give is refused, as is one
  it gives and the entry lacks. `output.digest` is the digest of the output document's `canon` bytes
  (RFC 0018 §1, §10); `outputDigest` is of the file's bytes, as it lies. `output.outputVersion` is an
  integer equal to the integer the document's own `outputVersion` spells, which RFC 0018 §10 writes
  as the string `"1"`. Output fixtures are held by their digests only until the gateway publishes
  policy vectors (RFC 0019, unresolved question 5): an output document has no preparation for a
  verifier to recompute, so an entry of direction `output` holds `sourceKinds` and `fixtures` as
  empty arrays, and an output document is pinned by `output.digest` and the manifest's
  `outputDigest` alone.
- **Digests.** Every digest is written `sha256:` followed by 64 lower-case hexadecimal characters,
  as RFC 0018 §1 writes one. `dialect.digest` is the digest of the dialect document's `canon` bytes
  (RFC 0018 §1): its dialect digest (§2 there), which every preparation it produces carries as
  `mappingDigest` (§9.1 there). The manifest's `entryDigest` and `dialectDigest`, and a fixture's
  `preparationDigest`, are digests of the files' bytes as stored. A `dialect.json` stored in bytes
  other than its `canon` form, indented say, has a `dialectDigest` other than its `dialect.digest`,
  and each is held to its own definition. `preparation.json` holds the preparation's canonical bytes
  (RFC 0018 §9.5), so its `preparationDigest` is the preparation's digest.
- **A fixture's files.** A fixture directory holds `case.json`, the case document; `sources.json`,
  the acquisitions, optional and absent for a case-only fixture; `profiles.json`, the input profiles
  the fixture was prepared under; `preparation.json`; and, exactly for a dialect with an unbound
  source, `binding.json`, the binding document the fixture was recorded under (RFC 0018 §4.4). This
  file set is closed and listed in the manifest row as above. A verifier reads these inputs under
  RFC 0018 §11, with the dialect taken from the entry's `dialect.json`. A fixture's `path` is
  `fixtures/<name>`, relative to the entry's directory. For a `research` source, `sources.json` holds
  the research record as the acquisition's result, held by its digest under its receipt, as every
  acquisition is.

## How this repository's tests read the format

These are the tests' readings where the RFC leaves a spelling to the implementation; the RFC
settles any that it spells out.

- A length in characters is a count of Unicode code points, as Python counts a string's length.
- A dialect has an **unbound source** when one of its sources is of kind `operation` and names
  neither `profile` nor `profileDigest` (RFC 0018 §4.4); the tests decide `binding.json` by that.
- A fixture's `binding.json` is held by the tests themselves, whether or not any reader can replay
  the fixture: at most 65,536 bytes (RFC 0018 §12), and, for a dialect with an unbound source, the
  form of RFC 0018 §4.4: a closed object of `dialect`, the entry's `dialect.digest`, and `sources`,
  naming each unbound source of the dialect and no other name, each a closed object of `profile`, a
  non-empty string, and `profileDigest`, a digest.
- A reader in `verification[].readers`, `<repository>/<path>@<commit>` in the RFC, is read as
  `<owner>/<name>/<path>@<commit>`: owner and name each 1 to 100 characters of `[A-Za-z0-9_.-]`; a
  path that is not empty and has no empty and no `..` segment; and a commit of 7 to 40 lower-case
  hexadecimal digits. This is the catalog's reading until the RFC gives the locator's grammar
  (judgment-pack-spec#166, item 5).
- The manifest is read within its bound: the file's size is taken first, a file over 1 MiB is
  refused before any byte of it is read or parsed, and otherwise exactly its size is read. A
  manifest over 1,024 rows is refused as a whole, with no row read further. The order of the names
  in a fixture's `files` is not prescribed; the examples list them in byte order.
- A release tag and a compatibility value are checked by `release_tag_ok` and `compatibility_ok` in
  [`tests/test_entries.py`](../tests/test_entries.py); [`release.yml`](../.github/workflows/release.yml)
  holds a release's own tag to the same function.
- Every value of an output document's `policies` is held to the decision-policy form of RFC 0018 §10 and the gateway's `docs/design/engine-config.md` (`decisionPolicy`, at v0.15.0): a closed object, `outcomes` required, `packs`, `reviewed`, `bind`, `fix`, `closed` and `requireSignedRecord` optional and of the gateway's types, every `argument` and `fact` an RFC 6901 pointer.
- A fixture whose source kind the specification's verifier defines and cannot recompute (`kind-unread`) is skipped by the verifier test with a reason naming the kind; such a fixture is held by its digests only.
- A fixture whose dialect names a `dialectVersion` the verifier does not implement (version 3 today, with the `research` kind and the unbound source form) is skipped by the verifier test with a reason naming the version; version-3 fixtures are held by digests until the verifier implements version 3. Any other refusal, `input-malformed` included, is a failure.
- `dialect.json`'s bounds (RFC 0018 §12) are held by the verifier when it reads a fixture; the tests
  hold no separate byte bound on it.
- The examples under [`tests/fixtures/`](../tests/fixtures/) are trees of the format's shape that
  are not entries: a passing example of each rule, and under `refused/` one tree per refusal, each a
  passing example with one change. The tests require each refused tree to produce exactly the
  problems listed for it, each problem naming the bound it fails, and each tree to have a problem no
  other tree produces; and they revert each tree's one change in a scratch copy and require the
  result to pass and to equal its passing example byte for byte.

## What the tests do about credentials and personal data

CI refuses recognised credential shapes and local paths. A maintainer must refuse credentials and
personal data in every file before merge. The scan's silence proves nothing.

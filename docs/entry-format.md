# The entry format

This page mirrors the entry format of
[RFC 0019](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md) §3,
"The entry format", and the test of its §4, as revised on 2026-10-16 by judgment-pack-spec#193
(merged as `8371cdb`): entry format version 3, which keeps version 2's required `kind`, its `preset`
kind and the catalog's settled checks (judgment-pack-spec#178), and adds checked references for the
named Dialect artifact formats of RFC 0021. The RFC defines the format and this repository enforces
it: this page and the tests in [`tests/`](../tests/) are what the repository holds an entry to, and
where they differ from the RFC, the RFC is right and this page is a bug. The format is that of any
catalog, a repository in it with a manifest a desk can read, and exists for reuse between
installations. What a release of a catalog is, and what a consumer checks before import, is
[the release contract](release-contract.md) (RFC 0019 §7).

## Entry format version 3

An entry of version 3 has a required `kind`, `dialect` or `preset`:

- an entry of kind **`dialect`** holds a dialect written against a pack, with the pack, its fixtures
  and its verification records, as version 1 did. Its document is in an integer format of RFC 0018
  or, new in version 3, a named format of RFC 0021, whose identity the entry carries as `artifact`
  ([Named artifacts](#named-artifacts));
- an entry of kind **`preset`** holds an input recipe without a pack and without fixtures: a
  dialect of integer version 3 whose every bindable source is unbound ([Presets](#presets)). A desk
  pairs it with a pack locally before any run.

A version-3 reader, this repository's tests among them, refuses version-1 and version-2 entries as
`entry-version-unread`: the entry forms are closed. A version-2 reader refuses `entryVersion: 3`,
but may read the release's manifest rows, whose form is unchanged from version 2; reading a row
establishes its form and pins, not acceptance of the entry it references. A version-1 reader refuses
these entries and the non-empty manifest's rows, whose `kind` it does not admit, and versions 2 and
3 refuse version-1 rows, which lack it. The empty manifest, `[]`, has no rows and fits all three; it
is the only manifest this catalog has released (`v0.1.0`), so no published entry is stranded.

A catalog whose test reads version 3 moves every entry to version 3 in one release, changing
`entryVersion` and the `entryDigest` pins that follow, and keeping integer documents and their
digests intact. Its test refuses a release that mixes versions: every entry of another version is
`entry-version-unread`. Consumers need version-3 support before importing such a release; earlier
releases stay available to their readers.

Entry format versions are separate from dialect document formats. An entry of kind `dialect` may
reference an integer-format document by `dialectVersion`, 2 or more, or a named-format document by
`formatVersion`, `"2.0.0"` or `"3.0.0"`; a preset references an integer document of exactly
version 3. Named and integer documents coexist in one release. Declaring a format does not make it
readable by a form checker or a verifier, and no selector is inferred or coerced. Converting a
document to a named format is RFC 0021's explicit new-artifact operation, with a new canonical
digest.

An **entry** is one directory `entries/<publisher>/<name>/` holding, as separate files with these
names:

- `entry.json` — a closed JSON object: `entryVersion` (`3`); `kind` (`"dialect"` or `"preset"`);
  `id` (`<publisher>.<name>`, lower-case letters, digits, `-` and `.`); `title`; `direction`
  (`"input"`, `"output"` or `"both"`); `pack` (required for kind `dialect`, absent for `preset`; an
  object: `id`, the pack's id, an absolute URI as Core §4 makes it, and either `versions`, a version
  range, or `digests`, an array of the pack digests the dialect was written against); `dialect` (a
  closed object: `path`, always `dialect.json`; exactly one of `dialectVersion` for an integer
  format or `formatVersion` for a named format; `digest`, the SHA-256 of the whole document's
  canonical bytes under RFC 0018 and RFC 0021, identity members included; required for direction
  `input` and `both`, absent for `output`); `artifact` (exactly `id` and `version`, copied from the
  document, required exactly for a named input document of kind `dialect`, forbidden for a preset);
  `output` (an object: `path`, always `output.json`; `outputVersion`; `digest`, the SHA-256 of the
  output document's canonical bytes as RFC 0018 §10 defines them; required for direction `output`
  and `both`, absent for `input`); `requires` (an object, members optional: `inputProfile` by
  digest, `connectionProfile` by digest, `platform` by catalog binding name for an output dialect);
  `sourceKinds` (the source kinds the dialect uses, from RFC 0018's list); `licence` (an SPDX
  identifier); `author` (a handle or organisation name as the author chooses to be named; never
  required to be a personal name); `assertion` (the one fixed sentence the format gives: that the
  author asserts these rules derive these facts and this evidence-availability from records of that
  shape, or these arguments from that disposition, and asserts nothing about any record's truth);
  `fixtures` (for kind `dialect`, an array of `{name, path, preparationDigest}`; absent for
  `preset`); `verification` (an array, empty for `preset` and otherwise empty until verified, of
  `{date, runner, runtime, readers, result}` where `readers` names the preparation verifiers that
  agreed and `result` is `"agree"`).
- `dialect.json` — the dialect document in an integer format of RFC 0018 or a named format of
  RFC 0021; present exactly when `entry.json` has a `dialect` member.
- `output.json` — the output dialect in RFC 0018 §10's form; present exactly when `entry.json` has
  an `output` member.
- `fixtures/<name>/` — for kind `dialect`, for each fixture, the recorded source records (as the
  Runner retains them) and `preparation.json`, the exact canonical bytes the dialect must produce
  from them; for a `research` source, the retained responses and research record under RFC 0018
  §4.3.
- `README.md` — what the dialect is for, in the publisher's words; no credentials, no personal
  data.

The repository root holds `manifest.json`, an array of closed rows with `id`, `kind`, `path`,
`entryDigest`, `fixtures`, and `dialectDigest` and `outputDigest` by direction, pinning each entry
by the SHA-256 of its `entry.json`, `dialect.json` and `output.json` bytes, in `id` order
([the manifest](#the-manifest)). Version 3 adds no member to the row: an entry's `artifact` lives in
the `entry.json` its `entryDigest` pins, and is not copied into the row. A test holds every entry to
the manifest, every dialect document to its form by the catalog's own form checker
([below](#the-catalogs-form-checker)), and every fixture to its `preparationDigest` by running the
specification's preparation verifier over it. A preset row has `fixtures: []` and no `outputDigest`;
its `kind` equals the entry's. What an entry of either kind establishes is its author's assertion
under the review of the catalog that holds it, and, for kind `dialect`, that its fixtures hold where
a verification record says so; neither kind establishes anything about truth (RFC 0019 §5). CI
refuses recognised credential shapes and local paths; a maintainer must refuse credentials and
personal data in every file of an entry before merge, recipe literals and receipt metadata included;
and the scan's silence proves nothing.

## Named artifacts

RFC 0021 adds two named document formats (the Dialect companion, `spec/dialect.md` §2.1): a document
whose root has `formatVersion`, exactly `"2.0.0"` or `"3.0.0"`, selecting the translation forms of
family 2 or 3; `id`, a stable, opaque artifact-series identifier; and `version`, its artifact
version in Core's three-component grammar, in place of the integer `version`. Both named formats
apply version 3's encoding rule to the whole document, and family 2 admits neither unbound nor
research sources. The canonical document includes the three identity members.

**The reference.** For an integer-format document the entry's `dialect` is exactly
`{path, dialectVersion, digest}`, as in version 2. For a named-format document of kind `dialect` it
is exactly `{path, formatVersion, digest}`, `formatVersion` the document's exact selector, and the
entry carries `artifact`, exactly `{id, version}`, equal as JSON string values (the same Unicode
scalar values after unescaping), with no normalization, to the document's root `id` and `version`.
`artifact` is forbidden on an entry for an integer-format document, on a preset and on an
output-only entry. The selector, the canonical digest and the pair are read from the document and
checked against it, never edited on their own. `artifact.id` is separate from the entry's path-based
`id`.

**The reference refusals.** The catalog checks the reference and the pair against the whole
document, for either entry kind, and reports the first refusal that applies, in this order: the
reference's form, then a format mismatch, then the `artifact` checks, then the digest.

| Refusal | When |
| --- | --- |
| `dialect-reference-form` | both `dialectVersion` and `formatVersion`, or neither; an unknown member; a wrong `path` or type; a `digest` that is no `sha256:` digest; a selector outside the exact values (`dialectVersion` an integer of 2 or more; `formatVersion` exactly `"2.0.0"` or `"3.0.0"`) or the kind rules (a preset: `dialectVersion` exactly 3, no `formatVersion`) |
| `dialect-format-mismatch` | a named reference with an integer-format document, or the reverse; a `formatVersion` or `dialectVersion` unequal to the document's. No fallback between forms is read |
| `artifact-required` | an entry for a named-format input document without `artifact` |
| `artifact-forbidden` | `artifact` on an entry for an integer-format document, on a preset or on an output-only entry |
| `artifact-malformed` | `artifact` outside its closed form, its grammar or its bounds |
| `artifact-mismatch` | `artifact.id` or `artifact.version` other than the document's root member |
| `dialect-digest-mismatch` | `dialect.digest` other than the digest of the whole document's canonical bytes, `formatVersion`, `id` and `version` included for a named document |

Before any of these, a version-3 reader refuses an entry of another `entryVersion` as
`entry-version-unread`.

**Publication identity.** A catalog holds `(artifact.id, artifact.version)` immutable across its
history, as RFC 0021 requires of a publication authority. Two entries of one release declaring the
same pair with different canonical `dialect.digest` refuse the release as
`artifact-content-changed`, and so does an entry declaring, with another canonical digest, a pair an
earlier release of this catalog published, even when the earlier entry has since been withdrawn. The
same pair with the same canonical digest is admitted in another entry or kind, under that kind's
reference rules. The check compares the canonical `dialect.digest`, not the stored-byte
`dialectDigest` or `entryDigest`, and an artifact pair is never an `upgrade` key.

**The history the check reads.** CI fetches the catalog's tags. Every tag in the release-tag grammar
that resolves to a commit and is lower in tag order than the release being made is an earlier
release; for a pull request, every release is. CI reads each earlier release's `manifest.json`, in
its own row form and within the manifest's bounds, and every `entry.json` its rows pin, as blobs at
that release's commit, each within 64 KiB and held to its row's `entryDigest`. Each earlier entry is
read for its `entryVersion`: only an entry of version 3 with a `formatVersion` reference is held to
the `dialect` and `artifact` forms above and holds a pair; every other entry holds none and is
checked by its digest only. A tag listing that cannot be read, or a missing or malformed manifest or
entry, refuses the release as `artifact-history-invalid`. The catalog has no form-only fallback. A
consumer that does not hold an earlier manifest checks form only and reports
`artifact-history-unchecked` ([the release contract](release-contract.md#artifact-history)); that
report is the consumer's alone.

**Published documents only.** An entry's `dialect.json` is the published document. An installation's
bound derivative (RFC 0021's §2.1 amendment, RFC 0018 §4.4) keeps the identity members and carries
no marker, so the format cannot tell one from its bytes: keeping it out is the reviewer's duty. When
the pair's publication is in the history the check reads, the derivative's other canonical content
is refused as `artifact-content-changed`.

The pair establishes the identity the document declares, checked against its bytes; it establishes
nothing about truth, authenticity, who may publish under it, execution permission, binding readiness
or an installation's binding.

## Presets

A preset is an entry of kind `preset`. Its form is closed:

- its `direction` is `input`; it has a `dialect` member and `dialect.json`, and no `output` member
  or `output.json`;
- it has no `pack` and no `fixtures` member, and its `verification` is `[]`: no preparation was
  verified;
- its reference is the integer form with `dialect.dialectVersion` exactly 3, and its `dialect.json`
  is a document of integer version 3 held to the whole document form of RFC 0018 §§2–8 and 12
  through round 11, version 3's one-spelling rule included. A `formatVersion` on a preset is
  `dialect-reference-form`, and an `artifact` on one is `artifact-forbidden`: a named preset waits
  for the separately adopted contract RFC 0021's unresolved question names;
- every source that has an unbound form under RFC 0018 §4.4 is unbound: an `operation` names its
  catalog `platform`, `operation`, `shape` and `record` and no profile, and a `research` source
  names its `model` and `capabilities` and none of `profile`, `profileDigest` and `webProfiles`. A
  bound one is refused as `bound-derivative`;
- its directory holds exactly `entry.json`, `dialect.json` and `README.md`, with no other file or
  directory: no fixture directory and no binding document;
- its `requires` names no profile: `inputProfile` and `connectionProfile` are absent.

A missing or unknown `kind`, a wrong direction for a preset, a pack or fixtures on a preset, or a
non-empty preset `verification` refuses the entry. The catalog checks a preset's entry and manifest
form, its document's form, its file and canonical digests, and the scans, and nothing else: there
are no fixtures to replay and no preparation-verification record to add. These checks establish
only the recipe's identity and form; never a preparation, a pack fit, an acquisition or an answer.
The specification's preparation verifier is not used for a preset: it needs fixture inputs, and a
binding document for every unbound source. The format carries no budget; a README may describe one,
and a research source's `constraints` is part of the request, not a budget. Nothing in a preset
grants an execution permission.

## Authoring metadata

`description`, `compatibility` and `upgrade` are optional members of `entry.json`, included in its
`entryDigest` when present. `description` says what the entry is for; `compatibility` names the desk
and runner releases its author says it fits; `upgrade` gives review notes keyed by the previous
entry's digest, the manifest's `entryDigest`, not a dialect digest. These are authoring statements,
not verification records or permissions. The catalog's tests hold them since
judgment-pack-exchange#6.

**Upgrade keys.** Each `upgrade` key equals the `entryDigest` of the row with this entry's `id` in
the manifest of some release of this catalog lower in tag order (by the three integer components)
than the release being made. CI fetches the catalog's tags and refuses a key found in none of those
rows. A catalog with no earlier release admits no `upgrade`. A pull request is compared against the
releases that exist when it is checked. For this check the earlier manifest's rows are read for
their `id` and `entryDigest` whatever their form, entry format version 1 included; that manifest is
not imported as version 2. A digest of unpublished intermediate bytes, or of another entry's bytes,
is not such a key. A verification record changes `entryDigest`, so an upgrade note names the
released entry's stored bytes, even when its dialect is unchanged.

An absent `compatibility` makes no compatibility statement; an absent `upgrade`, or no note for the
previous digest, supplies no upgrade guidance. None of these absences approves an import or an
upgrade ([the release contract](release-contract.md#compatibility-is-advice)).

## The members

Every member and nested object of `entry.json` has a type, a requiredness, a grammar or a set of
allowed values, and a bound. Conditional members are absent outside their condition:

| Member | Type | Required | Grammar, allowed values and bound |
| --- | --- | --- | --- |
| `entryVersion` | integer | yes | `3` |
| `kind` | string | yes | `dialect` or `preset` |
| `id` | string | yes | `^[a-z0-9]+(\.[a-z0-9-]+)+$`, 3 to 128 characters, equal to the entry's path under `entries/` with `/` read as `.`: `entries/<publisher>/<name>/` holds the id `<publisher>.<name>` |
| `title` | string | yes | 1 to 200 characters |
| `description` | string | no | 1 to 4096 characters |
| `compatibility` | object, closed | no | exactly `desk` and `runner` |
| `compatibility.desk` | string | with `compatibility` | 1 to 64 characters; a release tag or range, as [defined below](#release-tags-and-compatibility-ranges), naming the releases of any desk that reads catalogs |
| `compatibility.runner` | string | with `compatibility` | 1 to 64 characters; a release tag or a range of release tags, as [defined below](#release-tags-and-compatibility-ranges) |
| `upgrade` | object keyed by entry digest | no | 1 to 32 members; each key the `entryDigest` of this entry's row in an earlier release's manifest ([upgrade keys](#authoring-metadata)), each value a note below |
| `upgrade.<entryDigest>` | string | for each key in `upgrade` | 1 to 2048 characters: notes for review when moving from that entry digest to this entry |
| `direction` | string | yes | `input`, `output` or `both`; exactly `input` for a preset |
| `pack` | object, closed | for kind `dialect`; absent for `preset` | `id`, and exactly one of `versions` and `digests` |
| `pack.id` | string | with `pack` | an absolute URI (Core §4), at most 2048 characters |
| `pack.versions` | string | exactly one of the two | 1 to 64 characters, in the pack's own versioning; a range syntax is an unresolved question (2) |
| `pack.digests` | array of strings | exactly one of the two | 1 to 16 `sha256:` digests |
| `dialect` | object, closed | for `input` and `both`; absent for `output` | `path`, exactly one of `dialectVersion` and `formatVersion`, and `digest` ([named artifacts](#named-artifacts)) |
| `dialect.path` | string | with `dialect` | the literal `dialect.json` |
| `dialect.dialectVersion` | integer | for an integer-format document | 2 or more, exactly 3 for a preset, equal to the dialect document's integer `version` |
| `dialect.formatVersion` | string | for a named-format document of kind `dialect`; never for a preset | exactly `"2.0.0"` or `"3.0.0"`, the document's own selector |
| `dialect.digest` | string | with `dialect` | a `sha256:` digest, of the whole document's canonical bytes, identity members included |
| `artifact` | object, closed | exactly for a named-format input document of kind `dialect`; absent for an integer-format document, a preset or an output-only entry | exactly `id` and `version`, equal as JSON string values, with no normalization, to the document's root members |
| `artifact.id` | string | with `artifact` | non-empty, at most 1024 UTF-8 bytes, with no ASCII control character, space or DEL; separate from the entry's `id` |
| `artifact.version` | string | with `artifact` | `(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)` in its entirety, Core's three-component grammar: no suffix, no leading zero, never a number |
| `output` | object, closed | for `output` and `both`; absent for `input` | `path`, `outputVersion` and `digest` |
| `output.path` | string | with `output` | the literal `output.json` |
| `output.outputVersion` | integer | with `output` | 1 or more, equal to the integer the output document's own `outputVersion` spells |
| `output.digest` | string | with `output` | a `sha256:` digest |
| `requires` | object, closed | yes | its members optional |
| `requires.inputProfile` | string | no; absent for a preset | a `sha256:` digest |
| `requires.connectionProfile` | string | no; absent for a preset | a `sha256:` digest |
| `requires.platform` | string | no | `^[a-z][a-z0-9-]*$`, at most 64 characters |
| `sourceKinds` | array of strings | yes | 1 to 16, distinct (empty for `output`), each a kind RFC 0018 lists for the document's family (§4 there), and together the kinds the document's sources use: `formatVersion` `"2.0.0"` uses version 2's list and `"3.0.0"` version 3's; a `dialectVersion` above 3 is read with version 3's list until a later RFC defines more |
| `licence` | string | yes | one SPDX licence identifier matching `[A-Za-z0-9][A-Za-z0-9.+-]*`, or a `LicenseRef-` form of that grammar; no compound licence expressions; at most 64 characters |
| `author` | string | yes | 1 to 100 characters |
| `assertion` | string | yes | the fixed sentence (below), byte for byte; for a preset it remains the author's statement, and no preparation or pack fit is verified by it |
| `fixtures` | array of closed objects | for kind `dialect`; absent for `preset` | 1 to 64 (empty for `output`) |
| `fixtures[].name` | string | yes | `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 64 characters, distinct within the entry |
| `fixtures[].path` | string | yes | `fixtures/<name>` |
| `fixtures[].preparationDigest` | string | yes | a `sha256:` digest |
| `verification` | array of closed objects | yes | at most 32; empty until verified; exactly `[]` for a preset |
| `verification[].date` | string | yes | `YYYY-MM-DD` |
| `verification[].runner` | string | yes | a release tag, in the grammar below |
| `verification[].runtime` | string | yes | a release tag, in the grammar below |
| `verification[].readers` | array of strings | yes | 1 to 8, each a [reader locator](#reader-locators), at most 200 characters |
| `verification[].result` | string | yes | `agree` |

`entry.json` and `README.md` are each at most 64 KiB, and a fixture directory at most 16 MiB;
`dialect.json` is at most 131,072 bytes, RFC 0018 §12's bound, which the catalog's form checker holds
([below](#the-catalogs-form-checker)). Every object is closed: a member the table does not list is
refused. A member name given twice in one object is refused, as Core §2.1 refuses one. The 64 KiB
file bound governs even when every member is within its individual bound; the maxima are not a
promise that all maximum-length values fit together.

## Reader locators

A reader in `verification[].readers` is `<owner>/<name>/<path>@<commit>`. Owner and name are each 1
to 100 characters of `[A-Za-z0-9_.-]`. The path has one or more `/`-separated segments, each matching
`[A-Za-z0-9_.-]+`, with no empty, `.` or `..` segment. The commit is 7 to 40 lower-case hexadecimal
digits, and the last `@` separates it from the locator. The whole locator is at most 200
characters; a wrong form or an exceeded bound refuses the verification record and its entry. For
example: `Judgment-Pack/judgment-pack-runner/cmd/verify-run@82116bf`.

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
closed object with exactly `id`, `kind`, `path`, `entryDigest`, `fixtures`, and `dialectDigest` and
`outputDigest` when the entry's direction requires them. Duplicate member names are refused. Rows
have distinct `id` values and are ordered by those ids as byte strings (their UTF-8 bytes). The `id`
has the grammar and bound in the members' table; `kind` is `dialect` or `preset` and equals the
entry's; each digest has the form given below. The row's `path` is exactly
`entries/<publisher>/<name>`, without a trailing slash: split `id` at its first `.` for
`<publisher>` and `<name>`, leaving any further dots in `<name>`. A path that differs, or an entry
whose `id` differs from the row's, is refused. There is exactly one row per entry directory in the
release's tree and one entry per row.

The row's `fixtures` is an array of closed `{name, files}` objects, one per fixture in `entry.json`
in the same order (empty for an output-only entry or a preset, whose `entry.json` omits `fixtures`).
A wrong or mismatched `kind`, or a non-empty preset fixture list, refuses the row. Each `name` equals
that fixture's name, and `files` is an array of 3 to 5 distinct strings listing its complete file set
by basename. `case.json`, `profiles.json` and `preparation.json` are required; `sources.json` is
optional; `binding.json` is required exactly when the entry's dialect has an unbound source under
RFC 0018 §4.4, including round 8's research form:

- an `operation` is unbound when it has all of `platform`, `operation`, `shape` and `record`, and
  neither binding member `profile` nor `profileDigest`. Its bound form has both binding members and
  none of those four catalog members. Some but not all of either set, a mixture of the two forms, or
  neither complete form is `input-malformed`;
- a `research` source is unbound when it has none of the binding members `profile`,
  `profileDigest` and `webProfiles`; its bound form has all three. Some but not all of that set, or
  any operation catalog member, is `input-malformed`.

The catalog's own test checks this classification and the binding members' forms for every fixture,
whether or not the preparation verifier reads it. It also checks each binding document's form,
bound, dialect digest and exact source assignments under RFC 0018 §4.4. A partial or malformed
binding document is refused. A fixture lacking a required binding document, or carrying one when the
dialect has no unbound source, is refused. No other file is admitted in a fixture directory. A
consumer knows from this list which files to fetch under `<path>/fixtures/<name>/` over any
transport; a listed file that cannot be fetched is a failure, not an absent optional file. The list
equals the file set in the release's tree.

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
  as RFC 0018 §1 writes one. `dialect.digest` is the digest of the published document's `canon`
  bytes (RFC 0018 §1, §2 and RFC 0021's §2.1 amendment), including all identity members of a
  named-format document, without projecting it into an integer format. A preparation carries the
  bound dialect's digest as `mappingDigest`
  (§9.1 there); binding an unbound document changes that digest (§4.4 there). A preset has no
  preparation or `preparationDigest`. The manifest's `entryDigest` and `dialectDigest`, and a
  fixture's `preparationDigest`, are digests of the files' bytes as stored. A `dialect.json` stored
  in bytes other than its `canon` form, indented say, has a `dialectDigest` other than its
  `dialect.digest`, and each is held to its own definition. `preparation.json` holds the
  preparation's canonical bytes (RFC 0018 §9.5), so its `preparationDigest` is the preparation's
  digest.
- **A fixture's files.** A fixture directory holds `case.json`, the case document; `sources.json`,
  the acquisitions, optional and absent for a case-only fixture; `profiles.json`, the input profiles
  the fixture was prepared under; `preparation.json`; and, exactly for a dialect with an unbound
  source, `binding.json`, the binding document the fixture was recorded under (RFC 0018 §4.4). This
  file set is closed and listed in the manifest row as above. A verifier reads these inputs under
  RFC 0018 §11, with the dialect taken from the entry's `dialect.json`. A fixture's `path` is
  `fixtures/<name>`, relative to the entry's directory. For a `research` source, `sources.json` holds
  the research record as the acquisition's result under RFC 0018 §4.3; each retained response is
  held by its own receipt and digest, and the whole record's receipt is present only when it came
  through a gateway source. Every fixture published with an entry that has a `research` source is
  synthetic (RFC 0019 §6, after RFC 0018's round-8 Security and privacy rule): its records are
  made for the purpose, never recorded from a real person, customer or account.

## The catalog's form checker

Every `dialect.json`, of an entry of kind `dialect` or `preset`, is held to the whole document form
of RFC 0018 §§2–8 and 12 through round 11 and RFC 0021's §2.1 amendment by the catalog's own form
checker, [`tests/dialect_form.py`](../tests/dialect_form.py), whether or not any fixture is
replayed: a `dialect` entry whose every fixture the verifier skips is still form-checked. The
checker is written from the dialect's companion text, `spec/dialect.md` (at judgment-pack-spec
`00c21b5`, and its §2.1 as RFC 0021 adds it); it imports and runs nothing of the specification's
readers, and has its own tests on hand-written documents
([`tests/test_dialect_form.py`](../tests/test_dialect_form.py)). A malformed document, a bound
exceeded, or a version or source kind the checker does not read refuses the entry; a digest and the
scans cannot stand in for it.

The cases it holds:

- **Bytes and reading** (§1, §12): at most 131,072 bytes, 64 levels of nesting, number literals of
  at most 128 characters with an exponent of at most 308, measured before the document is read; one
  JSON value read strictly, no member name twice, every string well-formed; the `canon` domain, so a
  number that is not an integer is refused.
- **Counts** (§12): 16 sources, 64 parameters in a scope (`runAt` included), 64 clauses, 64
  conditions in one `all` or `any`, four `unwrap` pointers, 256 fact targets and 128 evidence
  targets; for research, 64 fields, field names of 64 UTF-8 bytes, descriptions of 2048, a model of
  256, evidence instructions of 4096, three capabilities, two web assignments and 15 earlier sources
  in a reconciliation. Over a maximum is `input-over-bound`.
- **The document** (§2): its closed members; version 2's `provider`, `facts` and `evidence`; version
  3 written one way, with no member of version 2 alone and no optional array or object written
  empty where the encoding omits it.
- **The named formats** (§2.1): `formatVersion` exactly `"2.0.0"` or `"3.0.0"`, any other selector
  refused and no legacy format guessed; `id` a non-empty string of at most 1024 UTF-8 bytes with no
  ASCII control character, space or DEL; `version` a string of Core's three components, with no
  leading zero and no suffix; the rest of the document in the selected family's forms, version 3's
  encoding rule over the whole document in both formats, and family 2 without unbound or research
  sources. An integer-format document carries neither `formatVersion` nor `id`.
- **The case and parameters** (§3): case and source parameters, their types and scopes, `runAt`
  reserved, a source parameter from an earlier source's fact target.
- **Sources** (§4): names, kinds of the version; `operation` bound and, in version 3, unbound, with
  §4.4's classification, profile and catalog members, `maxAge`, templates (`$param`, `$text` and its
  placeholders) and calculations (§7); `selected-file` of provider `local-file` or `google-drive`;
  `research` of round 8: the question as a string template, constraints, model, evidence, requested
  fields of the six types, capabilities in order, and the bound or unbound profile assignments;
  `http`, `sql` and `web` of version 3, with `profile`, `profileDigest` and `maxAge` and the
  members §4.3 gives each (an `http` `method` of `GET` or `POST`, its `path` and `query` members as
  string templates, no `body` beside `GET`, `headers` as header names; a `sql` `statement` as a
  string, never a template, and `bindings` of `{name, type, value}` with a `$param` value; a `web`
  `url` as a string or a `$param` naming a string parameter). Where §4.3 names a member without a
  form, the checker takes the form a path or a name has: `http`'s `path` a string template, its
  `headers` and a `sql` binding's `name` and `type` non-empty strings.
- **Reads** (§6): `unwrap`, copies and derivation rules with every condition and claim form; every
  `unwrap`, copy and rule pointer of a plain research read on §4.3's closed list, whatever else the
  read carries (descendants admitted under `/fields/<name>/value` alone, an observation's
  `/fields/<name>/values/<index>/value` exactly), and no value taken from under `values` by an
  `unwrap` pointer, a copy's source or a claim form's `from`; the reconciliation read of §6.4, with
  its earlier research sources, its admissible `from` pointers and its status and absence guards.
- **Targets and admission** (§8): no fact target equal to or below another, no requirement an
  evidence target of two sources, and `admits` naming only written targets.

It does not read the source kinds `http`, `sql` and `web`, which version 3 proposes: as RFC 0018 §11
orders its phases, each such source is held to its form with every other part of the document
first, and only a document whose every form holds is then refused, `kind-unread`, naming the kind.
A document of an integer dialect version other than 2 and 3 is refused, `version-unread`, naming the
version; a named document's `version` is its artifact version, never read as a dialect version.
Nothing a profile, a case, an acquisition or a binding document decides is checked by the form
checker (`profile-mismatch`, admission and the findings of RFC 0018 §11): it is given the document
alone. The specification's preparation verifier is not used for a preset.

## How this repository's tests read the format

These are the tests' readings where the RFC leaves a spelling to the implementation; the RFC
settles any that it spells out.

- A length in characters is a count of Unicode code points, as Python counts a string's length.
- Every JSON file the tests hold to a form, an earlier release's manifest and entries included, is
  read strictly: one value, no member name given twice, and none of the constants `NaN`, `Infinity`
  and `-Infinity`, which JSON does not have.
- A reader of entry format version 3 refuses an entry of any other `entryVersion` before reading
  its other members, as `entry-version-unread`, and a manifest row without `kind` as a row its
  closed form does not admit.
- Each named refusal is reported by its name, as `<code>: <detail>`. Of the reference refusals only
  the first that applies, in the order above, is reported; the entry's other members are still held
  to their own rules beside it. A preset's bound source is `bound-derivative`.
- `sourceKinds` is held to the set of kinds the document's sources use, in any order, and each kind
  to the list of the document's family when the document can be read, of the reference's otherwise.
- A preset's `requires` may name a `platform`: the RFC refuses only the profiles in it.
- A fixture's `binding.json` is held by the tests themselves, whether or not any reader can replay
  the fixture: at most 65,536 bytes (RFC 0018 §12), and, for a dialect with an unbound source, the
  form of RFC 0018 §4.4: a closed object of `dialect`, the entry's `dialect.digest`, and `sources`,
  naming each unbound source of the dialect and no other name. An `operation`'s assignment is a
  closed object of `profile`, a non-empty string, and `profileDigest`, a digest; a `research`
  source's adds `webProfiles`, a closed object assigning exactly the web capabilities (`search`,
  `page`) the source requests, each a closed `{profile, profileDigest}`.
- The upgrade-key check and the artifact-history check read the catalog's releases from its git
  tags: each tag in the release-tag grammar that resolves to a commit, an annotated tag peeled, and
  the blobs at that commit. The release being made is the tag of a run at `refs/tags/<tag>` (a tag
  push, or [`release.yml`](../.github/workflows/release.yml) calling `ci.yml`), whose earlier
  releases are the tags below it; on a branch or a pull request every release counts.
  [`ci.yml`](../.github/workflows/ci.yml) checks the repository out with `fetch-depth: 0` so the
  tags are there. A shallow clone may omit release history and tags, so its tag listing counts as
  one that cannot be read; so does a tree outside a git checkout. When the tags cannot be read, an
  entry with `upgrade` is refused, and the whole release is refused as `artifact-history-invalid`,
  whether or not it holds a named entry: neither check falls back to form alone.
- The artifact-history check holds an earlier manifest to its own row form: version 1's rows,
  without `kind`, when none of its rows has one, and otherwise the row form of versions 2 and 3. It
  is read within 1 MiB and 1,024 rows, and each entry a row pins within 64 KiB, its size taken
  before it is read. An earlier entry is malformed when it is not one JSON object with an integer
  `entryVersion`, or when, of version 3 with a `formatVersion` reference, its `dialect` or
  `artifact` breaks the forms above, its `artifact` is missing or its kind is not `dialect`. The
  check reports each refused release, and each current entry whose pair an earlier release published
  with another canonical digest, naming the release and the earlier entry.
- The examples under `tests/fixtures/` stand for an example catalog whose earlier release, `v0.1.0`,
  of entry format version 1, is under [`tests/fixtures/releases/`](../tests/fixtures/releases/); an
  example that holds its own earlier releases does so under `releases/<tag>/` beside its manifest,
  standing for that catalog's tags. The git reading itself is tested on scratch repositories the
  tests build, a shallow clone of one among them, with no network.
- The manifest is read within its bound: the file's size is taken first, a file over 1 MiB is
  refused before any byte of it is read or parsed, and otherwise exactly its size is read. A
  manifest over 1,024 rows is refused as a whole, with no row read further. The order of the names
  in a fixture's `files` is not prescribed; the examples list them in byte order.
- A release tag and a compatibility value are checked by `release_tag_ok` and `compatibility_ok` in
  [`tests/test_entries.py`](../tests/test_entries.py); [`release.yml`](../.github/workflows/release.yml)
  holds a release's own tag to the same function.
- Every value of an output document's `policies` is held to the decision-policy form of RFC 0018 §10 and the gateway's `docs/design/engine-config.md` (`decisionPolicy`, at v0.15.0): a closed object, `outcomes` required, `packs`, `reviewed`, `bind`, `fix`, `closed` and `requireSignedRecord` optional and of the gateway's types, every `argument` and `fact` an RFC 6901 pointer.
- The preparation verifier the tests run is `tools/dialect_verify.py` at the specification commit
  `ci.yml` pins, `4bec33a`, a reader of rounds 8 to 16: dialect versions 2 and 3, the named Dialect
  artifact formats of RFC 0021 (`formatVersion` `"2.0.0"` or `"3.0.0"` with `id` and `version`), the
  source kinds `operation` and `research`, the name an unbound operation's `record` carries (round
  10), and the fixture's own `binding.json` for an unbound source (RFC 0019 §4); since round 13 the class a
  binding takes by kind, since round 14 the `record` profile a Drive selected-file requires, and since
  round 15 the `endpointScope` an input profile may carry, and since round 16 the path form a scoped
  page URL and each `endpointScope` prefix must keep (no escaped slash or backslash, no dot segment
  before a parameter delimiter). The digest the
  tests compare with `dialect.digest` is the document's `canon` bytes, identity members included,
  and one test holds it equal to the pinned verifier's own canonical form of each named example.
  After the form checker passes, a fixture of a dialect with a research source, of version 3 or of a
  named format is replayed by the verifier like any other: the test gives it the fixture's
  `sources.json` and `binding.json` when it has them, and requires a reading whose digest is the
  `preparationDigest`. A fixture it refuses as `kind-unread` (a source of kind `http`, `sql`, `web`
  or `selected-file`, which it defines and does not read) or as `version-unread` is skipped with a
  reason naming the kind or the version, and is held by its digests, its classification and its
  binding document only. Any other refusal, `input-malformed` included, and any finding, is a
  failure. The specification commit is named in `ci.yml`, in `CONTRIBUTING.md` and in the test's
  `READER` constant, and one test holds the three equal.
- For fixture replay, the catalog relies on the pinned verifier to hold `dialect.json`'s byte bound,
  and a skipped fixture establishes no verifier byte check; the catalog's form checker holds that
  bound for every `dialect.json` independently.
- The examples under [`tests/fixtures/`](../tests/fixtures/) are trees of the format's shape that
  are not entries: a passing example of each rule, a preset and the named formats `3.0.0` (bound and
  unbound) and `2.0.0` among them, one pair in two entries with one canonical digest, and under
  `refused/` one tree per refusal, each a passing example with one change, every refusal named above
  with at least one. The tests require each refused tree to produce exactly the problems listed for
  it, each problem naming the bound it fails, and each tree to have a problem no other tree
  produces; and they revert each tree's one change in a scratch copy, removing the earlier releases
  a tree holds of its own, and require the result to pass and to equal its passing example byte for
  byte.

## What the tests do about credentials and personal data

CI refuses recognised credential shapes and local paths. A maintainer must refuse credentials and
personal data in every file before merge. The scan's silence proves nothing.

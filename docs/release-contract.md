# The release contract

This page states what a release of a catalog in the entry format is, and what a consumer — a desk,
or anything else that imports an entry — fetches, verifies and refuses before it offers an entry for
import.
[RFC 0019](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md) §7,
"A catalog's release contract", as revised by judgment-pack-spec#163, judgment-pack-spec#178 (merged
as `489f670`) and, on 2026-10-16, judgment-pack-spec#193 (merged as `8371cdb`), is the authority:
this page restates it in this repository's words, and where the two differ, the RFC is right and
this page is a bug. The revision of #178 left the manifest's bounds and this contract unchanged but
for the row's `kind`, the document form checks and the consumer's preset duties. Entry format
version 3 (#193) keeps that row form and adds the reference, artifact and history checks. The
contract is that of any catalog in the [entry format](entry-format.md), this repository included, so
a desk can consume this catalog or another one in the same format.

## A catalog and a release

- A **catalog location** is a git repository URL, or a local directory containing the catalog's git
  repository.
- A **release** is a tag resolved to the commit it names, an annotated tag peeled to its commit. A
  tag that does not resolve to a commit is refused. The tag has the
  [release-tag grammar](entry-format.md#release-tags-and-compatibility-ranges), `vMAJOR.MINOR.PATCH`.
- No branch ancestry is checked by the consumer. A producer may require the tagged commit to be on
  `main` as its own rule; this repository does, in [`release.yml`](../.github/workflows/release.yml)
  ([releasing](releasing.md)), and a consumer does not rely on that producer rule.
- The consumer reads `manifest.json` and every entry file as the blob in that commit's tree, byte for
  byte, with no conversion, including no checkout line-ending conversion. Every file it fetches
  therefore belongs to that same commit.
- The consumer retains the catalog location, the tag, the resolved commit and the manifest for the
  import. A later state of the repository does not replace what the installation imported. A tag
  that now resolves to a commit other than the one retained for that tag is refused.
- A catalog with no entries may release the empty manifest, `[]`.

## What a release pins

The manifest pins each entry by digests over the bytes as stored, and the entry pins its documents
and fixtures in turn ([the entry format](entry-format.md)):

- each row's `kind`, `dialect` or `preset`, which equals its entry's;
- the manifest's `entryDigest`, over `entry.json`; `dialectDigest`, over `dialect.json`, for an entry
  with an input dialect; and `outputDigest`, over `output.json`, for an entry with an output dialect;
- the manifest's `fixtures`, each fixture's complete file set, by basename, in `entry.json`'s order
  (`[]` for an output-only entry and for a preset);
- in `entry.json`, `dialect.digest` and `output.digest`, over the documents' canonical bytes
  (RFC 0018 §1, §2, §10, and RFC 0021's §2.1 amendment, identity members included for a named
  document), and each fixture's `preparationDigest`, over its `preparation.json` as stored;
- in `entry.json`, for a named-format document of kind `dialect`, its `formatVersion` and its
  `artifact` pair, `id` and `version`, checked against the document. The row gains no artifact
  member: the unchanged row alone supplies neither the pair nor the canonical digest.

The manifest gives no separate digest for `README.md` or for each fixture input. Those files are
fetched as blobs from the same commit, and the commit pins them.

## Who holds these duties

`tests/test_entries.py` holds this catalog's manifest, entries, fixtures and scans
([the entry format](entry-format.md)). The duties below are the consumer's, and are to be held by
the consumer's own tests. For the Desk, the repository is `Judgment-Pack/judgment-pack-desk`, tracked
by judgment-pack-desk#400:

- import replay with its own reader and the fixture's own inputs;
- refusal of lower tags and of tags moved from their retained commits;
- withdrawal: the imported commit stays and shows the withdrawal;
- review records: reviewer, time, old and new commits, and explicit approval before replacement;
- matching entry kinds in the manifest row and `entry.json`;
- the two reference forms, identity equality, changed-pair refusals, admission of identical content
  under a pair, and the stated limits of the artifact-history check;
- a preset's document-form check by its own form checker;
- refusal to run an unpaired preset.

These name the repository responsible for each duty, not a claim that an importer or its tests have
shipped. Another consumer holds each duty in its own repository's tests. The catalog's CI cannot
establish that a consumer fetched, replayed or reviewed anything.

## Before import: what a consumer verifies

The consumer performs these checks itself, independently of a catalog's CI. It fetches the release's
manifest within the bounds of 1 MiB (1,048,576 bytes) and 1,024 rows, checks its form
([the manifest](entry-format.md#the-manifest)), and checks one row per entry directory in the
commit's tree and one entry per row, distinct ids in byte order, closed rows and the exact
`id`-to-`path` match. It fetches every row's pinned `entry.json` and checks publication identity
across the release, and, for history, reads the earlier manifests it holds and fetches every entry
their rows pin as blobs at those releases' commits, within its stated `maxHistoryReleases` limit and
the file and row bounds ([artifact history](#artifact-history)). For each entry it would offer for
import, it fetches the entry's files from that release, using the manifest's fixture file lists, and
verifies:

- `entry.json` against the manifest's `entryDigest`, and its members against
  [the members' table](entry-format.md#the-members), its `id`, `kind`, direction and authoring
  metadata included, with the row's `kind` matching its `kind` and the row's path matching its `id`;
  each input dialect, of either entry kind, is held to its document's form by the consumer's own
  form checker, written to RFC 0018 through round 11 and RFC 0021
  ([the catalog's form checker](entry-format.md#the-catalogs-form-checker)), including the reference
  and artifact checks and their named refusals ([named artifacts](entry-format.md#named-artifacts));
- `dialect.json` against the manifest's `dialectDigest` over the stored bytes, and against
  `dialect.digest` over the whole document's canonical bytes (RFC 0018 §1, §2 and RFC 0021's §2.1
  amendment), identity members included for a named format, when the entry has an input dialect;
- `output.json` against `outputDigest` over the stored bytes, and against `output.digest` over the
  document's canonical bytes (RFC 0018 §10), when the entry has an output dialect;
- each fixture's `preparation.json` against its `preparationDigest`, and the fixture's closed file
  set against the manifest's list and the format, with every listed file fetched successfully and the
  source classification and binding document checked even when the preparation reader skips it;
- every pinned digest against the fetched bytes it names, the profiles and acquisitions the reader
  checks included, using canonical bytes only where that digest's definition requires them;
- each file's bounds (the entry format, and RFC 0018 §12), and every file against the credential and
  local-path scan: a recognised credential or local path refuses the entry, and the scan's silence
  establishes no absence of credentials or personal data; and
- each recomputable fixture, by replay with the consumer's own preparation reader, using the entry's
  own dialect, the fixture's own `profiles.json` and remaining inputs, and, for an unbound family-3
  dialect, that fixture's `binding.json` (RFC 0018 §4.4). The reader must return a reading with no
  finding and a digest equal to `preparationDigest`. No record is supplied, so the reading's binding
  is `not-checked`. A fixture outside the reader's supported versions or kinds is reported as not
  recomputable, with the reason, and never as a successful replay.

File digests and canonical digests are distinct checks, even when they happen to be equal. For a
fixture that is not recomputed, the checks establish only the pinned bytes, not the derivation; the
dialect's document form is checked independently. Verification runs no entry-supplied code and
re-executes no research recipe.

## Artifact history

The catalog's test and the consumer check publication identity across all rows of the release: a
pair `(artifact.id, artifact.version)` declared by two entries with different canonical
`dialect.digest`, or declared with another canonical digest than an earlier release published under
it, even by an entry since withdrawn, refuses the release as `artifact-content-changed`. Identical
content under the pair is admitted in another entry or kind, under that kind's reference rules. Each
row's pinned entry is read within the format's bounds for its `artifact` and canonical
`dialect.digest`; the row alone supplies neither.

- **The catalog's CI** fetches the catalog's tags and reads every earlier release's manifest and
  every entry its rows pin, as blobs at that release's commit. A tag listing that cannot be read, or
  a missing or malformed manifest or entry, refuses the release as `artifact-history-invalid`. The
  catalog has no form-only fallback.
- **A consumer** checks history when it holds the previous manifest, and otherwise checks form only
  and reports `artifact-history-unchecked`: that report is not a refusal, and not a proof of
  immutable history. When it holds an earlier manifest it reads every entry its rows pin as a blob
  at that release's commit; a malformed earlier manifest, or a pinned entry that is missing,
  malformed or fails its `entryDigest`, refuses the release as `artifact-history-invalid`, for the
  catalog and the consumer alike. A consumer states a `maxHistoryReleases` limit of 1 to 128
  earlier releases; a history check that would exceed it refuses the import as
  `artifact-history-invalid`.
- **Each earlier manifest** is read in its own row form, and held to the format's file and row
  bounds. Each earlier entry is checked against its row's `entryDigest` and read for its
  `entryVersion`; only an entry of version 3 with a `formatVersion` reference is held to the
  `dialect` and `artifact` forms and holds a pair. Every other entry holds none and is checked by
  its digest only: no old entry is imported as version 3, and no named identity is inferred from an
  integer-format document.

An artifact pair is never an `upgrade` key: upgrade keys remain released `entryDigest` values. A
consumer checks a key against the same entry's earlier rows when it holds the previous manifest,
and otherwise checks the key's form only, without claiming historical verification; the catalog's
CI holds every key to its earlier rows, with no form-only fallback.

Identity is not authenticity. Matching the declared pair and digest proves neither who published the
document nor permission to publish, acquire or execute, and the catalog's immutability is scoped to
that catalog and to the history checked.

## What a consumer refuses

- **The catalog's import**, when the manifest is malformed.
- **An entry**, before it is offered for import, on a failed digest, form, file-set, bound or scan
  check, its row's `kind` other than its own, its document's form, its reference and its artifact
  pair among them, and on a replay disagreement, a finding or a verifier refusal.
- **A release**, on changed content under an artifact pair (`artifact-content-changed`), and on held
  history it cannot read or that is malformed (`artifact-history-invalid`).
- **A tag** that does not resolve to a commit, and a tag that now resolves to a commit other than the
  one retained for it.
- **An update to a lower tag**, ordered by its three integer components.

## What a consumer must not do

- Run code an entry supplies. Verification runs none, and re-executes no research recipe.
- Treat an entry's requirements, display metadata or a README's suggestions as allowances. They are
  data for review. The format carries no budget; a README may describe one, and a research source's
  `constraints` is part of the request, not a budget.
- Run an unpaired preset, or treat a preset's lack of fixtures as a successful replay.
- Bind a connection, call a source, schedule a run or authorise a write because an entry was
  imported.
- Replay a fixture under the installation's own bindings or profiles. Replay uses the fixture's own
  binding document and profiles.
- Substitute profiles in an entry of family 2. Using one against the installation's
  sources is re-authoring, an open question (RFC 0019, Unresolved question 7).
- Let a newer tag, or an author's compatibility statement, replace the installation's review.
- Replace a named document's published digest with an installation's bound digest in its portable
  reference, or treat a bound derivative as a publication under the same pair.
- Remove or replace an imported entry silently.
- Rely on the catalog's CI in place of its own checks.

## Updates, changes and withdrawal

An **update** is an explicit, reviewed upgrade from one release to another. A lower tag is refused,
as is a moved tag, and the consumer verifies the new release as above.

An entry is **changed** if any file under its path is added, removed or differs in bytes between the
two commits, its README, fixture inputs and binding documents included, even when no pinned digest
changes. A change of entry kind or direction is a change to the entry, and is shown for review with
the changed files.

An entry absent from the new release is **withdrawn**: it stays imported at its previous commit and is
shown as withdrawn. It is not silently removed or replaced.

## Compatibility is advice

For a changed entry, the consumer shows the entry, its `compatibility` statement, and the `upgrade`
note keyed by the previously imported entry's digest, if one exists. A compatibility range that
excludes the consumer's own release informs the review and does not block the upgrade. An absent
`compatibility` makes no compatibility statement, and an absent `upgrade`, or no note for the
previous digest, supplies no upgrade guidance; none of these absences approves an import or an
upgrade. These members are the author's statements, not verification records or permissions.

An upgrade between two named releases of one artifact series shows both
`(artifact.id, artifact.version)` pairs beside their published canonical digests. Those pairs
describe the releases under review; the note's key remains the previously released entry's digest.

## Review records

The review of an update records who approved it (the reviewer's identifier), when, and both the
previously imported commit and the new one. Only that explicit approval replaces the imported entry.

## Importing enables no execution and grants no permission

Local binding means the binding document of RFC 0018 §4.4, for a family-3 dialect with unbound
sources, mapping those sources to the installation's input profiles; a fixture's replay still uses
the fixture's own binding document and profiles. An entry of family 2 is imported as published and,
where it has fixtures, re-verified under its own dialect with their own profiles; import does not
substitute profiles in it. For a named document, the installation retains the published pair and
digest, the binding and the bound document's digest (RFC 0021); the published digest is never
replaced by the bound digest in its portable reference. Import does not bind a connection, call a
source, schedule a run or authorise a write. The installation chooses its local bindings and
parameters separately, and may export its own dialect as an entry in any catalog.

## Presets

A desk importing a preset pairs its dialect with a pack locally before any run; an unpaired preset is
refused for running. It chooses parameters and, where required, binds sources under RFC 0018 §4.4.
This local pairing is not a catalog-verified preparation and adds no verification record to the
published preset. A preset's checks establish the recipe's identity and form only
([presets](entry-format.md#presets)).

## This repository's releases

This catalog is released by [`release.yml`](../.github/workflows/release.yml), as
[releasing](releasing.md) describes: a tag in the grammar, on a commit on `main`, after the `entries`
checks pass at that commit. The release carries that commit's `manifest.json`, the blob byte for
byte, and `checksums.txt`, both the subjects of a build-provenance attestation, and is published
only after a maintainer approves it. These assets are a copy for checking: a consumer following this
contract reads the manifest and the entries from the tagged commit, and can compare the copy, its
checksums and its attestation with that blob. The attestation says which workflow made the files
from which commit; it says nothing about any entry's review, and nothing here is signed by the
catalog (RFC 0019, Unresolved question 1).

This repository's tests hold the manifest and the entries a release carries to the form and bounds
above (the CI job `entries`). The consumer's own fetch, replay and update checks are the consumer's:
a desk's importer is tracked by judgment-pack-desk#400.

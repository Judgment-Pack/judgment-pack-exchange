# Example: currency conversion on an invoice, as a named artifact

**This is an example, not an entry.** It lives under `tests/fixtures/`, is in no manifest of the
Exchange, and exists so that the tests which hold an entry to its format have one to hold.

The dialect is the specification's staged `named-version-3-bound` vector
(`conformance/dialect/artifact-identity/` in the specification repository): the example entry's
currency conversion in the named format `3.0.0` of RFC 0021, with the root members `formatVersion`,
`id` and `version` and the version-3 encoding rule, its `operation` source bound to the vector's
own profile. The entry references it by `formatVersion` and carries its `artifact`, the document's
`id` and `version`, checked against the document. Its fixture is the vector's recorded records and
its `preparation.json`, byte for byte, and the specification's preparation verifier at the commit
CI pins replays it to a reading.

It asserts only what the format lets an entry assert, and nothing about any record's truth. The
artifact pair establishes the identity the document declares, nothing about its authenticity or
who may publish under it.

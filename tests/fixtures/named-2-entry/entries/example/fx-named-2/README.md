# Example: currency conversion on an invoice, in the named format 2.0.0

**This is an example, not an entry.** It lives under `tests/fixtures/`, is in no manifest of the
Exchange, and exists so that the tests which hold an entry to its format have one to hold.

The dialect is the specification's staged `named-valid` vector
(`conformance/dialect/artifact-identity/` in the specification repository): the example entry's
dialect in the named format `2.0.0` of RFC 0021, family 2's forms with the version-3 encoding rule
(no `provider`, `facts` or `evidence`). The entry references it by `formatVersion` `"2.0.0"`, its
`sourceKinds` are read against version 2's list, and it carries its `artifact`. Its fixture is the
vector's recorded records and its `preparation.json`, byte for byte, which the specification's
preparation verifier at the commit CI pins replays to a reading.

It asserts only what the format lets an entry assert, and nothing about any record's truth.

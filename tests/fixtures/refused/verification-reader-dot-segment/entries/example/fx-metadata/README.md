# Example: currency conversion with authoring metadata

**This is an example, not an entry.** It lives under `tests/fixtures/`, is in no manifest of the
Exchange, and exists so that the tests which hold the authoring metadata to its bounds have an
entry to hold.

Its dialect and fixture are the example entry's (`tests/fixtures/example-entry/`), byte for byte.
Its `entry.json` adds the three optional members of RFC 0019 §3: `description`, `compatibility`
(a range of desk releases and one runner release, as an author would state them; no desk reads a
catalog yet) and `upgrade`, one note keyed by the digest of the entry's previous bytes, the same
entry without those three members.

It asserts only what the format lets an entry assert, and nothing about any record's truth.

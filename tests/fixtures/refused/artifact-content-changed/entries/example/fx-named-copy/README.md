# Example: one named artifact in two entries

**This is an example, not an entry.** It lives under `tests/fixtures/`, is in no manifest of the
Exchange, and exists so that the tests which hold an entry to its format have one to hold.

Its `dialect.json` is the named-artifact example's, byte for byte (`tests/fixtures/named-entry/`):
the pair `(urn:judgmentpack:dialect:example, 0.1.0)` with one canonical digest. The catalog holds a
pair immutable, not unique: the same pair with the same canonical content is admitted in another
entry (RFC 0019 §3, following RFC 0021).

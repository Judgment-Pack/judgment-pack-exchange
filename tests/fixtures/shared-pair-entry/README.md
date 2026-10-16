# Example: one named artifact in two entries

**An example, not an entry.** `entries/example/fx-named/` and `entries/example/fx-named-copy/`
here are two entries of entry format version 3 holding the same named document, so the same
`artifact` pair with the same canonical digest, which the format admits. Nothing here is published
by the Exchange, and the repository root's `manifest.json` does not list it.

Every identifier, record and key in this tree is synthetic, and no live service was asked: the
records and receipts are those of the specification's staged vectors, written by the Runner's
tests against a stand-in of a gateway in the test's own process and signed with keys made for that
run.

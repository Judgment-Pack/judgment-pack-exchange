"""Holds the Exchange's manifest, entries and fixtures to the entry format (docs/entry-format.md).

Standard library only. The repository's own tree (entries/ and manifest.json) is held to every
rule; the examples under tests/fixtures/ are trees of the same shape, so the rules that need an
entry are exercised while the Exchange holds none. Entry format version 2 (RFC 0019 §3, as revised
by judgment-pack-spec#178): every entry has a `kind`, `dialect` or `preset`, and every dialect
document is held to its form by the catalog's own form checker (tests/dialect_form.py).
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

# The catalog's own form checker sits beside this file; discovery from tests/ finds it, and so does a run
# that names the module from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialect_form  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "tests" / "fixtures" / "example-entry"
SPEC = ROOT / ".spec"
VERIFIER = SPEC / "tools" / "dialect_verify.py"

ASSERTION = (
    "The author asserts that these rules derive these facts and this evidence-availability from "
    "records of that shape, or these arguments from that disposition, and asserts nothing about "
    "any record's truth."
)
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
ID = re.compile(r"[a-z0-9]+(\.[a-z0-9-]+)+")
PLATFORM = re.compile(r"[a-z][a-z0-9-]*")
FIXTURE_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# RFC 0019 §3: entry format version 2, whose entries have a kind.
ENTRY_VERSION = 2
ENTRY_KINDS = ("dialect", "preset")
# A preset's directory holds exactly these files (RFC 0019 §3).
PRESET_FILES = ("README.md", "dialect.json", "entry.json")
# RFC 0019 §3: a release tag is vMAJOR.MINOR.PATCH in ASCII digits, with no leading zeroes and nothing
# after. [0-9] is ASCII in Python's re, where \d is not.
TAG = r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
RELEASE_TAG = re.compile(TAG)
# A compatibility range: `>=` the lower tag, exactly one space, `<` the upper tag.
COMPATIBILITY_RANGE = re.compile(f">=({TAG}) <({TAG})")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LICENCE = re.compile(r"LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9][A-Za-z0-9.+-]*")
# RFC 0018 §4: the kinds of each dialect version (version 3 adds to version 2; later versions are read as 3).
KINDS_V2 = {"operation", "selected-file"}
KINDS_V3 = KINDS_V2 | {"http", "sql", "web", "research"}
MAX_TEXT_FILE = 64 * 1024
MAX_FIXTURE_DIR = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MANIFEST_ROWS = 1024
# A fixture directory's closed file set (RFC 0019 §3): these three always; sources.json optional;
# binding.json exactly when the entry's dialect has an unbound source (RFC 0018 §4.4).
FIXTURE_FILES = {"case.json", "profiles.json", "preparation.json"}
FIXTURE_FILES_OPTIONAL = {"sources.json", "binding.json"}
BINDING = "binding.json"
# RFC 0018 §12: a binding document is at most 65,536 bytes.
MAX_BINDING_BYTES = 65536
# A reader's locator, `<owner>/<name>/<path>@<commit>` (RFC 0019 §3, the grammar #166 settled): owner
# and name 1 to 100 of [A-Za-z0-9_.-]; one or more path segments of [A-Za-z0-9_.-]+, none `.` or `..`.
OWNER_OR_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}")
SEGMENT = re.compile(r"[A-Za-z0-9_.-]+")
COMMIT = re.compile(r"[0-9a-f]{7,40}")
READER = "Judgment-Pack/judgment-pack-spec/tools/dialect_verify.py@18aef51aa66a012e96cf9395471109bd77e037db"
ABSOLUTE_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]+")
SKIPPED_DIRS = {".git", ".spec", ".venv", "node_modules", "__pycache__"}
# The earlier releases of the example catalog the trees under tests/fixtures/ stand for, one directory
# per tag, each holding that release's manifest.json (the upgrade-key check, RFC 0019 §3).
EXAMPLE_RELEASES = ROOT / "tests" / "fixtures" / "releases"


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canon(value) -> bytes:
    """RFC 0018 §1's `canon` for the values a dialect holds (integers, no floats)."""

    def check(v):
        if isinstance(v, float):
            raise ValueError("a number that is not an integer has no canon form")
        if isinstance(v, dict):
            for x in v.values():
                check(x)
        elif isinstance(v, list):
            for x in v:
                check(x)

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_strict(data: bytes):
    def no_duplicates(pairs):
        names = [k for k, _ in pairs]
        if len(names) != len(set(names)):
            raise ValueError("a member name is given twice")
        return dict(pairs)

    return json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)


def read_manifest(path: Path):
    """The manifest, read within its bound (RFC 0019 §3). The open file's size is taken first; a file over
    1 MiB is refused before any byte is read or parsed, and otherwise exactly its size is read."""
    with path.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if size > MAX_MANIFEST_BYTES:
            raise ValueError(f"{size} bytes, over 1 MiB (1,048,576 bytes)")
        data = handle.read(size)
    return load_strict(data)


class Tree:
    """A manifest and the entries under it: the repository's, or an example's.

    `releases` gives the catalog's earlier releases for the upgrade-key check, `[(tag, manifest bytes)]`
    in tag order, or None when they cannot be read; it is called only for an entry with `upgrade`. The
    repository's tree reads them from its git tags; an example's are the example catalog's, under
    tests/fixtures/releases/.
    """

    def __init__(self, base: Path, releases=None):
        self.base = base
        self.manifest_path = base / "manifest.json"
        self._releases = example_releases if releases is None else releases
        self._read = None

    def releases(self):
        if self._read is None:
            self._read = (self._releases(),)
        return self._read[0]

    def manifest(self):
        return read_manifest(self.manifest_path)

    def entry_dirs(self) -> list[Path]:
        entries = self.base / "entries"
        if not entries.is_dir():
            return []
        found = []
        for publisher in sorted(p for p in entries.iterdir() if p.is_dir()):
            for name in sorted(p for p in publisher.iterdir() if p.is_dir()):
                found.append(name)
        return found


# ---------------------------------------------------------------------------------------------
# Shape checks, each returning a list of problems


def is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def is_str(v) -> bool:
    return isinstance(v, str) and v != ""


def closed(obj, required: set[str], optional: set[str], where: str) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{where}: not an object"]
    problems = []
    for name in sorted(required - obj.keys()):
        problems.append(f"{where}: missing {name}")
    for name in sorted(obj.keys() - required - optional):
        problems.append(f"{where}: unknown member {name}")
    return problems


def entry_path(entry_id: str) -> str:
    """The path an id names (RFC 0019 §3): split at its first `.`, further dots stay in <name>."""
    publisher, name = entry_id.split(".", 1)
    return f"entries/{publisher}/{name}"


def manifest_problems(manifest) -> list[str]:
    """The manifest's form (RFC 0019 §3): at most 1,024 closed rows, distinct ids in byte order."""
    if not isinstance(manifest, list):
        return ["manifest: not an array"]
    if len(manifest) > MAX_MANIFEST_ROWS:
        return [f"manifest: {len(manifest)} rows, more than 1,024"]
    problems = []
    for i, row in enumerate(manifest):
        where = f"manifest[{i}]"
        bad = closed(row, {"id", "kind", "path", "entryDigest", "fixtures"}, {"dialectDigest", "outputDigest"}, where)
        problems += bad
        if bad:
            continue
        if row["kind"] not in ENTRY_KINDS:
            problems.append(f"{where}: kind is not dialect or preset")
        elif row["kind"] == "preset":
            if row["fixtures"] != []:
                problems.append(f"{where}: a preset row's fixtures is not the empty array")
            if "outputDigest" in row:
                problems.append(f"{where}: a preset row has no outputDigest")
        if not id_ok(row["id"]):
            problems.append(f"{where}: id is not of the entry id form")
        elif row["path"] != entry_path(row["id"]):
            problems.append(f"{where}: path is not {entry_path(row['id'])}, the path its id names")
        for name in ("entryDigest", "dialectDigest", "outputDigest"):
            if name in row and not digest_ok(row[name]):
                problems.append(f"{where}: {name} is not a sha256 digest")
        problems += fixture_list_problems(row["fixtures"], where)
    ids = [r["id"] for r in manifest if isinstance(r, dict) and isinstance(r.get("id"), str)]
    in_bytes = [i.encode("utf-8", "surrogatepass") for i in ids]
    if in_bytes != sorted(in_bytes):
        problems.append("manifest: not in id byte order")
    if len(ids) != len(set(ids)):
        problems.append("manifest: an id is listed twice")
    return problems


def fixture_list_problems(fixtures, where: str) -> list[str]:
    """A row's `fixtures`: closed {name, files}; files 3 to 5 distinct names of the closed set."""
    if not isinstance(fixtures, list):
        return [f"{where}: fixtures is not an array"]
    problems = []
    for j, fixture in enumerate(fixtures):
        at = f"{where}.fixtures[{j}]"
        bad = closed(fixture, {"name", "files"}, set(), at)
        problems += bad
        if bad:
            continue
        if not is_str(fixture["name"]):
            problems.append(f"{at}: name is not a string")
        files = fixture["files"]
        if not (isinstance(files, list) and all(isinstance(f, str) for f in files)):
            problems.append(f"{at}: files is not an array of strings")
            continue
        if not 3 <= len(files) <= 5:
            problems.append(f"{at}: files lists {len(files)} names, not 3 to 5")
        for name in sorted({f for f in files if files.count(f) > 1}):
            problems.append(f"{at}: files names {name} twice")
        for name in sorted(FIXTURE_FILES - set(files)):
            problems.append(f"{at}: files lacks {name}")
        for name in sorted(set(files) - FIXTURE_FILES - FIXTURE_FILES_OPTIONAL):
            problems.append(f"{at}: files names {name}, which no fixture holds")
    return problems


def text_ok(v, low: int, high: int) -> bool:
    return isinstance(v, str) and low <= len(v) <= high


def id_ok(v) -> bool:
    return text_ok(v, 3, 128) and ID.fullmatch(v) is not None


def digest_ok(v) -> bool:
    return isinstance(v, str) and DIGEST.fullmatch(v) is not None


def release_tag_ok(v) -> bool:
    """RFC 0019 §3's release-tag grammar, ^v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$, in ASCII."""
    return isinstance(v, str) and RELEASE_TAG.fullmatch(v) is not None


def tag_order(tag: str) -> tuple[int, int, int]:
    """A release tag's three integer components, by which tags are ordered (RFC 0019 §3)."""
    major, minor, patch = tag[1:].split(".")
    return int(major), int(minor), int(patch)


def length_problem(where: str, v, low: int, high: int) -> str | None:
    """The bound a string fails, named: not a string, empty, or over its maximum by its count."""
    if not isinstance(v, str):
        return f"{where} is not a string"
    if len(v) < low:
        return f"{where} is empty" if low == 1 else f"{where} is {len(v)} characters, under {low}"
    if len(v) > high:
        return f"{where} is {len(v)} characters, over {high}"
    return None


def compatibility_problem(where: str, v) -> str | None:
    """A compatibility value (RFC 0019 §3): 1 to 64 characters, one release tag, or `>=<lower> <<upper>`
    with exactly one space and the upper tag above the lower by their integers. No other range syntax."""
    bound = length_problem(where, v, 1, 64)
    if bound:
        return bound
    if release_tag_ok(v):
        return None
    match = COMPATIBILITY_RANGE.fullmatch(v)
    if match is None:
        return f"{where} {v!r} is not a release tag or a range of release tags"
    if not tag_order(match.group(2)) > tag_order(match.group(1)):
        return f"{where} {v!r} has an upper tag not above its lower tag"
    return None


def compatibility_ok(v) -> bool:
    return compatibility_problem("value", v) is None


def reader_problems(where: str, v) -> list[str]:
    """A verification record's reader, `<owner>/<name>/<path>@<commit>` (RFC 0019 §3, reader locators): owner
    and name 1 to 100 of [A-Za-z0-9_.-]; a path of one or more `/`-separated segments, each matching
    [A-Za-z0-9_.-]+, none empty, `.` or `..`; a commit of 7 to 40 lower-case hexadecimal digits after the
    last `@`; at most 200 characters in all."""
    bound = length_problem(where, v, 1, 200)
    if bound:
        return [bound]
    locator, at, commit = v.rpartition("@")
    if not at:
        return [f"{where} {v!r} has no @<commit>"]
    problems = []
    if not COMMIT.fullmatch(commit):
        problems.append(f"{where}'s commit {commit!r} is not 7 to 40 lower-case hexadecimal digits")
    parts = locator.split("/", 2)
    if len(parts) < 2 or not all(OWNER_OR_NAME.fullmatch(p) for p in parts[:2]):
        problems.append(f"{where} {v!r} does not begin <owner>/<name>/, each 1 to 100 of [A-Za-z0-9_.-]")
    elif len(parts) < 3 or parts[2] == "":
        problems.append(f"{where} {v!r} has no path")
    elif any(segment in ("", ".", "..") for segment in parts[2].split("/")):
        problems.append(f"{where} {v!r} has an empty, '.' or '..' path segment")
    elif not all(SEGMENT.fullmatch(segment) for segment in parts[2].split("/")):
        problems.append(f"{where} {v!r} has a path segment of a character outside [A-Za-z0-9_.-]")
    return problems


def unbound_source_names(document) -> set[str]:
    """RFC 0018 §4.4 as RFC 0019 §3 settles it: an `operation` with all of platform, operation, shape and record
    and neither profile nor profileDigest, or a `research` source with none of profile, profileDigest and
    webProfiles, is unbound. A source with some but not all of either set is not unbound: the form
    checker refuses it, input-malformed."""
    return set(dialect_form.unbound_sources(document))


def has_unbound_source(document) -> bool:
    return bool(unbound_source_names(document))


def date_ok(v) -> bool:
    if not (isinstance(v, str) and DATE.fullmatch(v)):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def entry_problems(entry, directory_id: str, document_version=None, output_document_version=None) -> list[str]:
    """The entry format's types and bounds (docs/entry-format.md), version 2. Every object is closed.

    A reader of version 2 refuses any other entry format version, version 1 included, before it reads
    the entry's other members: their closed form is another one."""
    if isinstance(entry, dict) and not (is_int(entry.get("entryVersion")) and entry["entryVersion"] == ENTRY_VERSION):
        return [f"entry: entryVersion {entry.get('entryVersion')!r} is not 2; a version-2 reader refuses any other entry format version"]
    required = {
        "entryVersion", "kind", "id", "title", "direction", "requires", "sourceKinds",
        "licence", "author", "assertion", "verification",
    }
    optional = {"pack", "fixtures", "dialect", "output", "description", "compatibility", "upgrade"}
    problems = closed(entry, required, optional, "entry")
    if problems:
        return problems
    kind = entry["kind"]
    preset = kind == "preset"
    if kind not in ENTRY_KINDS:
        problems.append("entry: kind is not dialect or preset")
    elif preset:
        # RFC 0019 §3: a preset has direction input, no pack and no fixtures, an empty verification, a
        # dialect of version 3 and no profile in requires.
        for name in ("pack", "fixtures"):
            if name in entry:
                problems.append(f"entry: a preset has no {name}")
        if entry["direction"] != "input":
            problems.append(f"entry: a preset's direction is input, not {entry['direction']!r}")
        if entry["verification"] != []:
            problems.append("entry: a preset's verification is the empty array")
        if isinstance(entry.get("dialect"), dict) and entry["dialect"].get("dialectVersion") != 3:
            problems.append("dialect: a preset's dialectVersion is 3")
        if isinstance(entry["requires"], dict):
            for name in ("inputProfile", "connectionProfile"):
                if name in entry["requires"]:
                    problems.append(f"requires: a preset names no profile, and this one names {name}")
    else:
        for name in ("pack", "fixtures"):
            if name not in entry:
                problems.append(f"entry: {name} is required for kind dialect")
    if not id_ok(entry["id"]):
        problems.append("entry: id is not of the form ^[a-z0-9]+(\\.[a-z0-9-]+)+$, 3 to 128 characters")
    elif entry["id"] != directory_id:
        problems.append(f"entry: id {entry['id']} is not its path's {directory_id}")
    if not text_ok(entry["title"], 1, 200):
        problems.append("entry: title is not a string of 1 to 200 characters")
    if not text_ok(entry["licence"], 1, 64) or not LICENCE.fullmatch(entry["licence"]):
        problems.append("entry: licence is not an SPDX identifier or a LicenseRef- form of at most 64 characters")
    if not text_ok(entry["author"], 1, 100):
        problems.append("entry: author is not a string of 1 to 100 characters")
    if entry["direction"] not in ("input", "output", "both"):
        problems.append("entry: direction is not input, output or both")
    if entry["assertion"] != ASSERTION:
        problems.append("entry: assertion is not the format's sentence")

    # The authoring metadata (RFC 0019 §3): optional, and held to its bounds when present. Each
    # diagnostic names the bound it failed.
    if "description" in entry:
        bound = length_problem("entry: description", entry["description"], 1, 4096)
        if bound:
            problems.append(bound)
    if "compatibility" in entry:
        compatibility = entry["compatibility"]
        bad = closed(compatibility, {"desk", "runner"}, set(), "compatibility")
        problems += bad
        if not bad:
            for name in ("desk", "runner"):
                bound = compatibility_problem(f"compatibility: {name}", compatibility[name])
                if bound:
                    problems.append(bound)
    if "upgrade" in entry:
        upgrade = entry["upgrade"]
        if not isinstance(upgrade, dict):
            problems.append("upgrade: not an object")
        elif not upgrade:
            problems.append("upgrade has no members")
        elif len(upgrade) > 32:
            problems.append(f"upgrade has {len(upgrade)} members, over 32")
        else:
            for key, note in upgrade.items():
                if not digest_ok(key):
                    problems.append(f"upgrade: the key {key!r} is not a sha256 digest")
                bound = length_problem(f"upgrade: the note for {key!r}", note, 1, 2048)
                if bound:
                    problems.append(bound)

    pack = entry.get("pack")
    if "pack" not in entry:
        pass
    elif isinstance(pack, dict):
        problems += closed(pack, {"id"}, {"versions", "digests"}, "pack")
        if not (text_ok(pack.get("id"), 1, 2048) and ABSOLUTE_URI.fullmatch(pack["id"])):
            problems.append("pack: id is not an absolute URI of at most 2048 characters (Core §4)")
        if ("versions" in pack) == ("digests" in pack):
            problems.append("pack: exactly one of versions and digests")
        if "versions" in pack and not text_ok(pack["versions"], 1, 64):
            problems.append("pack: versions is not a string of 1 to 64 characters")
        if "digests" in pack and not (
            isinstance(pack["digests"], list)
            and 1 <= len(pack["digests"]) <= 16
            and all(digest_ok(d) for d in pack["digests"])
        ):
            problems.append("pack: digests is not an array of 1 to 16 sha256 digests")
    else:
        problems.append("pack: not an object")

    direction = entry["direction"]
    has_dialect = direction in ("input", "both")
    has_output = direction in ("output", "both")
    if direction in ("input", "output", "both"):
        if has_dialect != ("dialect" in entry):
            problems.append(f"entry: dialect is {'required' if has_dialect else 'absent'} for direction {direction}")
        if has_output != ("output" in entry):
            problems.append(f"entry: output is {'required' if has_output else 'absent'} for direction {direction}")

    version = None
    dialect = entry.get("dialect")
    if "dialect" not in entry:
        pass
    elif isinstance(dialect, dict):
        problems += closed(dialect, {"path", "dialectVersion", "digest"}, set(), "dialect")
        if dialect.get("path") != "dialect.json":
            problems.append("dialect: path is not dialect.json")
        version = dialect.get("dialectVersion")
        if not is_int(version) or version < 2:
            problems.append("dialect: dialectVersion is not an integer of at least 2")
        elif document_version is not None and version != document_version:
            problems.append("dialect: dialectVersion is not the document's own version")
        if not digest_ok(dialect.get("digest")):
            problems.append("dialect: digest is not a sha256 digest")
    else:
        problems.append("dialect: not an object")

    output = entry.get("output")
    if "output" not in entry:
        pass
    elif isinstance(output, dict):
        problems += closed(output, {"path", "outputVersion", "digest"}, set(), "output")
        if output.get("path") != "output.json":
            problems.append("output: path is not output.json")
        output_version = output.get("outputVersion")
        if not is_int(output_version) or output_version < 1:
            problems.append("output: outputVersion is not an integer of at least 1")
        elif output_document_version is not None and output_version != output_document_version:
            problems.append("output: outputVersion is not the integer the document's own outputVersion spells")
        if not digest_ok(output.get("digest")):
            problems.append("output: digest is not a sha256 digest")
    else:
        problems.append("output: not an object")

    requires = entry["requires"]
    if isinstance(requires, dict):
        problems += closed(requires, set(), {"inputProfile", "connectionProfile", "platform"}, "requires")
        for name in ("inputProfile", "connectionProfile"):
            if name in requires and not digest_ok(requires[name]):
                problems.append(f"requires: {name} is not a sha256 digest")
        if "platform" in requires and not (
            text_ok(requires["platform"], 1, 64) and PLATFORM.fullmatch(requires["platform"])
        ):
            problems.append("requires: platform is not ^[a-z][a-z0-9-]*$ of at most 64 characters")
    else:
        problems.append("requires: not an object")

    kinds = entry["sourceKinds"]
    if direction == "output":
        if kinds != []:
            problems.append("entry: sourceKinds is not an empty array for direction output")
    elif not (isinstance(kinds, list) and 1 <= len(kinds) <= 16 and all(isinstance(k, str) for k in kinds)):
        problems.append("entry: sourceKinds is not an array of 1 to 16 strings")
    else:
        if len(set(kinds)) != len(kinds):
            problems.append("entry: sourceKinds names a kind twice")
        if is_int(version) and version >= 2:
            listed = KINDS_V2 if version == 2 else KINDS_V3
            for kind in kinds:
                if kind not in listed:
                    problems.append(f"entry: sourceKinds names {kind}, not a kind of dialect version {version}")

    fixtures = entry.get("fixtures")
    if "fixtures" not in entry or preset:
        pass  # a preset's fixtures are refused above, whatever they hold
    elif isinstance(fixtures, list):
        if direction == "output":
            if fixtures:
                problems.append("entry: fixtures is not an empty array for direction output")
        elif not 1 <= len(fixtures) <= 64:
            problems.append("entry: fixtures is not an array of 1 to 64 (at least one is required)")
        names = []
        for i, fixture in enumerate(fixtures):
            where = f"fixtures[{i}]"
            bad = closed(fixture, {"name", "path", "preparationDigest"}, set(), where)
            problems += bad
            if bad:
                continue
            names.append(fixture["name"])
            if not (text_ok(fixture["name"], 1, 64) and FIXTURE_NAME.fullmatch(fixture["name"])):
                problems.append(f"{where}: name is not ^[a-z0-9]+(-[a-z0-9]+)*$ of at most 64 characters")
            if fixture["path"] != f"fixtures/{fixture['name']}":
                problems.append(f"{where}: path is not fixtures/<name>")
            if not digest_ok(fixture["preparationDigest"]):
                problems.append(f"{where}: preparationDigest is not a sha256 digest")
        if len(set(map(str, names))) != len(names):
            problems.append("entry: a fixture name is given twice")
    else:
        problems.append("entry: fixtures is not an array")

    verification = entry["verification"]
    if isinstance(verification, list):
        if len(verification) > 32:
            problems.append("entry: verification has more than 32 members")
        for i, v in enumerate(verification):
            where = f"verification[{i}]"
            bad = closed(v, {"date", "runner", "runtime", "readers", "result"}, set(), where)
            problems += bad
            if bad:
                continue
            if not date_ok(v["date"]):
                problems.append(f"{where}: date is not YYYY-MM-DD")
            for name in ("runner", "runtime"):
                if not release_tag_ok(v[name]):
                    problems.append(f"{where}: {name} {v[name]!r} is not a release tag (vMAJOR.MINOR.PATCH, ASCII, no leading zeroes)")
            readers = v["readers"]
            if not (isinstance(readers, list) and 1 <= len(readers) <= 8):
                problems.append(f"{where}: readers is not an array of 1 to 8")
            else:
                for k, reader in enumerate(readers):
                    problems += reader_problems(f"{where}: readers[{k}]", reader)
            if v["result"] != "agree":
                problems.append(f"{where}: result is not agree")
    else:
        problems.append("entry: verification is not an array")
    return problems


def size_problems(directory: Path, entry) -> list[str]:
    problems = []
    for name in ("entry.json", "README.md"):
        if (directory / name).stat().st_size > MAX_TEXT_FILE:
            problems.append(f"{name} is over 64 KiB")
    for fixture in entry.get("fixtures", []):
        total = sum(f.stat().st_size for f in (directory / fixture["path"]).rglob("*") if f.is_file())
        if total > MAX_FIXTURE_DIR:
            problems.append(f"{fixture['path']} is over 16 MiB")
    return problems


# ---------------------------------------------------------------------------------------------
# Whole-tree checks


def tree_problems(tree: Tree) -> list[str]:
    """Manifest, shape, id/path and digest checks (rules 1 to 4) over one tree."""
    problems: list[str] = []
    try:
        manifest = tree.manifest()
    except (OSError, ValueError) as error:
        return [f"manifest.json: {error}"]
    problems += manifest_problems(manifest)
    if not isinstance(manifest, list) or len(manifest) > MAX_MANIFEST_ROWS:
        return problems  # a manifest refused as a whole: nothing further is read from it
    by_path = {row["path"]: row for row in manifest if isinstance(row, dict) and isinstance(row.get("path"), str)}
    dirs = {d.relative_to(tree.base).as_posix(): d for d in tree.entry_dirs()}
    for path in sorted(dirs.keys() - by_path.keys()):
        problems.append(f"{path}: an entry the manifest does not list")
    for path in sorted(by_path.keys() - dirs.keys()):
        problems.append(f"{path}: listed in the manifest, no such entry")
    for path in sorted(dirs.keys() & by_path.keys()):
        problems += directory_problems(dirs[path], path, by_path[path], tree.releases)
    return problems


POINTER = re.compile(r"(/([^/~]|~[01])*)*")
KEY = re.compile(r"[0-9a-f]{64}")


def policy_problems(name, policy) -> list[str]:
    """One decision policy in the gateway's form (engine-config.md at v0.15.0, `decisionPolicy`)."""
    where = f"output.json: policies.{name}"
    problems = closed(policy, {"outcomes"}, {"packs", "reviewed", "bind", "fix", "closed", "requireSignedRecord"}, where)
    if problems:
        return problems

    def non_empty_distinct(member, item_ok):
        value = policy[member]
        if not (isinstance(value, list) and value and all(item_ok(v) for v in value)):
            problems.append(f"{where}: {member} is not a non-empty array of the form the gateway gives")
        elif len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            problems.append(f"{where}: {member} names an entry twice")

    def pointer_ok(v):
        return isinstance(v, str) and POINTER.fullmatch(v) is not None

    non_empty_distinct("outcomes", lambda v: isinstance(v, str) and v != "")
    if "packs" in policy:
        non_empty_distinct("packs", digest_ok)
    if "requireSignedRecord" in policy:
        non_empty_distinct("requireSignedRecord", lambda v: isinstance(v, str) and KEY.fullmatch(v) is not None)
    for member in ("reviewed", "closed"):
        if member in policy and not isinstance(policy[member], bool):
            problems.append(f"{where}: {member} is not a boolean")
    bound, fixed = [], []
    for member, other, sink in (("bind", "fact", bound), ("fix", "value", fixed)):
        if member not in policy:
            continue
        entries = policy[member]
        if not isinstance(entries, list):
            problems.append(f"{where}: {member} is not an array")
            continue
        for i, entry in enumerate(entries):
            bad = closed(entry, {"argument", other}, set(), f"{where}: {member}[{i}]")
            problems += bad
            if bad:
                continue
            if not pointer_ok(entry["argument"]):
                problems.append(f"{where}: {member}[{i}].argument is not an RFC 6901 pointer")
            elif member == "bind" and not pointer_ok(entry["fact"]):
                problems.append(f"{where}: bind[{i}].fact is not an RFC 6901 pointer")
            else:
                sink.append(entry["argument"])
    if len(set(bound)) != len(bound) or len(set(fixed)) != len(fixed):
        problems.append(f"{where}: an argument pointer is named twice")
    if set(bound) & set(fixed):
        problems.append(f"{where}: an argument pointer is both fixed and bound")
    return problems


def directory_problems(directory: Path, path: str, row: dict, releases=None) -> list[str]:
    """One entry against its manifest row: digests, the entry's form, its documents' forms, its fixtures.
    `releases` gives the catalog's earlier releases for the upgrade-key check (Tree.releases)."""
    releases = example_releases if releases is None else releases
    parts = path.split("/")
    expected_id = f"{parts[1]}.{parts[2]}"
    problems: list[str] = []
    if row.get("id") != expected_id:
        problems.append(f"{path}: manifest id {row.get('id')} is not {expected_id}")
    for name in ("entry.json", "README.md"):
        if not (directory / name).is_file():
            problems.append(f"{path}: no {name}")
    if problems:
        return problems
    entry_bytes = (directory / "entry.json").read_bytes()
    if digest(entry_bytes) != row.get("entryDigest"):
        problems.append(f"{path}: entry.json does not match the manifest's entryDigest")
    try:
        entry = load_strict(entry_bytes)
    except ValueError as error:
        return problems + [f"{path}: entry.json: {error}"]
    direction = entry.get("direction") if isinstance(entry, dict) else None
    # Which documents the entry holds follows from its direction; entry_problems refuses any other.
    documents = {
        "dialect": ("dialect.json", "dialectDigest", direction in ("input", "both")),
        "output": ("output.json", "outputDigest", direction in ("output", "both")),
    }
    canonical = {}
    form_refused = False
    for key, (name, column, wanted) in documents.items():
        present = (directory / name).is_file()
        if wanted and not present:
            problems.append(f"{path}: no {name}")
        if present and not wanted:
            problems.append(f"{path}: {name} is present in an entry of direction {direction}")
        if (column in row) != wanted:
            problems.append(f"{path}: the manifest {'lacks' if wanted else 'has'} {column} for direction {direction}")
        if not (wanted and present):
            continue
        data = (directory / name).read_bytes()
        if digest(data) != row.get(column):
            problems.append(f"{path}: {name} does not match the manifest's {column}")
        if key == "dialect":
            # RFC 0019 §§3–4: the catalog's own form checker, for either kind, replayed or not.
            refusal = dialect_form.check(data)
            if refusal:
                problems.append(f"{path}: dialect.json is refused by the catalog's form checker, {refusal[0]}: {refusal[1]}")
                form_refused = True
        try:
            canonical[key] = (load_strict(data), digest(canon(load_strict(data))))
        except ValueError as error:
            problems.append(f"{path}: {name}: {error}")
    document_version = None
    if "dialect" in canonical and isinstance(canonical["dialect"][0], dict):
        document_version = canonical["dialect"][0].get("version")
    output_version = None
    if "output" in canonical:
        document = canonical["output"][0]
        if not isinstance(document, dict) or set(document) != {"outputVersion", "platform", "policies"}:
            problems.append(f"{path}: output.json is not a closed object of outputVersion, platform and policies")
        elif not (isinstance(document["platform"], str) and document["platform"] and isinstance(document["policies"], dict)):
            problems.append(f"{path}: output.json: platform is not a non-empty string or policies is not an object")
        elif any(policy_problems(n, v) for n, v in document["policies"].items()):
            problems += [f"{path}: {p}" for n, v in document["policies"].items() for p in policy_problems(n, v)]
        elif document["outputVersion"] != "1":
            problems.append(f"{path}: output.json: outputVersion is not the string \"1\"")
        else:
            output_version = 1
    shape = entry_problems(entry, expected_id, document_version, output_version)
    problems += [f"{path}: {p}" for p in shape]
    if shape:
        return problems
    if row.get("kind") in ENTRY_KINDS and row["kind"] != entry["kind"]:
        problems.append(f"{path}: the manifest's kind {row['kind']} is not entry.json's kind {entry['kind']}")
    # What the dialect's sources are is read only from a document whose form holds.
    document = None if form_refused else canonical.get("dialect", (None,))[0]
    if entry["kind"] == "preset":
        problems += [f"{path}: {p}" for p in preset_problems(directory, document)]
    problems += [f"{path}: {p}" for p in source_kind_problems(entry, document)]
    problems += [f"{path}: {p}" for p in upgrade_history_problems(entry, releases)]
    problems += [f"{path}: {p}" for p in size_problems(directory, entry)]
    if "dialect" in canonical and canonical["dialect"][1] != entry["dialect"]["digest"]:
        problems.append(f"{path}: dialect.digest is not the digest of dialect.json's canonical bytes")
    if "output" in canonical and canonical["output"][1] != entry["output"]["digest"]:
        problems.append(f"{path}: output.digest is not the digest of output.json's canonical bytes")
    for fixture in entry.get("fixtures", []):
        prep = directory / fixture["path"] / "preparation.json"
        if not prep.is_file():
            problems.append(f"{path}: {fixture['path']} has no preparation.json")
        elif digest(prep.read_bytes()) != fixture["preparationDigest"]:
            problems.append(f"{path}: {fixture['name']}'s preparation.json does not match its preparationDigest")
    problems += fixture_set_problems(directory, path, entry, row, document)
    return problems


def preset_problems(directory: Path, document) -> list[str]:
    """RFC 0019 §3: a preset's directory holds exactly entry.json, dialect.json and README.md, and every
    source of its dialect that has an unbound form under RFC 0018 §4.4 is unbound."""
    problems = []
    for item in sorted(directory.iterdir()):
        if item.name not in PRESET_FILES or item.is_symlink() or not item.is_file():
            problems.append(f"a preset's directory holds {item.name}, and holds only entry.json, dialect.json and README.md")
    sources = document.get("sources", []) if isinstance(document, dict) else []
    for source in sources:
        if dialect_form.classification(source) == "bound":
            problems.append(f"a preset's source {source['name']!r} is bound: every source with an unbound form is unbound")
    return problems


def source_kind_problems(entry: dict, document) -> list[str]:
    """`sourceKinds` names the source kinds the dialect uses (RFC 0019 §3), as a set."""
    if not isinstance(document, dict):
        return []
    used = sorted({s["kind"] for s in document.get("sources", [])})
    if sorted(set(entry["sourceKinds"])) != used:
        return [f"sourceKinds is {', '.join(entry['sourceKinds'])}; the document's sources are of {', '.join(used) or 'no kind'}"]
    return []


def fixture_set_problems(directory: Path, path: str, entry: dict, row: dict, dialect_document) -> list[str]:
    """Each fixture directory against its row's file list and the closed set (RFC 0019 §3)."""
    listed = row.get("fixtures")
    if not isinstance(listed, list):
        return []  # the manifest's form refuses the row (manifest_problems)
    names = [fixture["name"] for fixture in entry.get("fixtures", [])]
    listed_names = [f.get("name") if isinstance(f, dict) else None for f in listed]
    if listed_names != names:
        return [
            f"{path}: the manifest's fixtures are {', '.join(map(str, listed_names)) or 'none'}, "
            f"not entry.json's {', '.join(names) or 'none'} in its order"
        ]
    problems = []
    unbound = has_unbound_source(dialect_document)
    for fixture, listing in zip(entry.get("fixtures", []), listed):
        where = f"{path}: {fixture['path']}"
        held = directory / fixture["path"]
        if not held.is_dir():
            problems.append(f"{where} is not a directory")
            continue
        held_names = set()
        for item in sorted(held.iterdir()):
            held_names.add(item.name)
            if item.is_symlink() or not item.is_file():
                problems.append(f"{where} holds {item.name}, which is not a file")
        files = listing.get("files")
        if not (isinstance(files, list) and all(isinstance(f, str) for f in files)):
            continue  # the row's form is refused by manifest_problems
        for name in sorted(held_names - set(files)):
            problems.append(f"{where} holds {name}, which the manifest's file list does not name")
        for name in sorted(set(files) - held_names):
            problems.append(f"{where} has no {name}, which the manifest's file list names")
        if dialect_document is None:
            continue  # no dialect whose form holds: its sources are not classified (the form check refuses it)
        if unbound and BINDING not in files:
            problems.append(f"{where}: binding.json is required: the dialect has an unbound source")
        if BINDING in files and not unbound:
            problems.append(f"{where}: binding.json is refused: the dialect has no unbound source")
        if (held / BINDING).is_file() and not (held / BINDING).is_symlink():
            problems += binding_problems(f"{where}: binding.json", held / BINDING, entry, dialect_document)
    return problems


def binding_problems(where: str, path: Path, entry: dict, dialect_document) -> list[str]:
    """A fixture's binding document, held by the catalog itself and not only by a replay: its byte bound
    (RFC 0018 §12, 65,536 bytes inclusive) always, read no further when over it; and, for a dialect with
    an unbound source, its form (RFC 0018 §4.4): a closed object of `dialect`, the entry's dialect digest,
    and `sources`, naming each unbound source of the dialect and no other name. An `operation`'s
    assignment is a closed `{profile, profileDigest}`; a `research` source's a closed
    `{profile, profileDigest, webProfiles}`, `webProfiles` assigning exactly the web capabilities the
    source requests, each a closed `{profile, profileDigest}`."""
    size = path.stat().st_size
    if size > MAX_BINDING_BYTES:
        return [f"{where} is {size} bytes, over 65,536"]
    unbound_sources = dialect_form.unbound_sources(dialect_document)
    unbound = set(unbound_sources)
    if not unbound:
        return []
    try:
        binding = load_strict(path.read_bytes())
    except ValueError as error:
        return [f"{where}: {error}"]
    problems = closed(binding, {"dialect", "sources"}, set(), where)
    if problems:
        return problems
    if not (digest_ok(binding["dialect"]) and binding["dialect"] == entry["dialect"]["digest"]):
        problems.append(f"{where}: dialect is not the entry's dialect digest")
    sources = binding["sources"]
    if not isinstance(sources, dict):
        return problems + [f"{where}: sources is not an object"]
    for name, value in sources.items():
        if name not in unbound:
            problems.append(f"{where}: sources names {name!r}, which is not an unbound source of the dialect")
        source = unbound_sources.get(name, {})
        research = source.get("kind") == "research"
        members = {"profile", "profileDigest", "webProfiles"} if research else {"profile", "profileDigest"}
        bad = closed(value, members, set(), f"{where}: sources.{name}")
        problems += bad
        if bad:
            continue
        problems += assignment_problems(f"{where}: sources.{name}", value)
        if research:
            web = value["webProfiles"]
            capabilities = source.get("capabilities") if isinstance(source.get("capabilities"), list) else []
            requested = {c for c in capabilities if c in ("search", "page")}
            if not isinstance(web, dict):
                problems.append(f"{where}: sources.{name}: webProfiles is not an object")
                continue
            if set(web) != requested:
                problems.append(
                    f"{where}: sources.{name}: webProfiles assigns {', '.join(sorted(web)) or 'nothing'}, not exactly the web "
                    f"capabilities the source requests ({', '.join(sorted(requested)) or 'none'})"
                )
            for capability, assignment in sorted(web.items()):
                at = f"{where}: sources.{name}.webProfiles.{capability}"
                bad = closed(assignment, {"profile", "profileDigest"}, set(), at)
                problems += bad or assignment_problems(at, assignment)
    for name in sorted(unbound - sources.keys()):
        problems.append(f"{where}: sources does not name the unbound source {name!r}")
    return problems


def assignment_problems(where: str, value: dict) -> list[str]:
    problems = []
    if not is_str(value["profile"]):
        problems.append(f"{where}: profile is not a non-empty string")
    if not digest_ok(value["profileDigest"]):
        problems.append(f"{where}: profileDigest is not a sha256 digest")
    return problems


def load_verifier():
    spec = importlib.util.spec_from_file_location("dialect_verify", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dialect_verify"] = module
    spec.loader.exec_module(module)
    return module


def verifier_answer(result: subprocess.CompletedProcess) -> dict:
    """The verifier's report (RFC 0018 §11: one object whose `result` is `reading`, `refusal` or `finding`) as
    the catalog reads it: {"reading": {...}}, {"refused": name, "detail": ...} or {"finding": name, "detail": ...}.
    The reason for a refusal or a finding is on the verifier's standard error; its exit status is 0 for a
    reading, 1 for a refusal, 2 for a finding, and 3 when it could not run (and printed no report)."""
    report = json.loads(result.stdout)
    status = {"reading": 0, "refusal": 1, "finding": 2}.get(report.get("result"))
    if status is None or status != result.returncode:
        raise ValueError("the report and the exit status disagree")
    detail = result.stderr.strip()
    if report["result"] == "reading":
        return {"reading": {k: v for k, v in report.items() if k != "result"}}
    if report["result"] == "refusal":
        return {"refused": report["refusal"], "detail": detail}
    return {"finding": report["finding"], "detail": detail}


def verifier_results(tree: Tree) -> list[tuple[str, str, str]]:
    """(label, "ok" | "skip" | "problem", message) for each fixture of each entry in the tree.

    The verifier reads dialect versions 2 and 3, the source kinds `operation` and `research` (a research
    source with the fixture's `sources.json` and, for an unbound source, its `binding.json`), and holds the
    kinds `http`, `sql` and `web` to their forms and refuses them as `kind-unread`. A fixture it refuses as
    `kind-unread`, or as `version-unread`, is a skip naming the kind or the version: its digests (rules 3
    and 4), the catalog's form checker and its binding document still hold it. Any other refusal, and any
    finding, is a failure. A preset has no fixtures, and the verifier is not used for it.
    """
    results: list[tuple[str, str, str]] = []
    for directory in tree.entry_dirs():
        path = directory.relative_to(tree.base).as_posix()
        entry = load_strict((directory / "entry.json").read_bytes())
        for fixture in entry.get("fixtures", []):
            label = f"{path}/{fixture['name']}"
            fixture_dir = directory / fixture["path"]
            command = [
                sys.executable, "-I", str(VERIFIER),
                "--dialect", str(directory / "dialect.json"),
                "--case", str(fixture_dir / "case.json"),
                "--profiles", str(fixture_dir / "profiles.json"),
                "--preparation", str(fixture_dir / "preparation.json"),
            ]
            if (fixture_dir / "sources.json").is_file():
                command += ["--acquisitions", str(fixture_dir / "sources.json")]
            if (fixture_dir / BINDING).is_file():
                command += ["--binding", str(fixture_dir / BINDING)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            try:
                answer = verifier_answer(result)
            except ValueError:
                results.append((label, "problem", "the verifier printed no answer"))
                continue
            unread = None
            if answer.get("refused") == "kind-unread":
                unread = f"the verifier cannot recompute a source of kind {', '.join(entry['sourceKinds'])} (kind-unread)"
            elif answer.get("refused") == "version-unread":
                unread = f"the verifier does not implement dialect version {entry['dialect']['dialectVersion']} (version-unread)"
            if unread:
                results.append((label, "skip", f"{unread}; held by its digests only"))
            elif "reading" not in answer:
                results.append((label, "problem", f"the verifier answered {json.dumps(answer, sort_keys=True)}"))
            elif answer["reading"].get("digest") != fixture["preparationDigest"]:
                results.append((label, "problem", "the verifier's digest is not the preparationDigest"))
            else:
                results.append((label, "ok", ""))
    return results


def verifier_problems(tree: Tree) -> list[str]:
    return [f"{label}: {message}" for label, status, message in verifier_results(tree) if status == "problem"]


# ---------------------------------------------------------------------------------------------
# The upgrade keys against the catalog's earlier releases (RFC 0019 §3)


def git(repo: Path, *args: str) -> bytes | None:
    """A local git command's output, or None when it fails. No network: tags, objects and blobs only."""
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=60, env=environment)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def release_being_made(environment=os.environ) -> str | None:
    """The release a run is held for: the tag of a run at refs/tags/<tag> in the release-tag grammar (a tag
    push, or release.yml calling ci.yml), else None, for a branch or a pull request."""
    ref = environment.get("GITHUB_REF", "")
    tag = ref[len("refs/tags/"):] if ref.startswith("refs/tags/") else None
    return tag if tag is not None and release_tag_ok(tag) else None


def catalog_releases(repo: Path, below: str | None = None):
    """The catalog's releases lower in tag order than `below` (all of them when None), in tag order, as
    `[(tag, manifest.json's blob at the tag's commit, or None)]`; None when the tags cannot be read.

    A release is a tag in the release-tag grammar resolved to a commit, an annotated tag peeled; a tag
    that resolves to no commit is no release. The manifest is read as the commit's blob."""
    listing = git(repo, "tag", "--list")
    if listing is None:
        return None
    tags = sorted({t for t in listing.decode("utf-8", "replace").splitlines() if release_tag_ok(t)}, key=tag_order)
    releases = []
    for tag in tags:
        if below is not None and tag_order(tag) >= tag_order(below):
            continue
        commit = git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
        if commit is None:
            continue
        releases.append((tag, git(repo, "cat-file", "blob", f"{commit.decode('ascii').strip()}:manifest.json")))
    return releases


def repository_releases():
    return catalog_releases(ROOT, release_being_made())


def example_releases():
    """The example catalog's earlier releases (tests/fixtures/releases/<tag>/manifest.json), in tag order."""
    found = [d for d in EXAMPLE_RELEASES.iterdir() if d.is_dir() and release_tag_ok(d.name)]
    return [(d.name, (d / "manifest.json").read_bytes()) for d in sorted(found, key=lambda d: tag_order(d.name))]


def release_rows(data) -> list[tuple[str, str]]:
    """An earlier release's manifest, read for each row's `id` and `entryDigest` whatever its form, entry
    format version 1 included; it is not imported as version 2 (RFC 0019 §3)."""
    try:
        rows = json.loads(data.decode("utf-8")) if isinstance(data, bytes) else None
    except (UnicodeDecodeError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [
        (r["id"], r["entryDigest"]) for r in rows
        if isinstance(r, dict) and isinstance(r.get("id"), str) and isinstance(r.get("entryDigest"), str)
    ]


def upgrade_history_problems(entry: dict, releases) -> list[str]:
    """RFC 0019 §3: each `upgrade` key equals the entryDigest of the row with this entry's id in the manifest
    of an earlier release, lower in tag order than the release being made. A catalog with no earlier release
    admits no upgrade, and releases that cannot be read check no key: there is no form-only fallback."""
    if "upgrade" not in entry:
        return []
    found = releases()
    if found is None:
        return ["upgrade: the catalog's earlier releases cannot be read (fetch its tags), so no upgrade key is admitted"]
    if not found:
        return ["upgrade: the catalog has no earlier release, so no upgrade is admitted"]
    held = {d for _, data in found for i, d in release_rows(data) if i == entry["id"]}
    return [
        f"upgrade: the key {key!r} is the entryDigest of no row with id {entry['id']} in an earlier release's manifest"
        for key in entry["upgrade"] if key not in held
    ]


# ---------------------------------------------------------------------------------------------
# The scan and the link check


def _join(*parts: str) -> str:
    return "".join(parts)


CREDENTIAL_SHAPES = {
    "a bearer token": re.compile(rb"[Bb]earer[ \t]+[A-Za-z0-9._~+/=-]{20,}"),
    "an AWS access key id": re.compile(_join("AK", "IA").encode() + rb"[0-9A-Z]{16}"),
    "a GitHub token": re.compile(_join("gh", "[pousr]_").encode() + rb"[A-Za-z0-9]{30,}"),
    "a secret key": re.compile(_join("s", "k-").encode() + rb"[A-Za-z0-9_-]{20,}"),
    "a private-key header": re.compile(_join("-----BEGIN ").encode() + rb"[A-Z ]*" + _join("PRIVATE ", "KEY-----").encode()),
}
LOCAL_PATHS = {
    "a local home path": re.compile(_join("/ho", "me/").encode()),
    "a local temp path": re.compile(_join("/t", "mp/").encode()),
}


def all_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file() and not (set(path.relative_to(base).parts) & SKIPPED_DIRS):
            yield path


def scan_problems(base: Path) -> list[str]:
    problems = []
    for path in all_files(base):
        data = path.read_bytes()
        for label, pattern in {**CREDENTIAL_SHAPES, **LOCAL_PATHS}.items():
            if pattern.search(data):
                problems.append(f"{path.relative_to(base).as_posix()}: holds {label}")
    return problems


LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*(```|~~~)")


def link_problems(base: Path) -> list[str]:
    problems = []
    for path in all_files(base):
        if path.suffix != ".md":
            continue
        fenced = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for target in LINK.findall(line):
                if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                file_part = target.split("#", 1)[0]
                if file_part and not (path.parent / file_part).resolve().exists():
                    problems.append(f"{path.relative_to(base).as_posix()}:{number}: {target} does not resolve")
    return problems


# ---------------------------------------------------------------------------------------------
# Tests


class RepositoryTree(unittest.TestCase):
    def test_manifest_and_entries(self):
        tree = Tree(ROOT, repository_releases)
        self.assertEqual(tree_problems(tree), [])

    def test_says_how_many_entries(self):
        count = len(Tree(ROOT).entry_dirs())
        print(f"\nThe Exchange holds {count} entries." if count else "\nThe Exchange holds no entries yet; the suite passes on the manifest, the example and the scans.")

    def test_manifest_is_empty_or_every_row_has_an_entry(self):
        manifest = Tree(ROOT).manifest()
        self.assertEqual(len(manifest), len(Tree(ROOT).entry_dirs()))

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_fixtures_against_the_preparation_verifier(self):
        results = verifier_results(Tree(ROOT))
        self.assertEqual([r for r in results if r[1] == "problem"], [])
        for label, status, message in results:
            with self.subTest(label):
                if status == "skip":
                    self.skipTest(message)


class ExampleEntry(unittest.TestCase):
    """The example is a tree of the format's shape, so every rule has something to hold."""

    tree = Tree(EXAMPLE)

    def test_example_holds_to_the_format(self):
        self.assertEqual(tree_problems(self.tree), [])

    def test_example_is_one_entry_and_not_in_the_repository_manifest(self):
        self.assertEqual(len(self.tree.entry_dirs()), 1)
        self.assertEqual([r for r in Tree(ROOT).manifest() if r["id"].startswith("example.")], [])
        self.assertIn("example", (EXAMPLE / "README.md").read_text().lower())

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_example_fixture_against_the_preparation_verifier(self):
        self.assertEqual(verifier_problems(self.tree), [])
        self.assertEqual([status for _, status, _ in verifier_results(self.tree)], ["ok"])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_canon_agrees_with_the_verifiers(self):
        verifier = load_verifier()
        directory = self.tree.entry_dirs()[0]
        document = load_strict((directory / "dialect.json").read_bytes())
        self.assertEqual(canon(document), verifier.canon(document))

    def test_a_changed_byte_is_refused(self):
        directory = self.tree.entry_dirs()[0]
        row = self.tree.manifest()[0]
        entry = load_strict((directory / "entry.json").read_bytes())
        self.assertEqual(directory_problems(directory, "entries/example/fx-convert", row), [])
        self.assertTrue(directory_problems(directory, "entries/example/fx-convert", {**row, "entryDigest": digest(b"x")}))
        self.assertTrue(directory_problems(directory, "entries/example/fx-convert", {**row, "dialectDigest": digest(b"x")}))
        self.assertTrue(entry_problems({**entry, "assertion": "x"}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "id": "example.other"}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "extra": 1}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "pack": {"id": "vendor-intake", "versions": "1"}}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "fixtures": []}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "pack": {"id": "p", "versions": "1", "digests": []}}, "example.fx-convert"))
        self.assertTrue(entry_problems({**entry, "verification": [{"date": "d"}]}, "example.fx-convert"))

    def test_each_type_and_bound_refuses_its_example(self):
        entry = load_strict((self.tree.entry_dirs()[0] / "entry.json").read_bytes())
        ident = "example.fx-convert"
        self.assertEqual(entry_problems(entry, ident, 2), [])
        d = "sha256:" + "a" * 64
        fx = entry["fixtures"][0]
        ver = {"date": "2026-10-14", "runner": "v0.9.0", "runtime": "v0.32.0", "readers": [READER], "result": "agree"}

        def with_(**changes):
            return {**entry, **changes}

        def pack(**changes):
            return {**entry["pack"], **changes}

        refused = {
            "entryVersion 1": with_(entryVersion=1),
            "entryVersion 3": with_(entryVersion=3),
            "entryVersion true": with_(entryVersion=True),
            "entryVersion string": with_(entryVersion="2"),
            "kind missing": {k: v for k, v in entry.items() if k != "kind"},
            "kind other": with_(kind="recipe"),
            "kind not a string": with_(kind=["dialect"]),
            "pack missing for kind dialect": {k: v for k, v in entry.items() if k != "pack"},
            "fixtures missing for kind dialect": {k: v for k, v in entry.items() if k != "fixtures"},
            "id upper case": with_(id="Example.fx"),
            "id without a dot": with_(id="examplefx"),
            "id too long": with_(id="a." + "b" * 127),
            "id other than the path": with_(id="example.other"),
            "title empty": with_(title=""),
            "title 201": with_(title="t" * 201),
            "direction other": with_(direction="sideways"),
            "pack not closed": with_(pack=pack(extra=1)),
            "pack id relative": with_(pack=pack(id="vendor-intake")),
            "pack id 2049": with_(pack=pack(id="https://example.com/" + "a" * 2029)),
            "pack neither versions nor digests": with_(pack={"id": entry["pack"]["id"]}),
            "pack both": with_(pack=pack(digests=[d])),
            "pack versions empty": with_(pack=pack(versions="")),
            "pack versions 65": with_(pack=pack(versions="1" * 65)),
            "pack digests empty": with_(pack={"id": entry["pack"]["id"], "digests": []}),
            "pack digests 17": with_(pack={"id": entry["pack"]["id"], "digests": [d] * 17}),
            "pack digest malformed": with_(pack={"id": entry["pack"]["id"], "digests": ["sha256:A"]}),
            "dialect path": with_(dialect={**entry["dialect"], "path": "other.json"}),
            "dialectVersion 1": with_(dialect={**entry["dialect"], "dialectVersion": 1}),
            "dialectVersion not the document's": with_(dialect={**entry["dialect"], "dialectVersion": 3}),
            "dialect digest": with_(dialect={**entry["dialect"], "digest": "x"}),
            "dialect not closed": with_(dialect={**entry["dialect"], "extra": 1}),
            "requires not closed": with_(requires={"extra": 1}),
            "requires inputProfile": with_(requires={"inputProfile": "x"}),
            "requires connectionProfile": with_(requires={"connectionProfile": "x"}),
            "requires platform upper": with_(requires={"platform": "Postgres"}),
            "requires platform 65": with_(requires={"platform": "a" * 65}),
            "sourceKinds empty": with_(sourceKinds=[]),
            "sourceKinds 17": with_(sourceKinds=["operation"] * 17),
            "sourceKinds repeated": with_(sourceKinds=["operation", "operation"]),
            "sourceKinds not of the version": with_(sourceKinds=["research"]),
            "licence empty": with_(licence=""),
            "licence 65": with_(licence="L" * 65),
            "licence not an identifier": with_(licence="not a licence"),
            "author empty": with_(author=""),
            "author 101": with_(author="a" * 101),
            "assertion differs": with_(assertion=ASSERTION + " "),
            "fixtures empty": with_(fixtures=[]),
            "fixtures 65": with_(fixtures=[{**fx, "name": f"f{i}", "path": f"fixtures/f{i}"} for i in range(65)]),
            "fixture not closed": with_(fixtures=[{**fx, "extra": 1}]),
            "fixture name upper": with_(fixtures=[{**fx, "name": "V", "path": "fixtures/V"}]),
            "fixture name 65": with_(fixtures=[{**fx, "name": "a" * 65, "path": "fixtures/" + "a" * 65}]),
            "fixture names repeated": with_(fixtures=[fx, fx]),
            "fixture path": with_(fixtures=[{**fx, "path": "fixtures/other"}]),
            "fixture digest": with_(fixtures=[{**fx, "preparationDigest": "x"}]),
            "verification 33": with_(verification=[ver] * 33),
            "verification not closed": with_(verification=[{**ver, "extra": 1}]),
            "verification date": with_(verification=[{**ver, "date": "2026-13-01"}]),
            "verification runner": with_(verification=[{**ver, "runner": "0.9.0"}]),
            "verification runtime": with_(verification=[{**ver, "runtime": "v1.2"}]),
            "verification runner leading zero": with_(verification=[{**ver, "runner": "v0.09.0"}]),
            "verification runtime non-ASCII digit": with_(verification=[{**ver, "runtime": "v0.\u0663.0"}]),
            "verification readers empty": with_(verification=[{**ver, "readers": []}]),
            "verification readers 9": with_(verification=[{**ver, "readers": [READER] * 9}]),
            "verification reader not a locator": with_(verification=[{**ver, "readers": ["r"]}]),
            "verification reader 201": with_(verification=[{**ver, "readers": ["r" * 201]}]),
            "verification result": with_(verification=[{**ver, "result": "disagree"}]),
            "member missing": {k: v for k, v in entry.items() if k != "title"},
        }
        for label, candidate in refused.items():
            with self.subTest(label):
                self.assertTrue(entry_problems(candidate, ident, 2), label)
        accepted = {
            "digests instead of versions": with_(pack={"id": entry["pack"]["id"], "digests": [d] * 16}),
            "LicenseRef": with_(licence="LicenseRef-Acme-1"),
            "bounds": with_(title="t" * 200, author="a" * 100, id="a.b"),
            "a verification": with_(verification=[ver] * 32),
            "platform": with_(requires={"platform": "postgres", "connectionProfile": d}),
        }
        for label, candidate in accepted.items():
            with self.subTest(label):
                self.assertEqual(entry_problems(candidate, candidate["id"] if label == "bounds" else ident, 2), [])

    def test_duplicate_member_names_are_refused(self):
        with self.assertRaises(ValueError):
            load_strict(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            load_strict(b'{"a":{"b":1,"b":2}}')

    def test_file_size_bounds(self):
        import tempfile

        directory = self.tree.entry_dirs()[0]
        entry = load_strict((directory / "entry.json").read_bytes())
        self.assertEqual(size_problems(directory, entry), [])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "entry.json").write_bytes(b"x" * (64 * 1024 + 1))
            (base / "README.md").write_bytes(b"x" * (64 * 1024))
            (base / "fixtures" / "valid").mkdir(parents=True)
            (base / "fixtures" / "valid" / "big").write_bytes(b"x" * (16 * 1024 * 1024 + 1))
            self.assertEqual(len(size_problems(base, entry)), 2)

    def test_manifest_shape_and_order(self):
        row = self.tree.manifest()[0]
        self.assertEqual(manifest_problems([row]), [])
        self.assertEqual(manifest_problems([]), [])
        later = {**row, "id": "zz.zz", "path": "entries/zz/zz"}
        self.assertEqual(manifest_problems([row, later]), [])
        self.assertTrue(manifest_problems([later, row]))
        self.assertTrue(manifest_problems([row, row]))
        self.assertTrue(manifest_problems([{**row, "extra": 1}]))
        self.assertTrue(manifest_problems({}))


class VerifierPin(unittest.TestCase):
    """The specification commit the catalog's verifier is pinned at is named in three places, and they are one
    commit: the `ref` CI checks the specification out at, the commit CONTRIBUTING.md has a contributor check
    out, and the commit of `READER`, the locator an entry's verification record cites (exchange #14)."""

    @staticmethod
    def pins() -> dict[str, list[str]]:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        return {
            "ci.yml": re.findall(r"repository: Judgment-Pack/judgment-pack-spec\s+ref: (\S+)", workflow),
            "CONTRIBUTING.md": re.findall(r"git -C \.spec checkout (\S+)", contributing),
            "READER": [READER.rpartition("@")[2]],
        }

    def test_each_place_names_one_full_commit(self):
        for place, pins in self.pins().items():
            with self.subTest(place):
                self.assertEqual(len(pins), 1)
                self.assertRegex(pins[0], r"[0-9a-f]{40}")

    def test_the_three_pins_are_one_commit(self):
        pins = self.pins()
        self.assertEqual(len({pin for found in pins.values() for pin in found}), 1, pins)

    def test_the_checkout_under_spec_is_at_the_pin(self):
        head = git(SPEC, "rev-parse", "HEAD") if (SPEC / ".git").exists() else None
        if head is None:
            self.skipTest(".spec/ is absent or not a git checkout")
        self.assertEqual(head.decode().strip(), READER.rpartition("@")[2])


class UnreadKindExample(unittest.TestCase):
    """A fixture of a kind the verifier does not read is a skip naming the kind, held by digests."""

    tree = Tree(EXAMPLE.parent / "unread-kind-entry")

    def test_digests_hold_it(self):
        self.assertEqual(tree_problems(self.tree), [])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_skip_reason_names_the_kind(self):
        results = verifier_results(self.tree)
        self.assertEqual(len(results), 1)
        label, status, message = results[0]
        self.assertEqual(status, "skip")
        self.assertIn("selected-file", message)
        self.assertIn("kind-unread", message)
        self.assertEqual(verifier_problems(self.tree), [])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_repository_report_skips_with_the_reason(self):
        for label, status, message in verifier_results(self.tree):
            with self.subTest(label):
                if status == "skip":
                    self.skipTest(message)
                self.assertEqual(status, "ok")


class UnreadVersionExample(unittest.TestCase):
    """A version-3 dialect with a round-8 `research` source, unbound, its fixture carrying binding.json and the
    research record in sources.json (RFC 0019 §3, corrected under round 8). Its form, its classification and its
    binding document hold, and the pinned verifier, which reads round 8, replays its fixture (RFC 0019 §4)."""

    tree = Tree(EXAMPLE.parent / "unread-version-entry")

    def test_its_form_classification_and_binding_hold(self):
        self.assertEqual(tree_problems(self.tree), [])
        directory = self.tree.entry_dirs()[0]
        document = load_strict((directory / "dialect.json").read_bytes())
        self.assertIsNone(dialect_form.check((directory / "dialect.json").read_bytes()))
        self.assertEqual(unbound_source_names(document), {"recipe"})
        self.assertIn("binding.json", self.tree.manifest()[0]["fixtures"][0]["files"])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_its_fixture_is_replayed_by_the_pinned_verifier(self):
        self.assertEqual([status for _, status, _ in verifier_results(self.tree)], ["ok"])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_a_research_fixture_without_its_record_or_with_a_changed_one_is_a_failure(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(UNREAD_VERSION, tmp)
            path = tree.entry_dirs()[0] / "fixtures" / "valid" / "sources.json"
            record = path.read_bytes()
            path.write_bytes(b"{}")
            results = verifier_results(tree)
            self.assertEqual([status for _, status, _ in results], ["problem"])
            self.assertIn("acquisition-missing", results[0][2])
            # The answer's value changed: the preparation the reader computes is no longer the fixture's.
            path.write_bytes(record.replace(b"A data export", b"A data deletion"))
            results = verifier_results(tree)
            self.assertEqual([status for _, status, _ in results], ["problem"])
            self.assertIn("preparation-differs", results[0][2])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_another_malformed_refusal_stays_a_failure(self):
        import tempfile, shutil

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shutil.copytree(self.tree.base, base, dirs_exist_ok=True)
            path = base / "entries/example/research/dialect.json"
            path.write_text(path.read_text().replace('"version":3', '"version":"3"'))
            self.assertEqual([s for _, s, _ in verifier_results(Tree(base))], ["problem"])


class TwoDocumentExamples(unittest.TestCase):
    """An entry of direction both holds dialect.json and output.json; one of direction output holds output.json alone."""

    both = Tree(EXAMPLE.parent / "both-entry")
    output = Tree(EXAMPLE.parent / "output-entry")

    def entry_and_row(self, tree):
        directory = tree.entry_dirs()[0]
        path = directory.relative_to(tree.base).as_posix()
        return directory, path, load_strict((directory / "entry.json").read_bytes()), tree.manifest()[0]

    def copy(self, tree, tmp):
        import shutil

        base = Path(tmp)
        shutil.copytree(tree.base, base, dirs_exist_ok=True)
        return Tree(base)

    def test_each_direction_holds_to_the_format(self):
        self.assertEqual(tree_problems(self.both), [])
        self.assertEqual(tree_problems(self.output), [])

    def test_the_manifest_rows_carry_the_digests_the_documents_have(self):
        _, _, _, row = self.entry_and_row(self.both)
        self.assertEqual(sorted(row), ["dialectDigest", "entryDigest", "fixtures", "id", "kind", "outputDigest", "path"])
        _, _, _, row = self.entry_and_row(self.output)
        self.assertEqual(sorted(row), ["entryDigest", "fixtures", "id", "kind", "outputDigest", "path"])
        self.assertEqual(row["kind"], "dialect")
        self.assertEqual(row["fixtures"], [])
        self.assertEqual(manifest_problems([row]), [])
        self.assertTrue(manifest_problems([{**row, "outputDigest": "x"}]))
        self.assertTrue(manifest_problems([{**row, "extra": 1}]))

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_input_side_of_a_both_entry_is_read_and_an_output_entry_has_nothing_to_read(self):
        self.assertEqual([s for _, s, _ in verifier_results(self.both)], ["ok"])
        self.assertEqual(verifier_results(self.output), [])

    def test_the_output_member_shape_and_bounds(self):
        _, _, entry, _ = self.entry_and_row(self.both)
        ident = "example.triage-both"
        self.assertEqual(entry_problems(entry, ident, 2, 1), [])
        out = entry["output"]

        def with_(**changes):
            return {**entry, **changes}

        refused = {
            "output path": with_(output={**out, "path": "other.json"}),
            "output not closed": with_(output={**out, "extra": 1}),
            "output member missing": with_(output={k: v for k, v in out.items() if k != "digest"}),
            "outputVersion 0": with_(output={**out, "outputVersion": 0}),
            "outputVersion string": with_(output={**out, "outputVersion": "1"}),
            "outputVersion true": with_(output={**out, "outputVersion": True}),
            "output digest": with_(output={**out, "digest": "sha256:A"}),
            "output not an object": with_(output="output.json"),
        }
        for label, candidate in refused.items():
            with self.subTest(label):
                self.assertTrue(entry_problems(candidate, ident, 2, 1), label)
        self.assertEqual(entry_problems(with_(output={**out, "outputVersion": 2}), ident, 2, 2), [])
        self.assertTrue(entry_problems(entry, ident, 2, 2))

    def test_direction_decides_which_documents_the_entry_holds(self):
        _, _, both, _ = self.entry_and_row(self.both)
        _, _, only, _ = self.entry_and_row(self.output)
        without = lambda e, name: {k: v for k, v in e.items() if k != name}
        refused = {
            "both without output": (without(both, "output"), "example.triage-both"),
            "both without dialect": (without(both, "dialect"), "example.triage-both"),
            "input with output": ({**both, "direction": "input"}, "example.triage-both"),
            "output with dialect": ({**only, "dialect": both["dialect"]}, "example.triage-write"),
            "output without output": (without(only, "output"), "example.triage-write"),
            "output with a source kind": ({**only, "sourceKinds": ["operation"]}, "example.triage-write"),
            "output with a fixture": ({**only, "fixtures": both["fixtures"]}, "example.triage-write"),
            "input without dialect": ({**without(both, "dialect"), "direction": "input", "output": None}, "example.triage-both"),
        }
        for label, (candidate, ident) in refused.items():
            with self.subTest(label):
                self.assertTrue(entry_problems(candidate, ident, 2, 1), label)
        input_only = without({**both, "direction": "input"}, "output")
        self.assertEqual(entry_problems(input_only, "example.triage-both", 2, None), [])

    def test_a_both_entry_without_output_json_is_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = self.copy(self.both, tmp)
            directory, path, _, row = self.entry_and_row(tree)
            (directory / "output.json").unlink()
            self.assertTrue(directory_problems(directory, path, row))

    def test_an_input_entry_with_an_output_json_is_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = self.copy(EXAMPLE_TREE, tmp)
            directory, path, _, row = self.entry_and_row(tree)
            self.assertEqual(directory_problems(directory, path, row), [])
            (directory / "output.json").write_bytes((self.both.entry_dirs()[0] / "output.json").read_bytes())
            self.assertTrue(directory_problems(directory, path, row))
            with_digest = {**row, "outputDigest": digest((directory / "output.json").read_bytes())}
            self.assertTrue(directory_problems(directory, path, with_digest))

    def test_an_output_entry_with_a_dialect_is_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = self.copy(self.output, tmp)
            directory, path, entry, row = self.entry_and_row(tree)
            (directory / "dialect.json").write_bytes((self.both.entry_dirs()[0] / "dialect.json").read_bytes())
            self.assertTrue(directory_problems(directory, path, row))
            dialect = load_strict((directory / "dialect.json").read_bytes())
            entry = {**entry, "dialect": {"path": "dialect.json", "dialectVersion": 2, "digest": digest(canon(dialect))}}
            (directory / "entry.json").write_bytes(json.dumps(entry, indent=2).encode() + b"\n")
            row = {**row, "entryDigest": digest((directory / "entry.json").read_bytes()),
                   "dialectDigest": digest((directory / "dialect.json").read_bytes())}
            self.assertTrue(directory_problems(directory, path, row))

    def test_a_digest_mismatch_on_output_json_is_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            for source in (self.both, self.output):
                tree = self.copy(source, tmp + "/" + source.base.name)
                directory, path, entry, row = self.entry_and_row(tree)
                self.assertEqual(directory_problems(directory, path, row), [])
                document = load_strict((directory / "output.json").read_bytes())
                document["policies"]["wit_work_item_write"]["closed"] = False
                changed = json.dumps(document, indent=2).encode() + b"\n"
                (directory / "output.json").write_bytes(changed)
                # the file no longer matches the manifest's outputDigest, nor the entry's output.digest
                problems = directory_problems(directory, path, row)
                self.assertTrue(any("outputDigest" in p for p in problems), problems)
                self.assertTrue(any("output.digest" in p for p in problems), problems)
                # the manifest follows the bytes: only the entry's canonical digest still refuses
                problems = directory_problems(directory, path, {**row, "outputDigest": digest(changed)})
                self.assertEqual([p for p in problems if "output.digest" in p].__len__(), 1, problems)
                # a stored form other than canon has its own file digest and the same canonical one
                (directory / "output.json").write_bytes(canon(load_strict((self.output.entry_dirs()[0] / "output.json").read_bytes())))
                problems = directory_problems(directory, path, row)
                self.assertTrue(any("outputDigest" in p for p in problems), problems)
                self.assertFalse(any("output.digest" in p for p in problems), problems)

    def test_the_output_document_is_held_to_its_form(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = self.copy(self.output, tmp)
            directory, path, entry, row = self.entry_and_row(tree)
            document = load_strict((directory / "output.json").read_bytes())
            for label, changed in {
                "version 2": {**document, "outputVersion": "2"},
                "version an integer": {**document, "outputVersion": 1},
                "member added": {**document, "extra": 1},
                "platform empty": {**document, "platform": ""},
                "policies an array": {**document, "policies": []},
                "policy a string": {**document, "policies": {"wit_work_item_write": "not-a-decision-policy"}},
                "policy without outcomes": {**document, "policies": {"t": {"closed": True}}},
                "policy member unknown": {**document, "policies": {"t": {"outcomes": ["a"], "x": 1}}},
                "outcomes empty": {**document, "policies": {"t": {"outcomes": []}}},
                "closed a string": {**document, "policies": {"t": {"outcomes": ["a"], "closed": "yes"}}},
                "requireSignedRecord malformed": {**document, "policies": {"t": {"outcomes": ["a"], "requireSignedRecord": ["abc"]}}},
                "bind not a pointer": {**document, "policies": {"t": {"outcomes": ["a"], "bind": [{"argument": "id", "fact": "/x"}]}}},
                "bind not closed": {**document, "policies": {"t": {"outcomes": ["a"], "bind": [{"argument": "/id", "fact": "/x", "z": 1}]}}},
                "fix without value": {**document, "policies": {"t": {"outcomes": ["a"], "fix": [{"argument": "/id"}]}}},
                "fixed and bound": {**document, "policies": {"t": {"outcomes": ["a"], "fix": [{"argument": "/id", "value": 1}], "bind": [{"argument": "/id", "fact": "/x"}]}}},
            }.items():
                with self.subTest(label):
                    data = json.dumps(changed, indent=2).encode() + b"\n"
                    (directory / "output.json").write_bytes(data)
                    entry = {**entry, "output": {**entry["output"], "digest": digest(canon(changed))}}
                    (directory / "entry.json").write_bytes(json.dumps(entry, indent=2).encode() + b"\n")
                    candidate = {**row, "outputDigest": digest(data), "entryDigest": digest((directory / "entry.json").read_bytes())}
                    self.assertTrue(directory_problems(directory, path, candidate), label)

    def test_an_output_entry_with_a_dialect_digest_in_its_row_is_refused(self):
        directory, path, _, row = self.entry_and_row(self.output)
        self.assertTrue(directory_problems(directory, path, {**row, "dialectDigest": digest(b"x")}))
        directory, path, _, row = self.entry_and_row(self.both)
        self.assertTrue(directory_problems(directory, path, {k: v for k, v in row.items() if k != "outputDigest"}))


EXAMPLE_TREE = ExampleEntry.tree
METADATA = EXAMPLE.parent / "metadata-entry"
UNBOUND = EXAMPLE.parent / "unbound-entry"
REFUSED = EXAMPLE.parent / "refused"


class ReleaseTags(unittest.TestCase):
    """RFC 0019 §3: the release-tag grammar, the order of tags and the compatibility ranges."""

    def test_the_grammar_accepts_its_tags(self):
        for tag in ["v0.0.0", "v0.1.0", "v0.10.0", "v1.2.3", "v10.20.30", "v2026.10.15", "v" + "9" * 40 + ".0.0"]:
            with self.subTest(tag):
                self.assertTrue(release_tag_ok(tag))

    def test_the_grammar_refuses_everything_else(self):
        refused = [
            "", "v", "0.1.0", "v0.1", "v0.1.0.0", "v1..0", "v01.0.0", "v0.01.0", "v0.0.00", "V0.1.0",
            "v0.1.0-rc.1", "v0.1.0+build.1", " v0.1.0", "v0.1.0 ", "v0.1.0\n", "v-1.0.0", "v+1.0.0",
            "v1.0.0x", "refs/tags/v0.1.0", "v\u0661.0.0", "v0.\uff11.0", "v0.1.\u00b2", None, 1, ["v0.1.0"],
        ]
        for tag in refused:
            with self.subTest(repr(tag)):
                self.assertFalse(release_tag_ok(tag))

    def test_tags_are_ordered_by_their_three_integers(self):
        self.assertLess(tag_order("v0.9.0"), tag_order("v0.10.0"))
        self.assertLess(tag_order("v0.10.9"), tag_order("v0.11.0"))
        self.assertLess(tag_order("v1.99.99"), tag_order("v10.0.0"))
        self.assertGreater("v0.9.0", "v0.10.0")  # as text the order is the other way round

    def test_compatibility_values(self):
        longest = ">=v0.14.0 <v1" + "0" * 47 + ".0.0"
        self.assertEqual(len(longest), 64)
        accepted = ["v0.11.0", "v0.0.0", ">=v0.10.0 <v0.11.0", ">=v0.0.0 <v0.0.1", ">=v0.9.0 <v0.10.0", ">=v1.9.9 <v2.0.0", longest]
        for value in accepted:
            with self.subTest(value):
                self.assertTrue(compatibility_ok(value))
        refused = [
            "", ">=v0.10.0 <v0.10.0", ">=v0.11.0 <v0.10.0", ">=v0.10.0 <v0.9.0", ">=v0.10.0  <v0.11.0",
            ">= v0.10.0 <v0.11.0", ">=v0.10.0< v0.11.0", ">=v0.10.0<v0.11.0", ">=v0.10.0\t<v0.11.0",
            ">=v0.10.0\u00a0<v0.11.0", "<v0.11.0 >=v0.10.0", ">=v0.10.0", "<v0.11.0", ">v0.10.0 <v0.11.0",
            ">=v0.10.0 <=v0.11.0", "^v0.10.0", "~v0.10.0", "v0.10.x", "v0.10.0 - v0.11.0", ">=0.10.0 <0.11.0",
            ">=v0.010.0 <v0.11.0", ">=v0.10.0 <v0.11.0 ", ">=v0.10.0 <v0.11.0\n", "v0.11.0-rc.1",
            ">=v0.14.0 <v1" + "0" * 48 + ".0.0", "v1" + "0" * 59 + ".0.0", None, 11, {"desk": "v0.11.0"},
        ]
        for value in refused:
            with self.subTest(repr(value)):
                self.assertFalse(compatibility_ok(value))
        self.assertEqual(len(refused[-5]), 65)
        self.assertEqual(len(refused[-4]), 65)
        self.assertTrue(release_tag_ok(refused[-4]))


class AuthoringMetadata(unittest.TestCase):
    """description, compatibility and upgrade (RFC 0019 §3): the passing example and each bound in place."""

    tree = Tree(METADATA)

    def entry(self):
        return load_strict((self.tree.entry_dirs()[0] / "entry.json").read_bytes())

    def test_example_holds_to_the_format(self):
        self.assertEqual(tree_problems(self.tree), [])
        entry = self.entry()
        self.assertTrue({"description", "compatibility", "upgrade"} <= entry.keys())

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_example_fixture_against_the_preparation_verifier(self):
        self.assertEqual([status for _, status, _ in verifier_results(self.tree)], ["ok"])

    def test_the_upgrade_note_is_keyed_by_the_previous_releases_bytes(self):
        # RFC 0019 §3: the key is the entryDigest of this entry's row in an earlier release's manifest: here the
        # example catalog's v0.1.0, of entry format version 1, whose row pins the entry.json it published.
        entry = self.entry()
        release = EXAMPLE_RELEASES / "v0.1.0"
        rows = dict(release_rows((release / "manifest.json").read_bytes()))
        published = (release / "entries/example/fx-metadata/entry.json").read_bytes()
        self.assertEqual(list(entry["upgrade"]), [rows["example.fx-metadata"]])
        self.assertEqual(rows["example.fx-metadata"], digest(published))
        self.assertEqual(load_strict(published)["entryVersion"], 1)

    def test_each_bound_in_place(self):
        entry = self.entry()
        ident = "example.fx-metadata"
        d = "sha256:" + "a" * 64

        def with_(**changes):
            return {**entry, **changes}

        bare = {k: v for k, v in entry.items() if k not in ("description", "compatibility", "upgrade")}
        accepted = {
            "no metadata": bare,
            "description 1": with_(description="d"),
            "description 4096": with_(description="d" * 4096),
            "description 4096 characters, more bytes": with_(description="\u00e9" * 4096),
            "compatibility of tags": with_(compatibility={"desk": "v0.14.0", "runner": "v0.0.0"}),
            "compatibility of 64": with_(compatibility={"desk": ">=v0.14.0 <v1" + "0" * 47 + ".0.0", "runner": "v0.11.0"}),
            "upgrade 1, a note of 1": with_(upgrade={d: "n"}),
            "upgrade 32, notes of 2048": with_(upgrade={digest(str(i).encode()): "n" * 2048 for i in range(32)}),
        }
        for label, candidate in accepted.items():
            with self.subTest(label):
                self.assertEqual(entry_problems(candidate, ident, 2), [])
        refused = {
            "description a number": with_(description=1),
            "description null": with_(description=None),
            "description an array": with_(description=["d"]),
            "description 4097 characters": with_(description="\u00e9" * 4097),
            "compatibility an array": with_(compatibility=["v0.14.0", "v0.11.0"]),
            "compatibility empty": with_(compatibility={}),
            "compatibility without desk": with_(compatibility={"runner": "v0.11.0"}),
            "desk a number": with_(compatibility={"desk": 14, "runner": "v0.11.0"}),
            "desk two spaces": with_(compatibility={"desk": ">=v0.14.0  <v0.15.0", "runner": "v0.11.0"}),
            "runner a prerelease": with_(compatibility={"desk": "v0.14.0", "runner": "v0.11.0-rc.1"}),
            "upgrade an array": with_(upgrade=[d]),
            "upgrade a string": with_(upgrade="n"),
            "upgrade key upper case": with_(upgrade={"sha256:" + "A" * 64: "n"}),
            "upgrade key short": with_(upgrade={"sha256:" + "a" * 63: "n"}),
            "upgrade note a number": with_(upgrade={d: 1}),
            "upgrade note null": with_(upgrade={d: None}),
        }
        for label, candidate in refused.items():
            with self.subTest(label):
                self.assertTrue(entry_problems(candidate, ident, 2), label)

    def test_duplicate_upgrade_keys_are_refused(self):
        with self.assertRaises(ValueError):
            load_strict(b'{"upgrade":{"sha256:%s":"a","sha256:%s":"b"}}' % (b"a" * 64, b"a" * 64))


class UnboundExample(unittest.TestCase):
    """A fixture of a dialect with an unbound source carries binding.json (RFC 0018 §4.4, RFC 0019 §3)."""

    tree = Tree(UNBOUND)

    def test_example_holds_to_the_format(self):
        self.assertEqual(tree_problems(self.tree), [])
        self.assertIn("binding.json", self.tree.manifest()[0]["fixtures"][0]["files"])

    def test_which_dialects_have_an_unbound_source(self):
        # RFC 0019 §3, as #166 settled it: an operation with all four catalog members and no binding member, or a
        # research source with none of its three binding members, is unbound; partial sets are not, and are
        # refused by the form checker as input-malformed.
        unbound = load_strict((self.tree.entry_dirs()[0] / "dialect.json").read_bytes())
        bound = load_strict((EXAMPLE_TREE.entry_dirs()[0] / "dialect.json").read_bytes())
        self.assertTrue(has_unbound_source(unbound))
        self.assertFalse(has_unbound_source(bound))
        source = bound["sources"][0]
        self.assertFalse(has_unbound_source({"sources": [{k: v for k, v in source.items() if k != "profileDigest"}]}))
        self.assertFalse(has_unbound_source({"sources": [{k: v for k, v in source.items() if k not in ("profile", "profileDigest")}]}))
        partial = {k: v for k, v in unbound["sources"][0].items() if k != "record"}
        self.assertFalse(has_unbound_source({"sources": [partial]}))
        self.assertEqual(dialect_form.check(json.dumps({**unbound, "sources": [partial]}).encode())[0], "input-malformed")
        self.assertTrue(has_unbound_source({"sources": [{"name": "r", "kind": "research"}]}))
        self.assertFalse(has_unbound_source({"sources": [{"name": "r", "kind": "research", "profile": "ai"}]}))
        self.assertFalse(has_unbound_source({"sources": [{"name": "f", "kind": "selected-file"}]}))
        self.assertFalse(has_unbound_source(None))

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_verifier_replays_it_with_its_binding(self):
        # The pinned verifier reads dialect version 3 and takes the fixture's binding document (RFC 0019 §4).
        self.assertEqual([status for _, status, _ in verifier_results(self.tree)], ["ok"])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_without_its_binding_the_replay_is_not_a_reading(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(UNBOUND, tmp)
            (tree.entry_dirs()[0] / "fixtures" / "valid" / BINDING).unlink()
            self.assertEqual([status for _, status, _ in verifier_results(tree)], ["problem"])


class ManifestForm(unittest.TestCase):
    """The manifest's bounds and rows (RFC 0019 §3), in place; the refused trees follow."""

    def row(self):
        return Tree(METADATA).manifest()[0]

    def test_the_path_is_the_ids_split_at_its_first_dot(self):
        self.assertEqual(entry_path("example.fx-metadata"), "entries/example/fx-metadata")
        self.assertEqual(entry_path("a.b.c"), "entries/a/b.c")

    def test_the_rows_fixture_lists(self):
        row = self.row()
        self.assertEqual(manifest_problems([row]), [])
        listing = row["fixtures"][0]

        def files(names):
            return [{**row, "fixtures": [{**listing, "files": names}]}]

        self.assertEqual(manifest_problems(files(["case.json", "profiles.json", "preparation.json"])), [])
        self.assertEqual(manifest_problems(files(["binding.json", "case.json", "preparation.json", "profiles.json", "sources.json"])), [])
        refused = {
            "fixtures not an array": [{**row, "fixtures": {}}],
            "a fixture not an object": [{**row, "fixtures": ["valid"]}],
            "a fixture without files": [{**row, "fixtures": [{"name": "valid"}]}],
            "name not a string": [{**row, "fixtures": [{**listing, "name": 1}]}],
            "files not an array": files("case.json"),
            "files with a number": files(["case.json", "profiles.json", "preparation.json", 1]),
            "files without profiles": files(["case.json", "preparation.json", "sources.json"]),
            "files without preparation": files(["case.json", "profiles.json", "sources.json"]),
            "files with a path": files(["case.json", "profiles.json", "preparation.json", "extra/case.json"]),
        }
        for label, manifest in refused.items():
            with self.subTest(label):
                self.assertTrue(manifest_problems(manifest), label)

    def test_the_row_bound_is_1024(self):
        row = self.row()
        rows = sorted(
            [{**row, "id": f"example.row-{i:04d}", "path": f"entries/example/row-{i:04d}"} for i in range(1023)] + [row],
            key=lambda r: r["id"].encode("utf-8"),
        )
        self.assertEqual(manifest_problems(rows), [])
        more = sorted(rows + [{**row, "id": "example.row-9999", "path": "entries/example/row-9999"}], key=lambda r: r["id"].encode("utf-8"))
        self.assertEqual(manifest_problems(more), ["manifest: 1025 rows, more than 1,024"])

    def test_the_manifest_is_read_within_its_bound(self):
        """Its size first: nothing read or parsed past 1 MiB, and exactly its size read at the bound."""
        import tempfile
        from unittest import mock

        module = sys.modules[__name__]
        real_open = Path.open
        reads: list[int] = []

        class Counted:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.handle.close()

            def fileno(self):
                return self.handle.fileno()

            def read(self, *args):
                data = self.handle.read(*args)
                reads.append(len(data))
                return data

        def counted_open(self, *args, **kwargs):
            return Counted(real_open(self, *args, **kwargs))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            for size, admitted in ((1024 * 1024, True), (1024 * 1024 + 1, False)):
                with self.subTest(size):
                    path.write_bytes(b"[" + b" " * (size - 3) + b"]\n")
                    reads.clear()
                    with mock.patch.object(Path, "open", counted_open), \
                            mock.patch.object(module, "load_strict", wraps=load_strict) as parse:
                        if admitted:
                            try:
                                self.assertEqual(read_manifest(path), [])
                            except ValueError as error:
                                self.fail(f"a manifest of exactly 1 MiB is refused: {error}")
                        else:
                            with self.assertRaises(ValueError):
                                read_manifest(path)
                    self.assertEqual(sum(reads), size if admitted else 0)
                    self.assertEqual(parse.call_count, 1 if admitted else 0)

    def test_the_byte_bound_is_one_mib(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_bytes(b"[" + b" " * (1024 * 1024 - 3) + b"]\n")
            self.assertEqual(path.stat().st_size, 1024 * 1024)
            try:
                self.assertEqual(read_manifest(path), [])
            except ValueError as error:
                self.fail(f"a manifest of exactly 1 MiB is refused: {error}")
            path.write_bytes(b"[" + b" " * (1024 * 1024 - 2) + b"]\n")
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_ids_in_byte_order(self):
        row = self.row()

        def at(ident):
            return {**row, "id": ident, "path": entry_path(ident)}

        # "-" (0x2d) is before "." (0x2e) and both before the digits and the letters.
        self.assertEqual(manifest_problems([at("example.a-b"), at("example.a.b"), at("example.a0")]), [])
        self.assertTrue(manifest_problems([at("example.a.b"), at("example.a-b")]))


# One refused tree per bound under tests/fixtures/refused/, each a passing example (its base) with one
# change; its README says which. For each tree: its base, the steps that revert its one change (a
# top-level member of entry.json restored from the base, the manifest's digests then following the
# bytes; or a path restored from the base, or removed where the base has none), and the complete set of
# problems the tree must produce.
REFUSED_TREES = {
    'binding-65537-bytes': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/fixtures/valid/binding.json')],
        [
            'entries/example/fx-unbound: fixtures/valid: binding.json is 65537 bytes, over 65,536',
        ],
    ),
    'binding-names-an-unknown-source': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/fixtures/valid/binding.json')],
        [
            "entries/example/fx-unbound: fixtures/valid: binding.json: sources names 'rates', which is not an unbound source of the dialect",
        ],
    ),
    'binding-research-unrequested-capability': (
        'unread-version-entry',
        [('path', 'entries/example/research/fixtures/valid/binding.json')],
        [
            'entries/example/research: fixtures/valid: binding.json: sources.recipe: webProfiles assigns search, not exactly the web capabilities the source requests (none)',
        ],
    ),
    'binding-research-without-web-profiles': (
        'unread-version-entry',
        [('path', 'entries/example/research/fixtures/valid/binding.json')],
        [
            'entries/example/research: fixtures/valid: binding.json: sources.recipe: missing webProfiles',
        ],
    ),
    'binding-with-another-member': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/fixtures/valid/binding.json')],
        [
            'entries/example/fx-unbound: fixtures/valid: binding.json: unknown member note',
        ],
    ),
    'binding-without-its-source': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/fixtures/valid/binding.json')],
        [
            "entries/example/fx-unbound: fixtures/valid: binding.json: sources does not name the unbound source 'fx'",
        ],
    ),
    'compatibility-desk-65-characters': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            'entries/example/fx-metadata: compatibility: desk is 65 characters, over 64',
        ],
    ),
    'compatibility-desk-empty': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            'entries/example/fx-metadata: compatibility: desk is empty',
        ],
    ),
    'compatibility-desk-lower-bound-only': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: desk '>=v0.14.0' is not a release tag or a range of release tags",
        ],
    ),
    'compatibility-not-an-object': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            'entries/example/fx-metadata: compatibility: not an object',
        ],
    ),
    'compatibility-runner-leading-zero': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: runner 'v0.011.0' is not a release tag or a range of release tags",
        ],
    ),
    'compatibility-runner-non-ascii-digit': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: runner 'v١.0.0' is not a release tag or a range of release tags",
        ],
    ),
    'compatibility-runner-two-spaces': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: runner '>=v0.11.0  <v0.12.0' is not a release tag or a range of release tags",
        ],
    ),
    'compatibility-runner-upper-below-lower-by-integers': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: runner '>=v0.10.0 <v0.9.0' has an upper tag not above its lower tag",
        ],
    ),
    'compatibility-runner-upper-not-above-lower': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            "entries/example/fx-metadata: compatibility: runner '>=v0.11.0 <v0.11.0' has an upper tag not above its lower tag",
        ],
    ),
    'compatibility-with-another-member': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            'entries/example/fx-metadata: compatibility: unknown member gateway',
        ],
    ),
    'compatibility-without-runner': (
        'metadata-entry',
        [('member', 'compatibility')],
        [
            'entries/example/fx-metadata: compatibility: missing runner',
        ],
    ),
    'description-4097-characters': (
        'metadata-entry',
        [('member', 'description')],
        [
            'entries/example/fx-metadata: entry: description is 4097 characters, over 4096',
        ],
    ),
    'description-empty': (
        'metadata-entry',
        [('member', 'description')],
        [
            'entries/example/fx-metadata: entry: description is empty',
        ],
    ),
    'dialect-kind-without-fixtures': (
        'metadata-entry',
        [('member', 'fixtures')],
        [
            'entries/example/fx-metadata: entry: fixtures is required for kind dialect',
        ],
    ),
    'dialect-kind-without-pack': (
        'metadata-entry',
        [('member', 'pack')],
        [
            'entries/example/fx-metadata: entry: pack is required for kind dialect',
        ],
    ),
    'dialect-refused-though-every-fixture-is-skipped': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/fx-unbound: dialect.json is refused by the catalog's form checker, input-malformed: version 3 is written one way: provider is a member of version 2 alone (§2)",
        ],
    ),
    'dialect-research-partial-binding': (
        'unread-version-entry',
        [('path', 'entries/example/research/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/research: dialect.json is refused by the catalog's form checker, input-malformed: research source 'recipe' has profile but not all of profile, profileDigest and webProfiles: partial binding members (§4.4)",
        ],
    ),
    'dialect-unbound-operation-partial': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/fx-unbound: dialect.json is refused by the catalog's form checker, input-malformed: operation source 'fx' has platform, operation, shape: neither its bound form (profile and profileDigest) nor its unbound form (platform, operation, shape and record) (§4.4)",
        ],
    ),
    'entry-kind-other': (
        'metadata-entry',
        [('member', 'kind')],
        [
            'entries/example/fx-metadata: entry: kind is not dialect or preset',
        ],
    ),
    'entry-version-1': (
        'metadata-entry',
        [('member', 'entryVersion')],
        [
            'entries/example/fx-metadata: entry: entryVersion 1 is not 2; a version-2 reader refuses any other entry format version',
        ],
    ),
    'entry-without-kind': (
        'metadata-entry',
        [('member', 'kind')],
        [
            'entries/example/fx-metadata: entry: missing kind',
        ],
    ),
    'fixture-binding-without-unbound-source': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/binding.json'), ('path', 'manifest.json')],
        [
            'entries/example/fx-metadata: fixtures/valid: binding.json is refused: the dialect has no unbound source',
        ],
    ),
    'fixture-file-not-listed': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/notes.json')],
        [
            "entries/example/fx-metadata: fixtures/valid holds notes.json, which the manifest's file list does not name",
        ],
    ),
    'fixture-holds-a-directory': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/extra')],
        [
            'entries/example/fx-metadata: fixtures/valid holds extra, which is not a file',
            "entries/example/fx-metadata: fixtures/valid holds extra, which the manifest's file list does not name",
        ],
    ),
    'fixture-listed-file-missing': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/sources.json')],
        [
            "entries/example/fx-metadata: fixtures/valid has no sources.json, which the manifest's file list names",
        ],
    ),
    'fixture-research-unbound-without-binding': (
        'unread-version-entry',
        [('path', 'entries/example/research/fixtures/valid/binding.json'), ('path', 'manifest.json')],
        [
            'entries/example/research: fixtures/valid: binding.json is required: the dialect has an unbound source',
        ],
    ),
    'fixture-unbound-source-without-binding': (
        'unbound-entry',
        [('path', 'entries/example/fx-unbound/fixtures/valid/binding.json'), ('path', 'manifest.json')],
        [
            'entries/example/fx-unbound: fixtures/valid: binding.json is required: the dialect has an unbound source',
        ],
    ),
    'manifest-1025-rows': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest: 1025 rows, more than 1,024',
        ],
    ),
    'manifest-digest-malformed': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            "entries/example/fx-metadata: entry.json does not match the manifest's entryDigest",
            'manifest[0]: entryDigest is not a sha256 digest',
        ],
    ),
    'manifest-entry-id-differs': (
        'metadata-entry',
        [('member', 'id')],
        [
            "entries/example/fx-metadata: entry: id example.fx-other is not its path's example.fx-metadata",
        ],
    ),
    'manifest-entry-unlisted': (
        'metadata-entry',
        [('path', 'entries/example/fx-unlisted')],
        [
            'entries/example/fx-unlisted: an entry the manifest does not list',
        ],
    ),
    'manifest-files-name-twice': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: files names profiles.json twice',
        ],
    ),
    'manifest-files-six-names': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: files lists 6 names, not 3 to 5',
            'manifest[0].fixtures[0]: files names case.json twice',
            'manifest[0].fixtures[0]: files names sources.json twice',
        ],
    ),
    'manifest-files-two-names': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/profiles.json'), ('path', 'entries/example/fx-metadata/fixtures/valid/sources.json'), ('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: files lacks profiles.json',
            'manifest[0].fixtures[0]: files lists 2 names, not 3 to 5',
        ],
    ),
    'manifest-files-unknown-name': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/notes.json'), ('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: files names notes.json, which no fixture holds',
        ],
    ),
    'manifest-files-without-case': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/valid/case.json'), ('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: files lacks case.json',
        ],
    ),
    'manifest-fixture-with-another-member': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0].fixtures[0]: unknown member preparationDigest',
        ],
    ),
    'manifest-fixtures-out-of-order': (
        'metadata-entry',
        [('path', 'entries/example/fx-metadata/fixtures/again'), ('member', 'fixtures'), ('path', 'manifest.json')],
        [
            "entries/example/fx-metadata: the manifest's fixtures are again, valid, not entry.json's valid, again in its order",
        ],
    ),
    'manifest-id-malformed': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'entries/example/fx-metadata: manifest id Example.fx-metadata is not example.fx-metadata',
            'manifest[0]: id is not of the entry id form',
        ],
    ),
    'manifest-id-twice': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest: an id is listed twice',
        ],
    ),
    'manifest-out-of-byte-order': (
        'metadata-entry',
        [('path', 'entries/example/a-first'), ('path', 'manifest.json')],
        [
            'manifest: not in id byte order',
        ],
    ),
    'manifest-over-1-mib': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest.json: 1048577 bytes, over 1 MiB (1,048,576 bytes)',
        ],
    ),
    'manifest-path-not-split-at-first-dot': (
        'metadata-entry',
        [('path', 'entries/example.fx'), ('path', 'entries/example'), ('path', 'manifest.json')],
        [
            'manifest[0]: path is not entries/example/fx.metadata, the path its id names',
        ],
    ),
    'manifest-path-trailing-slash': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'entries/example/fx-metadata/: listed in the manifest, no such entry',
            'entries/example/fx-metadata: an entry the manifest does not list',
            'manifest[0]: path is not entries/example/fx-metadata, the path its id names',
        ],
    ),
    'manifest-row-kind-other': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0]: kind is not dialect or preset',
        ],
    ),
    'manifest-row-member-twice': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest.json: a member name is given twice',
        ],
    ),
    'manifest-row-with-another-member': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0]: unknown member title',
        ],
    ),
    'manifest-row-without-entry': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'entries/example/fx-missing: listed in the manifest, no such entry',
        ],
    ),
    'manifest-row-without-fixtures': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0]: missing fixtures',
        ],
    ),
    'manifest-row-without-kind': (
        'metadata-entry',
        [('path', 'manifest.json')],
        [
            'manifest[0]: missing kind',
        ],
    ),
    'preset-dialect-changed': (
        'preset-entry',
        [('path', 'entries/example/company-research/dialect.json')],
        [
            "entries/example/company-research: dialect.digest is not the digest of dialect.json's canonical bytes",
            "entries/example/company-research: dialect.json does not match the manifest's dialectDigest",
        ],
    ),
    'preset-dialect-version-2': (
        'preset-entry',
        [('member', 'dialect')],
        [
            "entries/example/company-research: dialect: a preset's dialectVersion is 3",
            "entries/example/company-research: dialect: dialectVersion is not the document's own version",
            'entries/example/company-research: entry: sourceKinds names research, not a kind of dialect version 2',
        ],
    ),
    'preset-direction-both': (
        'preset-entry',
        [('member', 'direction')],
        [
            "entries/example/company-research: entry: a preset's direction is input, not 'both'",
            'entries/example/company-research: entry: output is required for direction both',
            'entries/example/company-research: no output.json',
            'entries/example/company-research: the manifest lacks outputDigest for direction both',
        ],
    ),
    'preset-holds-a-binding-document': (
        'preset-entry',
        [('path', 'entries/example/company-research/binding.json')],
        [
            "entries/example/company-research: a preset's directory holds binding.json, and holds only entry.json, dialect.json and README.md",
        ],
    ),
    'preset-holds-a-fixture-directory': (
        'preset-entry',
        [('path', 'entries/example/company-research/fixtures')],
        [
            "entries/example/company-research: a preset's directory holds fixtures, and holds only entry.json, dialect.json and README.md",
        ],
    ),
    'preset-operation-bound': (
        'preset-entry',
        [('path', 'entries/example/company-research/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/company-research: a preset's source 'registry' is bound: every source with an unbound form is unbound",
        ],
    ),
    'preset-requires-input-profile': (
        'preset-entry',
        [('member', 'requires')],
        [
            'entries/example/company-research: requires: a preset names no profile, and this one names inputProfile',
        ],
    ),
    'preset-research-bound': (
        'preset-entry',
        [('path', 'entries/example/company-research/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/company-research: a preset's source 'primary' is bound: every source with an unbound form is unbound",
        ],
    ),
    'preset-row-fixtures-not-empty': (
        'preset-entry',
        [('path', 'manifest.json')],
        [
            "entries/example/company-research: the manifest's fixtures are valid, not entry.json's none in its order",
            "manifest[0]: a preset row's fixtures is not the empty array",
        ],
    ),
    'preset-row-kind-dialect': (
        'preset-entry',
        [('path', 'manifest.json')],
        [
            "entries/example/company-research: the manifest's kind dialect is not entry.json's kind preset",
        ],
    ),
    'preset-row-with-output-digest': (
        'preset-entry',
        [('path', 'manifest.json')],
        [
            'entries/example/company-research: the manifest has outputDigest for direction input',
            'manifest[0]: a preset row has no outputDigest',
        ],
    ),
    'preset-source-kind-not-read': (
        'preset-entry',
        [('path', 'entries/example/company-research/dialect.json'), ('member', 'dialect'), ('path', 'manifest.json')],
        [
            "entries/example/company-research: dialect.json is refused by the catalog's form checker, kind-unread: source kind web is not one the catalog's form checker reads; it reads operation, selected-file and research",
        ],
    ),
    'preset-verification-not-empty': (
        'preset-entry',
        [('member', 'verification')],
        [
            "entries/example/company-research: entry: a preset's verification is the empty array",
        ],
    ),
    'preset-with-fixtures': (
        'preset-entry',
        [('member', 'fixtures')],
        [
            'entries/example/company-research: entry: a preset has no fixtures',
        ],
    ),
    'preset-with-pack': (
        'preset-entry',
        [('member', 'pack')],
        [
            'entries/example/company-research: entry: a preset has no pack',
        ],
    ),
    'source-kinds-not-the-documents': (
        'metadata-entry',
        [('member', 'sourceKinds')],
        [
            "entries/example/fx-metadata: sourceKinds is operation, selected-file; the document's sources are of operation",
        ],
    ),
    'upgrade-33-members': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            'entries/example/fx-metadata: upgrade has 33 members, over 32',
        ],
    ),
    'upgrade-empty': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            'entries/example/fx-metadata: upgrade has no members',
        ],
    ),
    'upgrade-key-not-a-digest': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            "entries/example/fx-metadata: upgrade: the key 'v0.1.0' is not a sha256 digest",
        ],
    ),
    'upgrade-key-not-in-an-earlier-release': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            "entries/example/fx-metadata: upgrade: the key 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' is the entryDigest of no row with id example.fx-metadata in an earlier release's manifest",
        ],
    ),
    'upgrade-key-of-another-entry': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            "entries/example/fx-metadata: upgrade: the key 'sha256:5d6cb179820cebbabcdb568b158ff29e2a66a328c02ed734c4293d3234b8a7b4' is the entryDigest of no row with id example.fx-metadata in an earlier release's manifest",
        ],
    ),
    'upgrade-note-2049-characters': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            "entries/example/fx-metadata: upgrade: the note for 'sha256:52895deee7e135c99f48553cfcd01586aafcfea29232c03698aac6bec1ca6c31' is 2049 characters, over 2048",
        ],
    ),
    'upgrade-note-empty': (
        'metadata-entry',
        [('member', 'upgrade')],
        [
            "entries/example/fx-metadata: upgrade: the note for 'sha256:52895deee7e135c99f48553cfcd01586aafcfea29232c03698aac6bec1ca6c31' is empty",
        ],
    ),
    'verification-reader-bad-commit': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: readers[0]'s commit 'main' is not 7 to 40 lower-case hexadecimal digits",
        ],
    ),
    'verification-reader-dot-segment': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: readers[0] 'Judgment-Pack/judgment-pack-spec/tools/./dialect_verify.py@18aef51aa66a012e96cf9395471109bd77e037db' has an empty, '.' or '..' path segment",
        ],
    ),
    'verification-reader-empty-path': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: readers[0] 'Judgment-Pack/judgment-pack-spec/@18aef51aa66a012e96cf9395471109bd77e037db' has no path",
        ],
    ),
    'verification-reader-segment-character': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: readers[0] 'Judgment-Pack/judgment-pack-spec/tools/dialect+verify.py@18aef51aa66a012e96cf9395471109bd77e037db' has a path segment of a character outside [A-Za-z0-9_.-]",
        ],
    ),
    'verification-reader-without-commit': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: readers[0] 'Judgment-Pack/judgment-pack-spec/tools/dialect_verify.py' has no @<commit>",
        ],
    ),
    'verification-runner-leading-zero': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: runner 'v0.011.0' is not a release tag (vMAJOR.MINOR.PATCH, ASCII, no leading zeroes)",
        ],
    ),
    'verification-runtime-prerelease': (
        'metadata-entry',
        [('member', 'verification')],
        [
            "entries/example/fx-metadata: verification[0]: runtime 'v0.32.0-rc.1' is not a release tag (vMAJOR.MINOR.PATCH, ASCII, no leading zeroes)",
        ],
    ),
}


def restore(tree: Path, base: Path, steps) -> None:
    """Revert a refused tree's one change, in place (a scratch copy)."""
    for step in steps:
        if step[0] == "member":
            # The member restored from the base, or removed where the base has none, in the base's order.
            entry_dir = tree / Tree(base).entry_dirs()[0].relative_to(base)
            entry = load_strict((entry_dir / "entry.json").read_bytes())
            original = load_strict((Tree(base).entry_dirs()[0] / "entry.json").read_bytes())
            entry = {k: original[k] if k == step[1] else entry[k] for k in original if k == step[1] or k in entry}
            (entry_dir / "entry.json").write_bytes((json.dumps(entry, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
            rows = load_strict((tree / "manifest.json").read_bytes())
            for row in rows:
                if (tree / row["path"] / "entry.json").is_file():
                    row["entryDigest"] = digest((tree / row["path"] / "entry.json").read_bytes())
            (tree / "manifest.json").write_bytes((json.dumps(rows, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        elif step[0] == "path":
            import shutil

            target, source = tree / step[1], base / step[1]
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
            if source.is_dir():
                shutil.copytree(source, target)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        else:
            raise ValueError(f"no such step {step[0]}")


def tree_files(base: Path) -> dict[str, bytes]:
    """Every file of a tree but its own README.md, by relative path."""
    return {
        p.relative_to(base).as_posix(): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.relative_to(base).as_posix() != "README.md"
    }


class RefusedExamples(unittest.TestCase):
    """tests/fixtures/refused/: one tree per refusal, each refused with exactly its own problems, and each
    a passing example once its one change is reverted."""

    def test_every_refused_tree_is_named_here(self):
        self.assertEqual(sorted(p.name for p in REFUSED.iterdir() if p.is_dir()), sorted(REFUSED_TREES))

    def test_each_tree_is_refused_with_exactly_its_problems(self):
        for name, (_, _, expected) in REFUSED_TREES.items():
            with self.subTest(name):
                self.assertEqual(sorted(tree_problems(Tree(REFUSED / name))), sorted(expected))

    def test_no_two_trees_share_a_problem(self):
        for name, (_, _, expected) in REFUSED_TREES.items():
            own = set(expected) - {p for other, (_, _, e) in REFUSED_TREES.items() if other != name for p in e}
            with self.subTest(name):
                self.assertTrue(own, f"{name} has no problem of its own")

    def test_each_tree_passes_once_its_change_is_reverted(self):
        import shutil
        import tempfile

        for name, (base_name, steps, _) in REFUSED_TREES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                base = EXAMPLE.parent / base_name
                tree = Path(tmp) / name
                self.assertTrue((REFUSED / name).is_dir(), f"no refused tree {name}")
                shutil.copytree(REFUSED / name, tree)
                restore(tree, base, steps)
                self.assertEqual(tree_problems(Tree(tree)), [])
                restored, original = tree_files(tree), tree_files(base)
                self.assertEqual(sorted(restored), sorted(original))
                self.assertEqual([p for p in restored if restored[p] != original[p]], [])


class BindingDocument(unittest.TestCase):
    """binding.json's bound and form, held by the catalog itself (RFC 0018 §12, §4.4; RFC 0019 §3)."""

    def copy(self, tmp):
        import shutil

        shutil.copytree(UNBOUND, Path(tmp), dirs_exist_ok=True)
        tree = Tree(Path(tmp))
        fixture = tree.entry_dirs()[0] / "fixtures" / "valid"
        return tree, fixture / "binding.json", load_strict((fixture / "binding.json").read_bytes())

    def test_65536_bytes_is_admitted_and_65537_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree, path, document = self.copy(tmp)
            body = canon(document)
            path.write_bytes(b"{" + b" " * (65536 - len(body)) + body[1:])
            self.assertEqual(path.stat().st_size, 65536)
            self.assertEqual(tree_problems(tree), [])
            path.write_bytes(b"{" + b" " * (65537 - len(body)) + body[1:])
            self.assertEqual(len(tree_problems(tree)), 1)

    def test_the_form(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree, path, document = self.copy(tmp)
            source = document["sources"]["fx"]
            refused = {
                "not an object": [document],
                "without sources": {"dialect": document["dialect"]},
                "dialect another digest": {**document, "dialect": "sha256:" + "0" * 64},
                "dialect not a digest": {**document, "dialect": document["dialect"].upper()},
                "sources an array": {**document, "sources": [source]},
                "source value not closed": {**document, "sources": {"fx": {**source, "shape": "mcp"}}},
                "source value without profileDigest": {**document, "sources": {"fx": {"profile": "fx"}}},
                "profile empty": {**document, "sources": {"fx": {**source, "profile": ""}}},
                "profileDigest malformed": {**document, "sources": {"fx": {**source, "profileDigest": "fx"}}},
            }
            for label, changed in refused.items():
                with self.subTest(label):
                    path.write_bytes(canon(changed))
                    self.assertTrue(tree_problems(tree), label)
            path.write_bytes(b'{"dialect":"x","dialect":"y","sources":{}}')
            self.assertTrue(tree_problems(tree))
            path.write_bytes(canon(document))
            self.assertEqual(tree_problems(tree), [])


class ReaderLocators(unittest.TestCase):
    """verification[].readers: `<owner>/<name>/<path>@<commit>`, RFC 0019 §3's reader-locator grammar (#166):
    path segments of [A-Za-z0-9_.-]+, none empty, `.` or `..`; the last `@` separates the commit."""

    def test_well_formed_locators(self):
        for reader in [
            READER,
            "Judgment-Pack/judgment-pack-runner/cmd/verify-run@82116bf",
            "a/b/c@" + "0" * 40,
            "Owner_1/name.with-dots/a/.b/b..c/b.py@abcdef0",
            "o" * 100 + "/n/p@1234567",
            "o/" + "n" * 100 + "/p@1234567",
            "o/n/" + "p" * 188 + "@1234567",
        ]:
            with self.subTest(reader):
                self.assertEqual(reader_problems("r", reader), [])

    def test_the_200_character_bound(self):
        self.assertEqual(len("o/n/" + "p" * 188 + "@1234567"), 200)
        self.assertEqual(reader_problems("r", "o/n/" + "p" * 189 + "@1234567"), ["r is 201 characters, over 200"])

    def test_malformed_locators(self):
        for reader in [
            "r", "", "a/b/c", "a/b/c@", "a/b/c@123456", "a/b/c@" + "0" * 41, "a/b/c@ABCDEF0", "a/b/c@main",
            "a/b@1234567", "a/b/@1234567", "/b/c@1234567", "a//c@1234567", "a/b/c//d@1234567", "a/b/c/@1234567",
            "a/b/../c@1234567", "a/b/c/..@1234567", "o" * 101 + "/b/c@1234567", "a/" + "n" * 101 + "/c@1234567",
            "a/b/./c@1234567", "a/b/.@1234567", "a/b/c+d@1234567", "a/b/c d@1234567", "a/b/c:d@1234567", "a/b/é@1234567",
            "a/b/c@d@1234567",
            "a b/c/d@1234567", "a/b/c@1234567\n", "o/n/" + "p" * 189 + "@1234567", None, 7,
        ]:
            with self.subTest(repr(reader)):
                self.assertTrue(reader_problems("r", reader))


PRESET = EXAMPLE.parent / "preset-entry"
UNREAD_VERSION = EXAMPLE.parent / "unread-version-entry"


def scratch_tree(source: Path, tmp: str) -> Tree:
    import shutil

    shutil.copytree(source, Path(tmp), dirs_exist_ok=True)
    return Tree(Path(tmp))


def rewrite_entry(tree: Tree, alter) -> None:
    """Change the tree's one entry.json and let the manifest's entryDigest follow its bytes."""
    directory = tree.entry_dirs()[0]
    entry = load_strict((directory / "entry.json").read_bytes())
    alter(entry)
    (directory / "entry.json").write_bytes((json.dumps(entry, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    rows = tree.manifest()
    rows[0]["entryDigest"] = digest((directory / "entry.json").read_bytes())
    tree.manifest_path.write_bytes((json.dumps(rows, indent=2) + "\n").encode("utf-8"))


def rewrite_dialect(tree: Tree, alter) -> None:
    """Change the tree's dialect.json, and let dialect.digest, entryDigest and dialectDigest follow."""
    directory = tree.entry_dirs()[0]
    document = load_strict((directory / "dialect.json").read_bytes())
    alter(document)
    data = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    (directory / "dialect.json").write_bytes(data)
    rewrite_entry(tree, lambda e: e["dialect"].update(digest=digest(canon(document))))
    rows = tree.manifest()
    rows[0]["dialectDigest"] = digest(data)
    tree.manifest_path.write_bytes((json.dumps(rows, indent=2) + "\n").encode("utf-8"))


class EntryFormatVersion(unittest.TestCase):
    """RFC 0019 §3: entry format version 2 requires `kind`; a version-2 reader refuses a version-1 entry and a
    version-1 manifest, and the empty manifest fits both forms."""

    def test_every_example_is_of_version_2_with_its_kind(self):
        for tree in [EXAMPLE, METADATA, UNBOUND, PRESET, UNREAD_VERSION] + [EXAMPLE.parent / n for n in ("unread-kind-entry", "both-entry", "output-entry")]:
            with self.subTest(tree.name):
                entry = load_strict((Tree(tree).entry_dirs()[0] / "entry.json").read_bytes())
                row = Tree(tree).manifest()[0]
                self.assertEqual((entry["entryVersion"], entry["kind"]), (2, row["kind"]))
                self.assertEqual(entry["kind"], "preset" if tree == PRESET else "dialect")

    def test_a_version_1_entry_is_refused(self):
        published = EXAMPLE_RELEASES / "v0.1.0" / "entries/example/fx-convert/entry.json"
        entry = load_strict(published.read_bytes())
        self.assertEqual((entry["entryVersion"], "kind" in entry), (1, False))
        self.assertEqual(
            entry_problems(entry, "example.fx-convert", 2),
            ["entry: entryVersion 1 is not 2; a version-2 reader refuses any other entry format version"],
        )

    def test_a_version_1_manifest_is_refused(self):
        rows = load_strict((EXAMPLE_RELEASES / "v0.1.0" / "manifest.json").read_bytes())
        self.assertEqual(manifest_problems(rows), [f"manifest[{i}]: missing kind" for i in range(len(rows))])

    def test_the_empty_manifest_fits_both_forms(self):
        self.assertEqual(manifest_problems([]), [])
        self.assertEqual(release_rows(b"[]\n"), [])

    def test_a_version_1_tree_is_refused_whole(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(EXAMPLE, tmp)
            directory = tree.entry_dirs()[0]
            published = EXAMPLE_RELEASES / "v0.1.0"
            (directory / "entry.json").write_bytes((published / "entries/example/fx-convert/entry.json").read_bytes())
            rows = [r for r in load_strict((published / "manifest.json").read_bytes()) if r["id"] == "example.fx-convert"]
            tree.manifest_path.write_bytes((json.dumps(rows, indent=2) + "\n").encode("utf-8"))
            refused_entry = "entries/example/fx-convert: entry: entryVersion 1 is not 2; a version-2 reader refuses any other entry format version"
            self.assertEqual(sorted(tree_problems(tree)), [refused_entry, "manifest[0]: missing kind"])
            rows[0]["kind"] = "dialect"
            tree.manifest_path.write_bytes((json.dumps(rows, indent=2) + "\n").encode("utf-8"))
            self.assertEqual(tree_problems(tree), [refused_entry])


class PresetExample(unittest.TestCase):
    """RFC 0019 §3: a preset has direction input, a dialect of version 3 with every bindable source unbound,
    exactly entry.json, dialect.json and README.md, no pack, no fixtures, an empty verification and no profile
    in requires; it is checked by its document's form, its digests and the scans only."""

    tree = Tree(PRESET)

    def entry(self):
        return load_strict((self.tree.entry_dirs()[0] / "entry.json").read_bytes())

    def test_example_holds_to_the_format(self):
        self.assertEqual(tree_problems(self.tree), [])
        directory = self.tree.entry_dirs()[0]
        self.assertEqual(sorted(p.name for p in directory.iterdir()), sorted(PRESET_FILES))
        document = load_strict((directory / "dialect.json").read_bytes())
        self.assertEqual({s["kind"] for s in document["sources"]}, {"operation", "research"})
        self.assertEqual(
            {s["name"]: dialect_form.classification(s) for s in document["sources"]},
            {"registry": "unbound", "primary": "unbound", "secondary": "unbound", "combined": "unbound"},
        )
        self.assertIn("sources", document["sources"][-1]["read"])  # a reconciliation read

    def test_its_row(self):
        row = self.tree.manifest()[0]
        self.assertEqual(sorted(row), ["dialectDigest", "entryDigest", "fixtures", "id", "kind", "path"])
        self.assertEqual((row["kind"], row["fixtures"]), ("preset", []))

    def test_the_verifier_is_not_used(self):
        # The verifier needs fixture inputs and a binding document (RFC 0019 §3): a preset has neither.
        self.assertEqual(verifier_results(self.tree), [])

    def test_each_rule_in_place(self):
        entry = self.entry()
        ident = "example.company-research"
        self.assertEqual(entry_problems(entry, ident, 3), [])
        record = {"date": "2026-10-14", "runner": "v0.11.0", "runtime": "v0.32.0", "readers": [READER], "result": "agree"}
        d = "sha256:" + "a" * 64
        refused = {
            "a pack": ({**entry, "pack": {"id": "https://example.com/packs/p", "versions": "1"}}, "entry: a preset has no pack"),
            "fixtures": ({**entry, "fixtures": []}, "entry: a preset has no fixtures"),
            "direction output": ({**entry, "direction": "output"}, "entry: a preset's direction is input, not 'output'"),
            "direction both": ({**entry, "direction": "both"}, "entry: a preset's direction is input, not 'both'"),
            "a verification record": ({**entry, "verification": [record]}, "entry: a preset's verification is the empty array"),
            "dialectVersion 2": ({**entry, "dialect": {**entry["dialect"], "dialectVersion": 2}}, "dialect: a preset's dialectVersion is 3"),
            "dialectVersion 4": ({**entry, "dialect": {**entry["dialect"], "dialectVersion": 4}}, "dialect: a preset's dialectVersion is 3"),
            "an input profile": ({**entry, "requires": {"inputProfile": d}}, "requires: a preset names no profile, and this one names inputProfile"),
            "a connection profile": ({**entry, "requires": {"connectionProfile": d}}, "requires: a preset names no profile, and this one names connectionProfile"),
        }
        for label, (candidate, problem) in refused.items():
            with self.subTest(label):
                self.assertIn(problem, entry_problems(candidate, ident, 3))
        self.assertEqual(entry_problems({**entry, "requires": {"platform": "example-registry"}}, ident, 3), [])

    def test_its_document_is_held_by_the_catalogs_form_checker(self):
        import tempfile

        for label, alter, fragment in [
            ("research of another field type", lambda d: d["sources"][1]["fields"][0].update(type="float"), "type is not one of"),
            ("a research source partly bound", lambda d: d["sources"][1].update(profile="ai"), "partial binding members"),
            ("an operation partly unbound", lambda d: d["sources"][0].pop("record"), "neither its bound form"),
            ("a reconciliation without its guards for one field", lambda d: d["sources"][3]["read"]["rule"]["clauses"][4].update(when={"op": "always"}), "has no guard for /current/fields/employee-count"),
            ("a version-2 document", lambda d: d.update(version=2), "a version-2 document names source kind research"),
            ("an http source", lambda d: d["sources"].append({"name": "h", "kind": "http", "profile": "h", "profileDigest": "sha256:" + "a" * 64, "maxAge": 60, "method": "GET", "path": "items", "read": {"copy": {"facts": [{"target": "/h", "source": ""}], "evidence": []}}}), "kind-unread: source kind http"),
            ("an http source held to its form first", lambda d: d["sources"].append({"name": "h", "kind": "http", "read": {}}), "input-malformed: source 'h' has no member maxAge"),
        ]:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = scratch_tree(PRESET, tmp)
                rewrite_dialect(tree, alter)
                problems = tree_problems(tree)
                self.assertTrue(any("refused by the catalog's form checker" in p and fragment in p for p in problems), problems)

    def test_a_bound_source_is_refused(self):
        import tempfile

        def bind(document):
            source = document["sources"][0]
            for name in ("platform", "operation", "shape", "record"):
                source.pop(name)
            source.update(profile="registry", profileDigest="sha256:" + "a" * 64)

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(PRESET, tmp)
            rewrite_dialect(tree, bind)
            self.assertEqual(tree_problems(tree), [
                "entries/example/company-research: a preset's source 'registry' is bound: every source with an unbound form is unbound",
            ])

    def test_a_preset_directory_holds_three_files(self):
        import tempfile

        for extra in ("fixtures/valid/case.json", "binding.json", "output.json", "notes.md"):
            with self.subTest(extra), tempfile.TemporaryDirectory() as tmp:
                tree = scratch_tree(PRESET, tmp)
                path = tree.entry_dirs()[0] / extra
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"{}")
                name = extra.split("/")[0]
                self.assertIn(
                    f"entries/example/company-research: a preset's directory holds {name}, and holds only entry.json, dialect.json and README.md",
                    tree_problems(tree),
                )


class CatalogFormChecker(unittest.TestCase):
    """RFC 0019 §§3–4: every dialect.json, of either kind, is held to RFC 0018 §§2–8 and 12 as round 8 amends
    them by the catalog's own form checker, also when every fixture of the entry is skipped."""

    def test_every_example_document_passes_it(self):
        for path in sorted((EXAMPLE.parent).glob("*/entries/*/*/dialect.json")):
            with self.subTest(path.relative_to(EXAMPLE.parent).as_posix()):
                self.assertIsNone(dialect_form.check(path.read_bytes()))

    def test_a_dialect_entry_whose_fixtures_are_all_skipped_is_still_form_checked(self):
        import tempfile

        # The unbound example's one fixture is skipped by the pinned verifier (dialect version 3).
        for label, alter, fragment in [
            ("a member of version 2 alone", lambda d: d.update(provider=""), "provider is a member of version 2 alone"),
            ("a source parameter from a later source", lambda d: d["sources"][0].update(parameters={"x": {"from": "later", "pointer": "/x", "type": "string"}}), "is not an earlier source"),
            ("a rule with no always clause", lambda d: d["sources"][0].update(read={"rule": {"ruleVersion": "1", "parameters": {}, "clauses": [{"when": {"op": "exists", "field": "/x"}, "claim": {"facts": [], "evidence": {}, "acquisitionStatus": "unknown"}, "reason": "r"}]}}), "last clause's when"),
            ("an admission of a target no source writes", lambda d: d.update(admits={"facts": {"/nothing": ["record"]}}), "which no source writes"),
        ]:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = scratch_tree(UNBOUND, tmp)
                rewrite_dialect(tree, alter)
                problems = tree_problems(tree)
                self.assertTrue(any("refused by the catalog's form checker, input-malformed" in p and fragment in p for p in problems), problems)

    def test_a_version_or_kind_the_checker_does_not_read_is_refused_by_name(self):
        import tempfile

        for label, alter, expected in [
            ("dialect version 4", lambda d: d.update(version=4), "version-unread: dialect version 4 is not one the catalog's form checker reads"),
            ("source kind sql", lambda d: d["sources"].append({"name": "q", "kind": "sql", "profile": "q", "profileDigest": "sha256:" + "a" * 64, "maxAge": 60, "statement": "select 1", "bindings": [], "read": {"copy": {"facts": [], "evidence": []}}}), "kind-unread: source kind sql is not one the catalog's form checker reads"),
            ("source kind sql held to its form first", lambda d: d["sources"].append({"name": "q", "kind": "sql", "read": {}}), "input-malformed: source 'q' has no member bindings"),
        ]:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tree = scratch_tree(UNBOUND, tmp)
                rewrite_dialect(tree, alter)
                self.assertTrue(any(expected in p for p in tree_problems(tree)), tree_problems(tree))

    def test_source_kinds_name_the_kinds_the_document_uses(self):
        entry = load_strict((Tree(METADATA).entry_dirs()[0] / "entry.json").read_bytes())
        document = load_strict((Tree(METADATA).entry_dirs()[0] / "dialect.json").read_bytes())
        self.assertEqual(source_kind_problems(entry, document), [])
        self.assertEqual(source_kind_problems({**entry, "sourceKinds": ["selected-file"]}, document), [
            "sourceKinds is selected-file; the document's sources are of operation",
        ])
        self.assertEqual(source_kind_problems(entry, None), [])


class UpgradeHistory(unittest.TestCase):
    """RFC 0019 §3: each upgrade key is the entryDigest of this entry's row in an earlier release's manifest, read
    from the catalog's tags; no upgrade before a first release, and no form-only fallback."""

    def entry(self):
        return load_strict((Tree(METADATA).entry_dirs()[0] / "entry.json").read_bytes())

    def test_the_example_key_is_an_earlier_releases_row(self):
        self.assertEqual(upgrade_history_problems(self.entry(), example_releases), [])

    def test_no_earlier_release_admits_no_upgrade(self):
        self.assertEqual(upgrade_history_problems(self.entry(), lambda: []), [
            "upgrade: the catalog has no earlier release, so no upgrade is admitted",
        ])
        entry = {k: v for k, v in self.entry().items() if k != "upgrade"}
        self.assertEqual(upgrade_history_problems(entry, lambda: []), [])

    def test_releases_that_cannot_be_read_admit_no_upgrade(self):
        self.assertEqual(upgrade_history_problems(self.entry(), lambda: None), [
            "upgrade: the catalog's earlier releases cannot be read (fetch its tags), so no upgrade key is admitted",
        ])
        self.assertEqual(catalog_releases(Path("/nonexistent-exchange-checkout")), None)

    def test_a_key_must_be_this_entrys_released_bytes(self):
        entry = self.entry()
        key = list(entry["upgrade"])[0]
        other = digest((EXAMPLE_RELEASES / "v0.1.0/entries/example/fx-convert/entry.json").read_bytes())
        for label, upgrade in {
            "another entry's row": {other: "n"},
            "unpublished bytes": {digest(b"an intermediate entry.json"): "n"},
            "one good key and one not": {key: "n", other: "n"},
        }.items():
            with self.subTest(label):
                problems = upgrade_history_problems({**entry, "upgrade": upgrade}, example_releases)
                self.assertEqual(len(problems), 1, problems)
        renamed = {**entry, "id": "example.other"}
        self.assertEqual(len(upgrade_history_problems(renamed, example_releases)), 1)

    def test_an_earlier_manifest_is_read_whatever_its_form(self):
        rows = [{"id": "a.b", "entryDigest": "sha256:1"}, {"id": "a.c"}, "row", {"id": 1, "entryDigest": "x"}]
        self.assertEqual(release_rows(json.dumps(rows).encode()), [("a.b", "sha256:1")])
        for data in (None, b"{}", b"not json", b"\xff", b'{"a": [}'):
            with self.subTest(data):
                self.assertEqual(release_rows(data), [])

    def test_the_release_being_made(self):
        self.assertEqual(release_being_made({"GITHUB_REF": "refs/tags/v0.2.0"}), "v0.2.0")
        for ref in ("refs/heads/main", "refs/pull/8/merge", "refs/tags/latest", "refs/tags/v0.2", ""):
            with self.subTest(ref):
                self.assertIsNone(release_being_made({"GITHUB_REF": ref}))
        self.assertIsNone(release_being_made({}))

    def test_releases_are_read_from_the_catalogs_tags(self):
        import shutil
        import tempfile

        if shutil.which("git") is None:
            self.skipTest("git is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            environment = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            identity = ["-c", "user.name=exchange-tests", "-c", "user.email=exchange-tests@example.invalid", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]

            def run(*args):
                subprocess.run(["git", "-C", str(repo), *identity, *args], check=True, capture_output=True, env=environment, timeout=60)

            def commit(manifest: bytes, message: str):
                (repo / "manifest.json").write_bytes(manifest)
                run("add", "manifest.json")
                run("commit", "-q", "-m", message)

            run("init", "-q")
            commit(b"[]\n", "empty")
            run("tag", "v0.1.0")
            version_1 = b'[{"id": "a.b", "path": "entries/a/b", "entryDigest": "sha256:one", "dialectDigest": "sha256:d", "fixtures": []}]\n'
            commit(version_1, "a version-1 row")
            run("tag", "-a", "v0.10.0", "-m", "annotated")
            commit(b'[{"id": "a.b", "kind": "dialect", "entryDigest": "sha256:two"}]\n', "a version-2 row")
            run("tag", "v0.9.0")
            run("tag", "latest")
            run("tag", "v0.9")
            tree = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"], capture_output=True, check=True, env=environment).stdout.decode().strip()
            run("tag", "v0.11.0", tree)  # a tag that names a tree, not a commit: no release
            (repo / "manifest.json").unlink()
            run("rm", "-q", "--cached", "manifest.json")
            run("commit", "-q", "-m", "no manifest")
            run("tag", "v0.12.0")

            releases = catalog_releases(repo)
            self.assertEqual([t for t, _ in releases], ["v0.1.0", "v0.9.0", "v0.10.0", "v0.12.0"])
            self.assertEqual([release_rows(d) for _, d in releases], [[], [("a.b", "sha256:two")], [("a.b", "sha256:one")], []])
            self.assertIsNone(dict(releases)["v0.12.0"])
            self.assertEqual([t for t, _ in catalog_releases(repo, "v0.10.0")], ["v0.1.0", "v0.9.0"])
            self.assertEqual(catalog_releases(repo, "v0.1.0"), [])
            entry = {"id": "a.b", "upgrade": {"sha256:one": "n"}}
            self.assertEqual(upgrade_history_problems(entry, lambda: catalog_releases(repo)), [])
            self.assertEqual(len(upgrade_history_problems(entry, lambda: catalog_releases(repo, "v0.10.0"))), 1)
            self.assertEqual(len(upgrade_history_problems(entry, lambda: catalog_releases(repo, "v0.1.0"))), 1)

    @unittest.skipUnless((ROOT / ".git").exists(), "not a git checkout: the repository's releases are read from its tags")
    def test_the_repository_reads_its_releases(self):
        self.assertIsNotNone(repository_releases())

    @unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "outside CI: whether the tags were fetched is the checkout's")
    def test_ci_fetches_the_catalogs_tags(self):
        # ci.yml checks the repository out with fetch-depth 0, so the upgrade-key check sees every earlier release.
        releases = repository_releases()
        self.assertIsNotNone(releases)
        made = release_being_made()
        if made is None or tag_order(made) > tag_order("v0.1.0"):
            self.assertIn("v0.1.0", [t for t, _ in releases])


class ResearchBindingDocument(unittest.TestCase):
    """A research source's assignment in a fixture's binding.json (RFC 0018 §4.4): exactly profile, profileDigest
    and webProfiles, the last assigning exactly the web capabilities the source requests."""

    def test_the_form(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(UNREAD_VERSION, tmp)
            path = tree.entry_dirs()[0] / "fixtures" / "valid" / "binding.json"
            document = load_strict(path.read_bytes())
            assignment = document["sources"]["recipe"]
            web = {"profile": "web", "profileDigest": "sha256:" + "b" * 64}
            refused = {
                "without webProfiles": {k: v for k, v in assignment.items() if k != "webProfiles"},
                "webProfiles an array": {**assignment, "webProfiles": []},
                "an unrequested capability": {**assignment, "webProfiles": {"page": web}},
                "answer assigned as a web capability": {**assignment, "webProfiles": {"answer": web}},
                "a member more": {**assignment, "model": "model-a"},
                "an empty profile": {**assignment, "profile": ""},
                "a profileDigest that is no digest": {**assignment, "profileDigest": "ai"},
                "the operation form": {"profile": assignment["profile"], "profileDigest": assignment["profileDigest"]},
            }
            for label, changed in refused.items():
                with self.subTest(label):
                    path.write_bytes(canon({**document, "sources": {"recipe": changed}}))
                    self.assertTrue(tree_problems(tree), label)
            path.write_bytes(canon(document))
            self.assertEqual(tree_problems(tree), [])

    def test_a_requested_capability_is_assigned(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tree = scratch_tree(UNREAD_VERSION, tmp)
            rewrite_dialect(tree, lambda d: d["sources"][0].update(capabilities=["answer", "search"]))
            directory = tree.entry_dirs()[0]
            path = directory / "fixtures" / "valid" / "binding.json"
            document = load_strict(path.read_bytes())
            document["dialect"] = load_strict((directory / "entry.json").read_bytes())["dialect"]["digest"]
            path.write_bytes(canon(document))
            self.assertEqual(tree_problems(tree), [
                "entries/example/research: fixtures/valid: binding.json: sources.recipe: webProfiles assigns nothing, not exactly the web capabilities the source requests (search)",
            ])
            document["sources"]["recipe"]["webProfiles"] = {"search": {"profile": "web", "profileDigest": "sha256:" + "b" * 64}}
            path.write_bytes(canon(document))
            self.assertEqual(tree_problems(tree), [])


class Scans(unittest.TestCase):
    def test_no_credentials_or_local_paths_in_the_tree(self):
        self.assertEqual(scan_problems(ROOT), [])

    def test_the_scan_catches_each_shape(self):
        samples = [
            _join("Bear", "er ", "a" * 24),
            _join("AK", "IA", "A" * 16),
            _join("gh", "p_", "a" * 36),
            _join("s", "k-", "a" * 24),
            _join("-----BEGIN RSA ", "PRIVATE ", "KEY-----"),
            _join("/ho", "me/someone"),
            _join("/t", "mp/x"),
        ]
        patterns = list(CREDENTIAL_SHAPES.values()) + list(LOCAL_PATHS.values())
        for sample in samples:
            self.assertTrue(any(p.search(sample.encode()) for p in patterns), sample)
        self.assertFalse(any(p.search(b"sha256:" + b"a" * 64) for p in patterns))

    def test_relative_links_resolve(self):
        self.assertEqual(link_problems(ROOT), [])

    def test_the_link_check_catches_a_missing_target(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "a.md").write_text("[ok](b.md) [no](missing.md) [web](https://example.org/x)\n```\n[skip](nothing.md)\n```\n")
            (base / "b.md").write_text("x\n")
            self.assertEqual(len(link_problems(base)), 1)


if __name__ == "__main__":
    unittest.main()

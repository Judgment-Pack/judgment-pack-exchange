"""Holds the Exchange's manifest, entries and fixtures to the entry format (docs/entry-format.md).

Standard library only. The repository's own tree (entries/ and manifest.json) is held to every
rule; the example under tests/fixtures/example-entry/ is a tree of the same shape, so the rules
that need an entry are exercised while the Exchange holds none.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

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
ABSOLUTE_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]+")
SKIPPED_DIRS = {".git", ".spec", ".venv", "node_modules", "__pycache__"}


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
    """The manifest, read within its bound (RFC 0019 §3): over 1 MiB is refused before it is parsed."""
    with path.open("rb") as handle:
        data = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("over 1 MiB (1,048,576 bytes)")
    return load_strict(data)


class Tree:
    """A manifest and the entries under it: the repository's, or an example's."""

    def __init__(self, base: Path):
        self.base = base
        self.manifest_path = base / "manifest.json"

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
        bad = closed(row, {"id", "path", "entryDigest", "fixtures"}, {"dialectDigest", "outputDigest"}, where)
        problems += bad
        if bad:
            continue
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
        if len(set(files)) != len(files):
            problems.append(f"{at}: files names a file twice")
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


def compatibility_ok(v) -> bool:
    """A compatibility value (RFC 0019 §3): 1 to 64 characters, one release tag, or `>=<lower> <<upper>`
    with exactly one space and the upper tag above the lower by their integers. No other range syntax."""
    if not text_ok(v, 1, 64):
        return False
    if release_tag_ok(v):
        return True
    match = COMPATIBILITY_RANGE.fullmatch(v)
    return match is not None and tag_order(match.group(2)) > tag_order(match.group(1))


def has_unbound_source(document) -> bool:
    """RFC 0018 §4.4: an `operation` source naming no `profile` and no `profileDigest` is unbound."""
    sources = document.get("sources") if isinstance(document, dict) else None
    return isinstance(sources, list) and any(
        isinstance(s, dict) and s.get("kind") == "operation" and not ({"profile", "profileDigest"} & s.keys())
        for s in sources
    )


def date_ok(v) -> bool:
    if not (isinstance(v, str) and DATE.fullmatch(v)):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def entry_problems(entry, directory_id: str, document_version=None, output_document_version=None) -> list[str]:
    """The entry format's types and bounds (docs/entry-format.md). Every object is closed."""
    required = {
        "entryVersion", "id", "title", "direction", "pack", "requires", "sourceKinds",
        "licence", "author", "assertion", "fixtures", "verification",
    }
    problems = closed(entry, required, {"dialect", "output", "description", "compatibility", "upgrade"}, "entry")
    if problems:
        return problems
    if not is_int(entry["entryVersion"]) or entry["entryVersion"] != 1:
        problems.append("entry: entryVersion is not the integer 1")
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

    # The authoring metadata (RFC 0019 §3): optional, and held to its bounds when present.
    if "description" in entry and not text_ok(entry["description"], 1, 4096):
        problems.append("entry: description is not a string of 1 to 4096 characters")
    if "compatibility" in entry:
        compatibility = entry["compatibility"]
        bad = closed(compatibility, {"desk", "runner"}, set(), "compatibility")
        problems += bad
        if not bad:
            for name in ("desk", "runner"):
                if not compatibility_ok(compatibility[name]):
                    problems.append(f"compatibility: {name} is not a release tag or a range of release tags of 1 to 64 characters")
    if "upgrade" in entry:
        upgrade = entry["upgrade"]
        if not (isinstance(upgrade, dict) and 1 <= len(upgrade) <= 32):
            problems.append("upgrade: not an object of 1 to 32 members")
        else:
            for key, note in upgrade.items():
                if not digest_ok(key):
                    problems.append(f"upgrade: the key {key!r} is not a sha256 digest")
                if not text_ok(note, 1, 2048):
                    problems.append(f"upgrade: the note for {key!r} is not a string of 1 to 2048 characters")

    pack = entry["pack"]
    if isinstance(pack, dict):
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

    fixtures = entry["fixtures"]
    if isinstance(fixtures, list):
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
                    problems.append(f"{where}: {name} is not a release tag (vMAJOR.MINOR.PATCH, ASCII, no leading zeroes)")
            if not (
                isinstance(v["readers"], list)
                and 1 <= len(v["readers"]) <= 8
                and all(text_ok(r, 1, 200) for r in v["readers"])
            ):
                problems.append(f"{where}: readers is not an array of 1 to 8 strings of 1 to 200 characters")
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
    for fixture in entry["fixtures"]:
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
        problems += directory_problems(dirs[path], path, by_path[path])
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


def directory_problems(directory: Path, path: str, row: dict) -> list[str]:
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
    problems += [f"{path}: {p}" for p in size_problems(directory, entry)]
    if "dialect" in canonical and canonical["dialect"][1] != entry["dialect"]["digest"]:
        problems.append(f"{path}: dialect.digest is not the digest of dialect.json's canonical bytes")
    if "output" in canonical and canonical["output"][1] != entry["output"]["digest"]:
        problems.append(f"{path}: output.digest is not the digest of output.json's canonical bytes")
    for fixture in entry["fixtures"]:
        prep = directory / fixture["path"] / "preparation.json"
        if not prep.is_file():
            problems.append(f"{path}: {fixture['path']} has no preparation.json")
        elif digest(prep.read_bytes()) != fixture["preparationDigest"]:
            problems.append(f"{path}: {fixture['name']}'s preparation.json does not match its preparationDigest")
    problems += fixture_set_problems(directory, path, entry, row, canonical.get("dialect", (None,))[0])
    return problems


def fixture_set_problems(directory: Path, path: str, entry: dict, row: dict, dialect_document) -> list[str]:
    """Each fixture directory against its row's file list and the closed set (RFC 0019 §3)."""
    listed = row.get("fixtures")
    names = [fixture["name"] for fixture in entry["fixtures"]]
    if not (isinstance(listed, list) and [f.get("name") if isinstance(f, dict) else None for f in listed] == names):
        return [f"{path}: the manifest's fixtures do not name the entry's fixtures, in its order"]
    problems = []
    unbound = has_unbound_source(dialect_document)
    for fixture, listing in zip(entry["fixtures"], listed):
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
        if unbound and BINDING not in files:
            problems.append(f"{where}: binding.json is required: the dialect has an unbound source")
        if BINDING in files and not unbound:
            problems.append(f"{where}: binding.json is refused: the dialect has no unbound source")
    return problems


def load_verifier():
    spec = importlib.util.spec_from_file_location("dialect_verify", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dialect_verify"] = module
    spec.loader.exec_module(module)
    return module


# The verifier gives a version it does not read no name of its own: input-malformed, with this detail.
VERSION_UNREAD = "a dialect version this reader does not read"


def verifier_results(tree: Tree) -> list[tuple[str, str, str]]:
    """(label, "ok" | "skip" | "problem", message) for each fixture of each entry in the tree.

    A fixture whose source kind the verifier defines and cannot recompute (`kind-unread`) is a
    skip naming the kind: its digests (rules 3 and 4) still hold it.
    """
    results: list[tuple[str, str, str]] = []
    for directory in tree.entry_dirs():
        path = directory.relative_to(tree.base).as_posix()
        entry = load_strict((directory / "entry.json").read_bytes())
        for fixture in entry["fixtures"]:
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
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            try:
                answer = json.loads(result.stdout)
            except ValueError:
                results.append((label, "problem", "the verifier printed no answer"))
                continue
            if answer.get("refused") == "kind-unread":
                kinds = ", ".join(entry["sourceKinds"])
                results.append((label, "skip", f"the verifier cannot recompute a source of kind {kinds} (kind-unread); held by its digests only"))
            elif answer.get("refused") == "input-malformed" and VERSION_UNREAD in answer.get("detail", ""):
                version = entry["dialect"]["dialectVersion"]
                results.append((label, "skip", f"the verifier does not implement dialect version {version}; held by its digests only"))
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
        tree = Tree(ROOT)
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
        ver = {"date": "2026-10-14", "runner": "v0.9.0", "runtime": "v0.32.0", "readers": ["r"], "result": "agree"}

        def with_(**changes):
            return {**entry, **changes}

        def pack(**changes):
            return {**entry["pack"], **changes}

        refused = {
            "entryVersion 2": with_(entryVersion=2),
            "entryVersion true": with_(entryVersion=True),
            "entryVersion string": with_(entryVersion="1"),
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
            "verification readers 9": with_(verification=[{**ver, "readers": ["r"] * 9}]),
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
    """A version-3 fixture is held by its digests until the verifier implements version 3."""

    tree = Tree(EXAMPLE.parent / "unread-version-entry")

    def test_digests_hold_it(self):
        self.assertEqual(tree_problems(self.tree), [])

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_skip_reason_names_the_version(self):
        results = verifier_results(self.tree)
        self.assertEqual(len(results), 1)
        _, status, message = results[0]
        self.assertEqual(status, "skip")
        self.assertIn("dialect version 3", message)

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
        self.assertEqual(sorted(row), ["dialectDigest", "entryDigest", "fixtures", "id", "outputDigest", "path"])
        _, _, _, row = self.entry_and_row(self.output)
        self.assertEqual(sorted(row), ["entryDigest", "fixtures", "id", "outputDigest", "path"])
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

    def test_the_upgrade_note_is_keyed_by_the_previous_bytes(self):
        entry = self.entry()
        previous = {k: v for k, v in entry.items() if k not in ("description", "compatibility", "upgrade")}
        stored = (json.dumps(previous, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self.assertEqual(list(entry["upgrade"]), [digest(stored)])

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
        unbound = load_strict((self.tree.entry_dirs()[0] / "dialect.json").read_bytes())
        bound = load_strict((EXAMPLE_TREE.entry_dirs()[0] / "dialect.json").read_bytes())
        self.assertTrue(has_unbound_source(unbound))
        self.assertFalse(has_unbound_source(bound))
        source = bound["sources"][0]
        self.assertFalse(has_unbound_source({"sources": [{k: v for k, v in source.items() if k != "profileDigest"}]}))
        self.assertFalse(has_unbound_source({"sources": [{"name": "f", "kind": "selected-file"}]}))
        self.assertFalse(has_unbound_source(None))

    @unittest.skipUnless(VERIFIER.is_file(), ".spec/ is absent: the preparation verifier is not checked out (CI checks it out at the pinned commit)")
    def test_the_verifier_skips_it_naming_the_version(self):
        results = verifier_results(self.tree)
        self.assertEqual([status for _, status, _ in results], ["skip"])
        self.assertIn("dialect version 3", results[0][2])


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


# One refused tree per bound, each a passing example (metadata-entry, or unbound-entry for the last of
# the binding rules) with one change; its README says which. The reason is the problem the tree must
# produce, so a tree refused for another reason does not pass.
REFUSALS = {
    'compatibility-desk-65-characters': 'compatibility: desk is not a release tag or a range',
    'compatibility-desk-empty': 'compatibility: desk is not a release tag or a range',
    'compatibility-desk-lower-bound-only': 'compatibility: desk is not a release tag or a range',
    'compatibility-not-an-object': 'compatibility: not an object',
    'compatibility-runner-leading-zero': 'compatibility: runner is not a release tag or a range',
    'compatibility-runner-non-ascii-digit': 'compatibility: runner is not a release tag or a range',
    'compatibility-runner-two-spaces': 'compatibility: runner is not a release tag or a range',
    'compatibility-runner-upper-below-lower-by-integers': 'compatibility: runner is not a release tag or a range',
    'compatibility-runner-upper-not-above-lower': 'compatibility: runner is not a release tag or a range',
    'compatibility-with-another-member': 'compatibility: unknown member gateway',
    'compatibility-without-runner': 'compatibility: missing runner',
    'description-4097-characters': 'entry: description is not a string of 1 to 4096 characters',
    'description-empty': 'entry: description is not a string of 1 to 4096 characters',
    'fixture-binding-without-unbound-source': 'fixtures/valid: binding.json is refused: the dialect has no unbound source',
    'fixture-file-not-listed': "fixtures/valid holds notes.json, which the manifest's file list does not name",
    'fixture-holds-a-directory': 'fixtures/valid holds extra, which is not a file',
    'fixture-listed-file-missing': "fixtures/valid has no sources.json, which the manifest's file list names",
    'fixture-unbound-source-without-binding': 'fixtures/valid: binding.json is required: the dialect has an unbound source',
    'manifest-1025-rows': 'manifest: 1025 rows, more than 1,024',
    'manifest-digest-malformed': 'manifest[0]: entryDigest is not a sha256 digest',
    'manifest-entry-id-differs': "entry: id example.fx-other is not its path's example.fx-metadata",
    'manifest-entry-unlisted': 'entries/example/fx-unlisted: an entry the manifest does not list',
    'manifest-files-name-twice': 'manifest[0].fixtures[0]: files names a file twice',
    'manifest-files-six-names': 'manifest[0].fixtures[0]: files lists 6 names, not 3 to 5',
    'manifest-files-two-names': 'manifest[0].fixtures[0]: files lists 2 names, not 3 to 5',
    'manifest-files-unknown-name': 'manifest[0].fixtures[0]: files names notes.json, which no fixture holds',
    'manifest-files-without-case': 'manifest[0].fixtures[0]: files lacks case.json',
    'manifest-fixture-with-another-member': 'manifest[0].fixtures[0]: unknown member preparationDigest',
    'manifest-fixtures-out-of-order': "the manifest's fixtures do not name the entry's fixtures, in its order",
    'manifest-id-malformed': 'manifest[0]: id is not of the entry id form',
    'manifest-id-twice': 'manifest: an id is listed twice',
    'manifest-out-of-byte-order': 'manifest: not in id byte order',
    'manifest-over-1-mib': 'manifest.json: over 1 MiB (1,048,576 bytes)',
    'manifest-path-not-split-at-first-dot': 'manifest[0]: path is not entries/example/fx.metadata, the path its id names',
    'manifest-path-trailing-slash': 'manifest[0]: path is not entries/example/fx-metadata, the path its id names',
    'manifest-row-member-twice': 'manifest.json: a member name is given twice',
    'manifest-row-with-another-member': 'manifest[0]: unknown member title',
    'manifest-row-without-entry': 'entries/example/fx-missing: listed in the manifest, no such entry',
    'manifest-row-without-fixtures': 'manifest[0]: missing fixtures',
    'upgrade-33-members': 'upgrade: not an object of 1 to 32 members',
    'upgrade-empty': 'upgrade: not an object of 1 to 32 members',
    'upgrade-key-not-a-digest': "upgrade: the key 'v0.1.0' is not a sha256 digest",
    'upgrade-note-2049-characters': "upgrade: the note for 'sha256:52895deee7e135c99f48553cfcd01586aafcfea29232c03698aac6bec1ca6c31' is not a string of 1 to 2048 characters",
    'upgrade-note-empty': "upgrade: the note for 'sha256:52895deee7e135c99f48553cfcd01586aafcfea29232c03698aac6bec1ca6c31' is not a string of 1 to 2048 characters",
    'verification-runner-leading-zero': 'verification[0]: runner is not a release tag',
    'verification-runtime-prerelease': 'verification[0]: runtime is not a release tag',
}


class RefusedExamples(unittest.TestCase):
    """tests/fixtures/refused/: one tree per refusal, each refused for its own reason."""

    def test_every_refused_tree_is_named_here(self):
        self.assertEqual(sorted(p.name for p in REFUSED.iterdir() if p.is_dir()), sorted(REFUSALS))

    def test_each_tree_is_refused_for_its_reason(self):
        for name, reason in REFUSALS.items():
            with self.subTest(name):
                problems = tree_problems(Tree(REFUSED / name))
                self.assertTrue(any(reason in p for p in problems), problems)


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

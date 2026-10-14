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
RUNNER_VERSION = re.compile(r"v\d+\.\d+\.\d+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LICENCE = re.compile(r"LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9][A-Za-z0-9.+-]*")
# RFC 0018 §4: the kinds of each dialect version (version 3 adds to version 2; later versions are read as 3).
KINDS_V2 = {"operation", "selected-file"}
KINDS_V3 = KINDS_V2 | {"http", "sql", "web", "research"}
MAX_TEXT_FILE = 64 * 1024
MAX_FIXTURE_DIR = 16 * 1024 * 1024
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


class Tree:
    """A manifest and the entries under it: the repository's, or an example's."""

    def __init__(self, base: Path):
        self.base = base
        self.manifest_path = base / "manifest.json"

    def manifest(self):
        return load_strict(self.manifest_path.read_bytes())

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


def manifest_problems(manifest) -> list[str]:
    if not isinstance(manifest, list):
        return ["manifest: not an array"]
    problems = []
    for i, row in enumerate(manifest):
        where = f"manifest[{i}]"
        bad = closed(row, {"id", "path", "entryDigest", "dialectDigest"}, set(), where)
        problems += bad
        if bad:
            continue
        if not id_ok(row["id"]):
            problems.append(f"{where}: id is not of the entry id form")
        if not is_str(row["path"]):
            problems.append(f"{where}: path is not a string")
        for name in ("entryDigest", "dialectDigest"):
            if not (isinstance(row[name], str) and DIGEST.fullmatch(row[name])):
                problems.append(f"{where}: {name} is not a sha256 digest")
    ids = [r["id"] for r in manifest if isinstance(r, dict) and isinstance(r.get("id"), str)]
    if ids != sorted(ids):
        problems.append("manifest: not in id order")
    if len(ids) != len(set(ids)):
        problems.append("manifest: an id is listed twice")
    return problems


def text_ok(v, low: int, high: int) -> bool:
    return isinstance(v, str) and low <= len(v) <= high


def id_ok(v) -> bool:
    return text_ok(v, 3, 128) and ID.fullmatch(v) is not None


def digest_ok(v) -> bool:
    return isinstance(v, str) and DIGEST.fullmatch(v) is not None


def date_ok(v) -> bool:
    if not (isinstance(v, str) and DATE.fullmatch(v)):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def entry_problems(entry, directory_id: str, document_version=None) -> list[str]:
    """The entry format's types and bounds (docs/entry-format.md). Every object is closed."""
    required = {
        "entryVersion", "id", "title", "direction", "pack", "dialect", "requires", "sourceKinds",
        "licence", "author", "assertion", "fixtures", "verification",
    }
    problems = closed(entry, required, set(), "entry")
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

    dialect = entry["dialect"]
    if isinstance(dialect, dict):
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
        version = None
        problems.append("dialect: not an object")

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
    if not (isinstance(kinds, list) and 1 <= len(kinds) <= 16 and all(isinstance(k, str) for k in kinds)):
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
        if not 1 <= len(fixtures) <= 64:
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
                if not (isinstance(v[name], str) and RUNNER_VERSION.fullmatch(v[name])):
                    problems.append(f"{where}: {name} is not of the form vN.N.N")
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
    by_path = {row["path"]: row for row in manifest if isinstance(row, dict) and "path" in row}
    dirs = {d.relative_to(tree.base).as_posix(): d for d in tree.entry_dirs()}
    for path in sorted(dirs.keys() - by_path.keys()):
        problems.append(f"{path}: an entry the manifest does not list")
    for path in sorted(by_path.keys() - dirs.keys()):
        problems.append(f"{path}: listed in the manifest, no such entry")
    for path in sorted(dirs.keys() & by_path.keys()):
        problems += directory_problems(dirs[path], path, by_path[path])
    return problems


def directory_problems(directory: Path, path: str, row: dict) -> list[str]:
    parts = path.split("/")
    expected_id = f"{parts[1]}.{parts[2]}"
    problems: list[str] = []
    if row.get("id") != expected_id:
        problems.append(f"{path}: manifest id {row.get('id')} is not {expected_id}")
    for name in ("entry.json", "dialect.json", "README.md"):
        if not (directory / name).is_file():
            problems.append(f"{path}: no {name}")
    if problems:
        return problems
    entry_bytes = (directory / "entry.json").read_bytes()
    dialect_bytes = (directory / "dialect.json").read_bytes()
    if digest(entry_bytes) != row.get("entryDigest"):
        problems.append(f"{path}: entry.json does not match the manifest's entryDigest")
    if digest(dialect_bytes) != row.get("dialectDigest"):
        problems.append(f"{path}: dialect.json does not match the manifest's dialectDigest")
    try:
        entry = load_strict(entry_bytes)
    except ValueError as error:
        return problems + [f"{path}: entry.json: {error}"]
    try:
        dialect_document = load_strict(dialect_bytes)
        canonical = digest(canon(dialect_document))
    except ValueError as error:
        return problems + [f"{path}: dialect.json: {error}"]
    document_version = dialect_document.get("version") if isinstance(dialect_document, dict) else None
    shape = entry_problems(entry, expected_id, document_version)
    problems += [f"{path}: {p}" for p in shape]
    if shape:
        return problems
    problems += [f"{path}: {p}" for p in size_problems(directory, entry)]
    if canonical != entry["dialect"]["digest"]:
        problems.append(f"{path}: dialect.digest is not the digest of dialect.json's canonical bytes")
    for fixture in entry["fixtures"]:
        prep = directory / fixture["path"] / "preparation.json"
        if not prep.is_file():
            problems.append(f"{path}: {fixture['path']} has no preparation.json")
        elif digest(prep.read_bytes()) != fixture["preparationDigest"]:
            problems.append(f"{path}: {fixture['name']}'s preparation.json does not match its preparationDigest")
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
        later = {**row, "id": "zz.zz"}
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

"""The catalog's own form checker for a dialect document (RFC 0019 §§3–4).

RFC 0019 holds every `dialect.json`, of an entry of kind `dialect` or `preset`, to the whole document
form of RFC 0018 §§2–8 and 12 as its round 8 amends them, by the catalog's own form checker, written to
RFC 0018's text, whether or not any fixture is replayed. This module is that checker. It is written
from the dialect's companion text, `spec/dialect.md` at judgment-pack-spec commit 00c21b5, and takes
nothing from the specification's readers: it imports none of them and runs none.

What it reads (docs/entry-format.md, "The catalog's form checker"):

- dialect versions 2 and 3; a document of another version is refused by name, `version-unread`;
- the case (§3) and the source kinds `operation`, bound and, in version 3, unbound (§4.1, §4.4);
  `selected-file`, of provider `local-file` or `google-drive` (§4.2); and `research`, in version 3, as
  round 8 gives it: requested fields, bound and unbound profile assignments, the plain read's closed
  pointer list and the reconciliation read (§4.3, §4.4, §6.4);
- reads, copies, rules and their conditions, templates, calculations, targets and admission (§§6–8);
- the byte and count bounds of §12 that a document alone carries.

The source kinds `http`, `sql` and `web`, which version 3 proposes, are not read: a document naming one
is refused by name, `kind-unread`, before the rest of its sources' forms. Nothing a profile, a case, an
acquisition or a binding document decides is checked here (`profile-mismatch`, `parameter-invalid`,
admission, the findings of §11): a form checker is given the document alone.

A refusal is `(code, detail)`, the code one of `input-over-bound`, `input-malformed`, `version-unread`
and `kind-unread` (§11), the detail naming the rule. The phases are §11's, in its order: the bounds
measured on bytes, the strict read, the bounds that are counts, the version, the form; `kind-unread`
is reported once the document's members, its case and its sources' names and kinds are read.

Standard library only.
"""

from __future__ import annotations

import json
import re

# §12: the document's bounds, and the counts a document carries.
MAX_DOCUMENT_BYTES = 131072
MAX_NESTING = 64
MAX_NUMBER_CHARACTERS = 128
MAX_EXPONENT = 308
MAX_SOURCES = 16
MAX_SCOPE = 64
MAX_CLAUSES = 64
MAX_CONDITIONS = 64
MAX_UNWRAP = 4
MAX_FACT_TARGETS = 256
MAX_EVIDENCE_TARGETS = 128
MAX_FIELDS = 64
MAX_FIELD_NAME_BYTES = 64
MAX_DESCRIPTION_BYTES = 2048
MAX_MODEL_BYTES = 256
MAX_EVIDENCE_BYTES = 4096
MAX_CAPABILITIES = 3
MAX_WEB_ASSIGNMENTS = 2
MAX_READ_SOURCES = 15
MAX_INTEGER = 2**53 - 1
# §4.1 and §7.
MAX_AGE = 86400
MAX_TABLE_AGE = 315360000

VERSIONS_READ = (2, 3)
# §4: the source kinds of each dialect version.
KINDS = {
    2: ("operation", "selected-file"),
    3: ("operation", "selected-file", "http", "sql", "web", "research"),
}
KINDS_READ = ("operation", "selected-file", "research")
TYPES = ("string", "integer", "timestamp")
CLASSES = ("asserted", "record", "generated")
AVAILABILITIES = ("present", "absent", "unknown")
ACQUISITION_STATUSES = ("resolved", "absent", "unknown")
SHAPES = ("airbyte", "mcp", "http")
PROVIDERS = ("local-file", "google-drive")
FIELD_TYPES = ("integer", "decimal", "boolean", "text", "text-list", "range")
CAPABILITIES = ("answer", "search", "page")
# §4.4: an `operation`'s catalog members and binding members; a `research` source's binding members.
CATALOG_MEMBERS = ("platform", "operation", "shape", "record")
OPERATION_BINDING = ("profile", "profileDigest")
RESEARCH_BINDING = ("profile", "profileDigest", "webProfiles")
COMMON = ("name", "kind", "parameters", "read")
RESEARCH_MEMBERS = ("maxAge", "question", "constraints", "model", "evidence", "fields", "capabilities")
ANSWER_STATUSES = ("found", "not-found", "stale", "conflicting")

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
POINTER = re.compile(r"(/([^/~]|~[01])*)*")
INDEX = re.compile(r"0|[1-9][0-9]*")
NUMBER_CHARACTERS = frozenset(b"0123456789+-.eE")
DIGITS = frozenset(b"0123456789")


class Refusal(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def malformed(detail: str) -> Refusal:
    return Refusal("input-malformed", detail)


def over_bound(detail: str) -> Refusal:
    return Refusal("input-over-bound", detail)


class NotAnInteger:
    """A number literal that is not an integer (§1): a fraction, an exponent, or a value beyond 2⁵³−1.
    The document holding one is outside the `canon` domain, and is refused in the form phase."""

    def __init__(self, literal: str):
        self.literal = literal


def check(data: bytes) -> tuple[str, str] | None:
    """The refusal of a dialect document's bytes, `(code, detail)`, or None when its form holds."""
    try:
        byte_bounds(data)
        document = read(data)
        count_bounds(document)
        version_read(document)
        Form(document).check()
    except Refusal as refusal:
        return refusal.code, refusal.detail
    return None


# ---------------------------------------------------------------------------------------------
# §12's bounds measured on bytes, before anything is read


def byte_bounds(data: bytes) -> None:
    """The document's size, its nesting, and each number literal's characters and exponent (§12)."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise over_bound(f"the document is {len(data)} bytes, over 131,072 (§12)")
    depth = 0
    in_string = False
    escaped = False
    run = bytearray()
    for byte in data:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                in_string = False
            continue
        if byte in NUMBER_CHARACTERS:
            run.append(byte)
            continue
        number_literal(run)
        run.clear()
        if byte == 0x22:
            in_string = True
        elif byte in (0x5B, 0x7B):
            depth += 1
            if depth > MAX_NESTING:
                raise over_bound(f"the document nests deeper than {MAX_NESTING} levels (§12)")
        elif byte in (0x5D, 0x7D):
            depth -= 1
    number_literal(run)


def number_literal(run: bytearray) -> None:
    """A maximal run, outside strings, of 0-9 + - . e E: at most 128 characters, and its exponent, the
    digits after its first e or E (or after the sign that follows it), of magnitude at most 308 (§12)."""
    if not run:
        return
    if len(run) > MAX_NUMBER_CHARACTERS:
        raise over_bound(f"a number literal is {len(run)} characters, over {MAX_NUMBER_CHARACTERS} (§12)")
    for position, byte in enumerate(run):
        if byte in b"eE":
            start = position + 1
            if start < len(run) and run[start] in b"+-":
                start += 1
            end = start
            while end < len(run) and run[end] in DIGITS:
                end += 1
            if end > start and int(run[start:end]) > MAX_EXPONENT:
                raise over_bound(f"a number literal's exponent is over {MAX_EXPONENT} in magnitude (§12)")
            return


# ---------------------------------------------------------------------------------------------
# §1: the strict read


def read(data: bytes):
    """Exactly one JSON value with only whitespace around it; no member name given twice in one object;
    every string well-formed Unicode, an escaped lone surrogate included (§1)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise malformed("the document is not UTF-8 (§1)") from None

    def no_duplicates(pairs):
        names = set()
        for name, _ in pairs:
            if name in names:
                raise malformed(f"the member name {name!r} is given twice in one object (§1)")
            names.add(name)
        return dict(pairs)

    def integer(literal: str):
        value = int(literal)
        return value if abs(value) <= MAX_INTEGER else NotAnInteger(literal)

    def constant(name: str):
        raise malformed(f"{name} is not a JSON value (§1)")

    try:
        document = json.loads(
            text, object_pairs_hook=no_duplicates, parse_int=integer, parse_float=NotAnInteger, parse_constant=constant
        )
    except Refusal:
        raise
    except (ValueError, RecursionError) as error:
        raise malformed(f"the document is not one JSON value (§1): {error}") from None
    well_formed(document)
    return document


def well_formed(value) -> None:
    for text in strings(value):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
            raise malformed("a string holds a lone surrogate, which is not well-formed Unicode (§1)")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for name, member in value.items():
            yield name
            yield from strings(member)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


# ---------------------------------------------------------------------------------------------
# §12's bounds that are counts, measured wherever they can be before any form


def utf8_length(text: str) -> int:
    return len(text.encode("utf-8", "surrogatepass"))


def count_bounds(document) -> None:
    if not isinstance(document, dict):
        return
    sources = document.get("sources")
    if isinstance(sources, list) and len(sources) > MAX_SOURCES:
        raise over_bound(f"the document has {len(sources)} sources, over {MAX_SOURCES} (§12)")
    case = document.get("case")
    case_parameters = case.get("parameters") if isinstance(case, dict) else None
    declared = len(case_parameters) if isinstance(case_parameters, dict) else 0
    # A scope is the case parameters, a source's own parameters and runAt (§3).
    if declared + 1 > MAX_SCOPE:
        raise over_bound(f"the case's scope holds {declared + 1} parameters, runAt included, over {MAX_SCOPE} (§3, §12)")
    facts, evidence = lenient_targets(case if isinstance(case, dict) else {}, "case")
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict):
            continue
        name = source.get("name")
        parameters = source.get("parameters")
        own = len(parameters) if isinstance(parameters, dict) else 0
        if declared + own + 1 > MAX_SCOPE:
            raise over_bound(
                f"the scope of source {name!r} holds {declared + own + 1} parameters, runAt included, over {MAX_SCOPE} (§3, §12)"
            )
        read_counts(source.get("read"), name)
        research_counts(source, name)
        more_facts, more_evidence = lenient_targets(source.get("read"), "read")
        facts += more_facts
        evidence += more_evidence
    if facts > MAX_FACT_TARGETS:
        raise over_bound(f"the document has {facts} fact targets, over {MAX_FACT_TARGETS} (§8.1, §12)")
    if evidence > MAX_EVIDENCE_TARGETS:
        raise over_bound(f"the document has {evidence} evidence targets, over {MAX_EVIDENCE_TARGETS} (§8.1, §12)")


def read_counts(read, name) -> None:
    if not isinstance(read, dict):
        return
    unwrap = read.get("unwrap")
    if isinstance(unwrap, list) and len(unwrap) > MAX_UNWRAP:
        raise over_bound(f"source {name!r}'s read has {len(unwrap)} unwrap pointers, over {MAX_UNWRAP} (§12)")
    listed = read.get("sources")
    if isinstance(listed, list) and len(listed) > MAX_READ_SOURCES:
        raise over_bound(f"source {name!r}'s read names {len(listed)} earlier sources, over {MAX_READ_SOURCES} (§6.4, §12)")
    rule = read.get("rule")
    if not isinstance(rule, dict):
        return
    clauses = rule.get("clauses")
    if not isinstance(clauses, list):
        return
    if len(clauses) > MAX_CLAUSES:
        raise over_bound(f"source {name!r}'s rule has {len(clauses)} clauses, over {MAX_CLAUSES} (§12)")
    for clause in clauses:
        if isinstance(clause, dict):
            condition_counts(clause.get("when"), name)


def condition_counts(condition, name) -> None:
    if not isinstance(condition, dict):
        return
    listed = condition.get("of")
    if condition.get("op") in ("all", "any") and isinstance(listed, list):
        if len(listed) > MAX_CONDITIONS:
            raise over_bound(f"a condition of source {name!r}'s rule lists {len(listed)} conditions, over {MAX_CONDITIONS} (§12)")
        for item in listed:
            condition_counts(item, name)
    elif condition.get("op") == "not":
        condition_counts(listed, name)


def research_counts(source: dict, name) -> None:
    if source.get("kind") != "research":
        return
    fields = source.get("fields")
    if isinstance(fields, list):
        if len(fields) > MAX_FIELDS:
            raise over_bound(f"research source {name!r} declares {len(fields)} fields, over {MAX_FIELDS} (§4.3, §12)")
        for field in fields:
            if not isinstance(field, dict):
                continue
            if isinstance(field.get("name"), str) and utf8_length(field["name"]) > MAX_FIELD_NAME_BYTES:
                raise over_bound(f"a field name of research source {name!r} is over {MAX_FIELD_NAME_BYTES} UTF-8 bytes (§4.3, §12)")
            if isinstance(field.get("description"), str) and utf8_length(field["description"]) > MAX_DESCRIPTION_BYTES:
                raise over_bound(f"a field description of research source {name!r} is over {MAX_DESCRIPTION_BYTES} UTF-8 bytes (§4.3, §12)")
    model = source.get("model")
    if isinstance(model, str) and utf8_length(model) > MAX_MODEL_BYTES:
        raise over_bound(f"research source {name!r}'s model is over {MAX_MODEL_BYTES} UTF-8 bytes (§4.3, §12)")
    evidence = source.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, str) and utf8_length(item) > MAX_EVIDENCE_BYTES:
                raise over_bound(f"an evidence instruction of research source {name!r} is over {MAX_EVIDENCE_BYTES} UTF-8 bytes (§4.3, §12)")
    capabilities = source.get("capabilities")
    if isinstance(capabilities, list) and len(capabilities) > MAX_CAPABILITIES:
        raise over_bound(f"research source {name!r} lists {len(capabilities)} capabilities, over {MAX_CAPABILITIES} (§4.3, §12)")
    web = source.get("webProfiles")
    if isinstance(web, dict) and len(web) > MAX_WEB_ASSIGNMENTS:
        raise over_bound(f"research source {name!r} has {len(web)} web assignments, over {MAX_WEB_ASSIGNMENTS} (§4.4, §12)")


def lenient_targets(holder, shape: str) -> tuple[int, int]:
    """The number of distinct fact and evidence targets a case or a read names, counted as far as its
    shape allows, for the count bound (§8.1)."""
    facts: set = set()
    evidence: set = set()
    if not isinstance(holder, dict):
        return 0, 0
    copy = holder if shape == "case" else holder.get("copy")
    if isinstance(copy, dict):
        for entry in copy.get("facts") if isinstance(copy.get("facts"), list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("target"), str):
                facts.add(entry["target"])
        for entry in copy.get("evidence") if isinstance(copy.get("evidence"), list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("requirement"), str):
                evidence.add(entry["requirement"])
    rule = holder.get("rule") if shape == "read" else None
    clauses = rule.get("clauses") if isinstance(rule, dict) else None
    for clause in clauses if isinstance(clauses, list) else []:
        claim = clause.get("claim") if isinstance(clause, dict) else None
        if not isinstance(claim, dict):
            continue
        for entry in claim.get("facts") if isinstance(claim.get("facts"), list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("pointer"), str):
                facts.add(entry["pointer"])
        if isinstance(claim.get("evidence"), dict):
            evidence.update(claim["evidence"])
    return len(facts), len(evidence)


# ---------------------------------------------------------------------------------------------
# §11, phase 4: a version the checker does not read


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def version_read(document) -> None:
    if isinstance(document, dict) and is_int(document.get("version")) and document["version"] not in VERSIONS_READ:
        raise Refusal(
            "version-unread",
            f"dialect version {document['version']} is not one the catalog's form checker reads; it reads versions 2 and 3",
        )


# ---------------------------------------------------------------------------------------------
# The classification of a source (§4.4; RFC 0019 §3)


def classification(source) -> str | None:
    """`unbound`, `bound` or `partial` for a source of kind `operation` or `research`; None for another.

    An `operation` is unbound when it has all of platform, operation, shape and record and neither
    profile nor profileDigest, and bound when it has both binding members and none of the four. A
    `research` source is unbound when it has none of profile, profileDigest and webProfiles, and bound
    when it has all three and no catalog member. Anything else is partial, input-malformed."""
    if not isinstance(source, dict):
        return None
    kind = source.get("kind")
    catalog = [m for m in CATALOG_MEMBERS if m in source]
    if kind == "operation":
        binding = [m for m in OPERATION_BINDING if m in source]
        if len(catalog) == len(CATALOG_MEMBERS) and not binding:
            return "unbound"
        if len(binding) == len(OPERATION_BINDING) and not catalog:
            return "bound"
        return "partial"
    if kind == "research":
        binding = [m for m in RESEARCH_BINDING if m in source]
        if catalog:
            return "partial"
        if not binding:
            return "unbound"
        return "bound" if len(binding) == len(RESEARCH_BINDING) else "partial"
    return None


def unbound_sources(document) -> dict[str, dict]:
    """The sources of a document that are unbound under §4.4, by name. A source whose members are
    partial is not unbound; the form check refuses it."""
    sources = document.get("sources") if isinstance(document, dict) else None
    found = {}
    for source in sources if isinstance(sources, list) else []:
        if classification(source) == "unbound" and isinstance(source.get("name"), str):
            found[source["name"]] = source
    return found


# ---------------------------------------------------------------------------------------------
# The form: §§2–8


def pointer_ok(value) -> bool:
    return isinstance(value, str) and POINTER.fullmatch(value) is not None


def fact_target_ok(value) -> bool:
    return pointer_ok(value) and value != ""


def tokens(pointer: str) -> list[str]:
    return [t.replace("~1", "/").replace("~0", "~") for t in pointer.split("/")[1:]]


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def non_empty(value) -> bool:
    return isinstance(value, str) and value != ""


def digest_ok(value) -> bool:
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def canon_domain(value, where: str) -> None:
    if isinstance(value, NotAnInteger):
        raise malformed(f"{where} holds the number {value.literal}, not an integer (§1): the document is outside the canon domain (§2)")
    if isinstance(value, dict):
        for member in value.values():
            canon_domain(member, where)
    elif isinstance(value, list):
        for item in value:
            canon_domain(item, where)


def closed(value, where: str, required: tuple | set, optional: tuple | set = ()) -> dict:
    if not isinstance(value, dict):
        raise malformed(f"{where} is not an object")
    for name in sorted(set(required) - value.keys()):
        raise malformed(f"{where} has no member {name}")
    for name in sorted(value.keys() - set(required) - set(optional)):
        raise malformed(f"{where} has the member {name!r}, which its form does not list")
    return value


class Form:
    """One document's form (§§2–8), checked in order; the first rule broken refuses it."""

    def __init__(self, document):
        self.document = document
        self.version = None
        self.case_types: dict[str, str] = {}
        self.fact_targets: dict[str, list[str]] = {}
        self.evidence_targets: dict[str, list[str]] = {}
        self.kinds: dict[str, str] = {}
        self.fields: dict[str, list[str]] = {}

    # The document (§2) -----------------------------------------------------------------------

    def check(self) -> None:
        document = self.document
        if not isinstance(document, dict):
            raise malformed("the document is not an object (§2)")
        canon_domain(document, "the document")
        closed(
            document, "the document", ("version", "case"),
            ("sources", "admits", "unmapped", "unmappedEvidence", "provider", "facts", "evidence"),
        )
        version = document["version"]
        if not is_int(version) or version not in VERSIONS_READ:
            raise malformed("version is not the integer 2 or 3 (§2)")
        self.version = version
        if version == 3:
            for name in ("provider", "facts", "evidence"):
                if name in document:
                    raise malformed(f"version 3 is written one way: {name} is a member of version 2 alone (§2)")
        else:
            if "provider" in document and document["provider"] != "":
                raise malformed("provider is not the string \"\" (§2)")
            for name in ("facts", "evidence"):
                if name in document and document[name] is not None:
                    raise malformed(f"{name} is not null (§2)")
        sources = document.get("sources", [])
        if not isinstance(sources, list):
            raise malformed("sources is not an array (§2)")
        if "sources" in document:
            self.one_spelling("sources", sources)
        self.unmapped(document)
        self.sources_named(sources)
        self.case(document["case"])
        unread = [s["kind"] for s in sources if s["kind"] not in KINDS_READ]
        if unread:
            raise Refusal("kind-unread", f"source kind {unread[0]} is not one the catalog's form checker reads; it reads operation, selected-file and research")
        for index, source in enumerate(sources):
            self.source(source, index, sources)
        self.targets()
        self.admits(document.get("admits"))

    def one_spelling(self, where: str, value) -> None:
        """§2: version 3 is kept only as its encoding writes it, so an optional array or object
        written empty is refused where the encoding omits it."""
        if self.version == 3 and value in ([], {}):
            raise malformed(f"version 3 is written one way: {where} is written empty (§2)")

    def unmapped(self, document: dict) -> None:
        if "unmapped" in document:
            unmapped = document["unmapped"]
            if not (isinstance(unmapped, list) and all(pointer_ok(p) for p in unmapped)):
                raise malformed("unmapped is not an array of pointers (§2)")
            if len(set(unmapped)) != len(unmapped):
                raise malformed("unmapped names a pointer twice (§2)")
            self.one_spelling("unmapped", unmapped)
        if "unmappedEvidence" in document:
            listed = document["unmappedEvidence"]
            if not (isinstance(listed, list) and all(non_empty(i) for i in listed)):
                raise malformed("unmappedEvidence is not an array of non-empty strings (§2)")
            if len(set(listed)) != len(listed):
                raise malformed("unmappedEvidence names a requirement twice (§2)")
            self.one_spelling("unmappedEvidence", listed)

    def sources_named(self, sources: list) -> None:
        """§4: each source an object with a distinct name, not `case`, of a kind of the version."""
        for index, source in enumerate(sources):
            where = f"sources[{index}]"
            if not isinstance(source, dict):
                raise malformed(f"{where} is not an object (§4)")
            for name in ("name", "kind", "read"):
                if name not in source:
                    raise malformed(f"{where} has no member {name} (§4)")
            name = source["name"]
            if not non_empty(name) or name == "case":
                raise malformed(f"{where}'s name is not a non-empty string other than case (§4)")
            if name in self.kinds:
                raise malformed(f"the source name {name!r} is given twice (§4)")
            kind = source["kind"]
            if not isinstance(kind, str) or kind not in KINDS[3]:
                raise malformed(f"source {name!r} is of kind {kind!r}, which RFC 0018 does not define (§4)")
            if kind not in KINDS[self.version]:
                raise malformed(f"a version-2 document names source kind {kind}, a kind of version 3 (§4)")
            self.kinds[name] = kind

    # The case (§3) ---------------------------------------------------------------------------

    def case(self, case) -> None:
        closed(case, "case", ("facts", "evidence"), ("parameters",))
        parameters = case.get("parameters", {})
        if not isinstance(parameters, dict):
            raise malformed("case.parameters is not an object (§3)")
        if "parameters" in case:
            self.one_spelling("case.parameters", parameters)
        for name, declaration in parameters.items():
            self.parameter_name(name, "a case parameter")
            closed(declaration, f"case parameter {name!r}", ("pointer", "type"))
            if not pointer_ok(declaration["pointer"]):
                raise malformed(f"case parameter {name!r}'s pointer is not a JSON Pointer (§3)")
            if declaration["type"] not in TYPES:
                raise malformed(f"case parameter {name!r}'s type is not string, integer or timestamp (§3)")
            self.case_types[name] = declaration["type"]
        facts, evidence = self.copy({"facts": case["facts"], "evidence": case["evidence"]}, "case")
        self.fact_targets["case"] = facts
        self.evidence_targets["case"] = evidence

    def parameter_name(self, name: str, what: str) -> None:
        if name == "":
            raise malformed(f"{what}'s name is empty (§3)")
        if name == "runAt":
            raise malformed(f"{what} is named runAt, which is reserved (§3)")

    # Sources (§4) ----------------------------------------------------------------------------

    def source(self, source: dict, index: int, sources: list) -> None:
        name, kind = source["name"], source["kind"]
        scope = dict(self.case_types)
        scope.update(self.source_parameters(source, index, sources))
        scope["runAt"] = "timestamp"
        if kind == "operation":
            self.operation(source, scope)
        elif kind == "selected-file":
            self.selected_file(source, scope)
        else:
            self.research(source, scope)
        if isinstance(source["read"], dict) and "sources" in source["read"]:
            if kind != "research":
                raise malformed(f"source {name!r} of kind {kind} has a reconciliation read, which only a research source has (§6.4)")
            facts = self.reconciliation(source, scope, index, sources)
            evidence: list[str] = []
        else:
            facts, evidence = self.read(source["read"], name, scope, research=kind == "research")
        self.fact_targets[name] = facts
        self.evidence_targets[name] = evidence

    def source_parameters(self, source: dict, index: int, sources: list) -> dict[str, str]:
        name = source["name"]
        if "parameters" not in source:
            return {}
        parameters = source["parameters"]
        if not isinstance(parameters, dict):
            raise malformed(f"source {name!r}'s parameters is not an object (§4)")
        self.one_spelling(f"source {name!r}'s parameters", parameters)
        earlier = [s["name"] for s in sources[:index]]
        types = {}
        for parameter, declaration in parameters.items():
            self.parameter_name(parameter, f"a parameter of source {name!r}")
            if parameter in self.case_types:
                raise malformed(f"source {name!r}'s parameter {parameter!r} has the name of a case parameter (§3)")
            closed(declaration, f"source {name!r}'s parameter {parameter!r}", ("from", "pointer", "type"))
            origin = declaration["from"]
            if origin not in earlier:
                raise malformed(f"source {name!r}'s parameter {parameter!r} is from {origin!r}, which is not an earlier source (§3)")
            if declaration["pointer"] not in self.fact_targets.get(origin, []):
                raise malformed(f"source {name!r}'s parameter {parameter!r} reads {declaration['pointer']!r}, which is not a fact target of {origin!r} (§3)")
            if declaration["type"] not in TYPES:
                raise malformed(f"source {name!r}'s parameter {parameter!r}'s type is not string, integer or timestamp (§3)")
            types[parameter] = declaration["type"]
        return types

    def operation(self, source: dict, scope: dict) -> None:
        name = source["name"]
        form = classification(source)
        if form == "partial":
            present = [m for m in CATALOG_MEMBERS + OPERATION_BINDING if m in source]
            raise malformed(
                f"operation source {name!r} has {', '.join(present) or 'none of the binding and catalog members'}: neither its "
                "bound form (profile and profileDigest) nor its unbound form (platform, operation, shape and record) (§4.4)"
            )
        if form == "unbound":
            if self.version == 2:
                raise malformed(f"a version-2 document has the unbound source {name!r} (§4)")
            closed(source, f"source {name!r}", COMMON[:2] + ("read",) + CATALOG_MEMBERS + ("maxAge", "arguments"), ("parameters", "calculation"))
            for member in ("platform", "operation", "record"):
                if not non_empty(source[member]):
                    raise malformed(f"unbound source {name!r}'s {member} is not a non-empty string (§4.4)")
            if source["shape"] not in SHAPES:
                raise malformed(f"unbound source {name!r}'s shape is not airbyte, mcp or http (§4.4)")
        else:
            closed(source, f"source {name!r}", ("name", "kind", "read") + OPERATION_BINDING + ("maxAge", "arguments"), ("parameters", "calculation"))
            self.profile(source, f"source {name!r}")
        self.max_age(source, name)
        self.arguments(source["arguments"], name, scope)
        if "calculation" in source:
            self.calculation(source["calculation"], name, scope)

    def profile(self, holder: dict, where: str) -> None:
        if not non_empty(holder["profile"]):
            raise malformed(f"{where}'s profile is not a non-empty string (§4.1)")
        if not digest_ok(holder["profileDigest"]):
            raise malformed(f"{where}'s profileDigest is not a digest (§4.1)")

    def max_age(self, source: dict, name: str) -> None:
        age = source["maxAge"]
        if not (is_int(age) and 1 <= age <= MAX_AGE):
            raise malformed(f"source {name!r}'s maxAge is not an integer from 1 to 86400 (§4.1)")

    def arguments(self, arguments, name: str, scope: dict) -> None:
        if not isinstance(arguments, dict) or template_form(arguments):
            raise malformed(f"source {name!r}'s arguments is not an object that is not a template form (§4.1)")
        self.template(arguments, name, scope)

    def template(self, value, name: str, scope: dict) -> None:
        """§4.1: an object one of whose member names begins with `$` is a template form, exactly
        {"$param": N} or {"$text": T}; a name it gives is in the source's scope and is not runAt."""
        if isinstance(value, list):
            for item in value:
                self.template(item, name, scope)
            return
        if not isinstance(value, dict):
            return
        if not template_form(value):
            for member in value.values():
                self.template(member, name, scope)
            return
        if set(value) == {"$param"} and isinstance(value["$param"], str):
            self.named(value["$param"], name, scope)
        elif set(value) == {"$text"} and isinstance(value["$text"], str):
            for placeholder in placeholders(value["$text"], name):
                self.named(placeholder, name, scope)
                if scope[placeholder] != "integer":
                    raise malformed(f"a placeholder of source {name!r} names {placeholder!r}, which is not an integer parameter (§4.1)")
        else:
            raise malformed(f"source {name!r} has a template form that is not exactly {{\"$param\": N}} or {{\"$text\": T}} (§4.1)")

    def named(self, parameter: str, name: str, scope: dict) -> None:
        if parameter == "runAt":
            raise malformed(f"a template of source {name!r} names runAt, which no request can carry (§4.1)")
        if parameter not in scope:
            raise malformed(f"a template of source {name!r} names {parameter!r}, which is not in its scope (§4.1)")

    def string_template(self, value, name: str, scope: dict) -> None:
        """A string, a $text, or a $param naming a parameter of type string or timestamp (§4.1)."""
        if isinstance(value, str):
            return
        if isinstance(value, dict) and template_form(value):
            self.template(value, name, scope)
            if "$param" in value and scope[value["$param"]] not in ("string", "timestamp"):
                raise malformed(f"source {name!r}'s question names {value['$param']!r}, not a string or timestamp parameter (§4.1, §4.3)")
            return
        raise malformed(f"source {name!r}'s question is not a string template (§4.3)")

    def calculation(self, calculation, name: str, scope: dict) -> None:
        closed(calculation, f"source {name!r}'s calculation", ("inputs", "tables"))
        inputs, tables = calculation["inputs"], calculation["tables"]
        if not isinstance(inputs, dict):
            raise malformed(f"source {name!r}'s calculation.inputs is not an object (§7)")
        for parameter in inputs.values():
            if not isinstance(parameter, str) or parameter == "runAt" or parameter not in scope:
                raise malformed(f"source {name!r}'s calculation binds an input to {parameter!r}, not a parameter of its scope other than runAt (§7)")
        if not isinstance(tables, dict):
            raise malformed(f"source {name!r}'s calculation.tables is not an object (§7)")
        for table, age in tables.items():
            if not (is_int(age) and 1 <= age <= MAX_TABLE_AGE):
                raise malformed(f"source {name!r}'s calculation table {table!r} is not an integer from 1 to 315360000 (§7)")

    def selected_file(self, source: dict, scope: dict) -> None:
        name = source["name"]
        provider = source.get("provider")
        if provider not in PROVIDERS:
            raise malformed(f"selected-file source {name!r}'s provider is not local-file or google-drive (§4.2)")
        if provider == "local-file":
            closed(source, f"source {name!r}", ("name", "kind", "read", "provider"), ("parameters",))
            return
        closed(source, f"source {name!r}", ("name", "kind", "read", "provider") + OPERATION_BINDING + ("maxAge", "arguments"), ("parameters",))
        self.profile(source, f"source {name!r}")
        self.max_age(source, name)
        self.arguments(source["arguments"], name, scope)

    def research(self, source: dict, scope: dict) -> None:
        """§4.3 and §4.4 as round 8 amends them."""
        name = source["name"]
        form = classification(source)
        if form == "partial":
            catalog = [m for m in CATALOG_MEMBERS if m in source]
            if catalog:
                raise malformed(f"research source {name!r} has the operation catalog member {catalog[0]} (§4.4)")
            present = [m for m in RESEARCH_BINDING if m in source]
            raise malformed(
                f"research source {name!r} has {', '.join(present)} but not all of profile, profileDigest and webProfiles: "
                "partial binding members (§4.4)"
            )
        binding = RESEARCH_BINDING if form == "bound" else ()
        closed(source, f"source {name!r}", ("name", "kind", "read") + RESEARCH_MEMBERS + binding, ("parameters",))
        self.max_age(source, name)
        self.string_template(source["question"], name, scope)
        if not isinstance(source["constraints"], dict):
            raise malformed(f"research source {name!r}'s constraints is not an object (§4.3)")
        if not non_empty(source["model"]):
            raise malformed(f"research source {name!r}'s model is not a non-empty string (§4.3)")
        evidence = source["evidence"]
        if not (isinstance(evidence, list) and all(non_empty(e) for e in evidence)):
            raise malformed(f"research source {name!r}'s evidence is not an array of non-empty strings (§4.3)")
        self.fields[name] = self.requested_fields(source["fields"], name)
        capabilities = source["capabilities"]
        if not (isinstance(capabilities, list) and capabilities and all(isinstance(c, str) for c in capabilities)):
            raise malformed(f"research source {name!r}'s capabilities is not a non-empty array of names (§4.3)")
        if capabilities not in (["answer"], ["answer", "search"], ["answer", "page"], ["answer", "search", "page"]):
            raise malformed(
                f"research source {name!r}'s capabilities {capabilities} are not distinct names of answer, search and page, "
                "in that order, answer among them (§4.3)"
            )
        if form == "bound":
            self.profile(source, f"research source {name!r}")
            web = source["webProfiles"]
            requested = [c for c in capabilities if c != "answer"]
            if not isinstance(web, dict):
                raise malformed(f"research source {name!r}'s webProfiles is not an object (§4.4)")
            if sorted(web) != sorted(requested):
                raise malformed(
                    f"research source {name!r}'s webProfiles assigns {sorted(web)}, not exactly the web capabilities "
                    f"it requests, {requested} (§4.4)"
                )
            for capability, assignment in web.items():
                closed(assignment, f"research source {name!r}'s webProfiles.{capability}", OPERATION_BINDING)
                self.profile(assignment, f"research source {name!r}'s webProfiles.{capability}")

    def requested_fields(self, fields, name: str) -> list[str]:
        if not (isinstance(fields, list) and fields):
            raise malformed(f"research source {name!r}'s fields is not an array of 1 to 64 declarations (§4.3)")
        names = []
        for position, field in enumerate(fields):
            where = f"research source {name!r}'s fields[{position}]"
            closed(field, where, ("name", "type", "required", "description"))
            if not non_empty(field["name"]) or field["name"] == "case":
                raise malformed(f"{where}'s name is not a non-empty string other than case (§4.3)")
            if field["name"] in names:
                raise malformed(f"research source {name!r} declares the field {field['name']!r} twice (§4.3)")
            if field["type"] not in FIELD_TYPES:
                raise malformed(f"{where}'s type is not one of {', '.join(FIELD_TYPES)} (§4.3)")
            if not isinstance(field["required"], bool):
                raise malformed(f"{where}'s required is not a boolean (§4.3)")
            if not non_empty(field["description"]):
                raise malformed(f"{where}'s description is not a non-empty string (§4.3)")
            names.append(field["name"])
        return names

    # Reads (§6) ------------------------------------------------------------------------------

    def read(self, read, name: str, scope: dict, research: bool = False) -> tuple[list[str], list[str]]:
        closed(read, f"source {name!r}'s read", (), ("unwrap", "copy", "rule"))
        if ("copy" in read) == ("rule" in read):
            raise malformed(f"source {name!r}'s read has not exactly one of copy and rule (§6)")
        unwrap = read.get("unwrap")
        if "unwrap" in read and not (isinstance(unwrap, list) and unwrap and all(pointer_ok(p) for p in unwrap)):
            raise malformed(f"source {name!r}'s unwrap is not an array of one to four pointers (§6.1)")
        if "copy" in read:
            facts, evidence = self.copy(read["copy"], f"source {name!r}")
            pointers = [e["source"] for e in read["copy"]["facts"]] + [e["source"] for e in read["copy"]["evidence"]]
            selected = [e["source"] for e in read["copy"]["facts"]]
        else:
            facts, evidence, fields, selected = self.rule(read["rule"], name, scope)
            pointers = fields + selected
        if research:
            self.research_pointers(name, unwrap, pointers, selected)
        return facts, evidence

    def research_pointers(self, name: str, unwrap, pointers: list[str], selected: list[str]) -> None:
        """§4.3, "Reading fields": a plain research read's pointers into R form a closed list, and no
        fact is taken from under `values`. With `unwrap`, its first pointer is the one read from R."""
        declared = self.fields[name]
        if unwrap:
            pointers, selected = unwrap[:1], []
        for pointer in pointers:
            if not research_pointer_ok(pointer, declared):
                raise malformed(f"research source {name!r} reads {pointer!r}, which is not among the pointers a research read may read (§4.3)")
        for pointer in selected:
            path = tokens(pointer)
            if len(path) > 2 and path[2] == "values":
                raise malformed(f"research source {name!r} takes a fact from {pointer!r}, under values (§4.3)")

    def copy(self, copy, where: str) -> tuple[list[str], list[str]]:
        """§6.2: exactly facts, of {target, source}, and evidence, of {requirement, source}."""
        closed(copy, f"{where}'s copy", ("facts", "evidence"))
        if not isinstance(copy["facts"], list):
            raise malformed(f"{where}'s copy facts is not an array (§6.2)")
        if not isinstance(copy["evidence"], list):
            raise malformed(f"{where}'s copy evidence is not an array (§6.2)")
        facts = []
        for entry in copy["facts"]:
            closed(entry, f"a fact copy of {where}", ("target", "source"))
            if not fact_target_ok(entry["target"]):
                raise malformed(f"a fact copy of {where} has a target that is not a fact target (§6.2, §8.1)")
            if not pointer_ok(entry["source"]):
                raise malformed(f"a fact copy of {where} has a source that is not a JSON Pointer (§6.2)")
            if entry["target"] in facts:
                raise malformed(f"{where} writes the fact target {entry['target']!r} twice (§8.1)")
            facts.append(entry["target"])
        evidence = []
        for entry in copy["evidence"]:
            closed(entry, f"an evidence copy of {where}", ("requirement", "source"))
            if not non_empty(entry["requirement"]):
                raise malformed(f"an evidence copy of {where} has a requirement that is not a non-empty string (§6.2)")
            if not pointer_ok(entry["source"]):
                raise malformed(f"an evidence copy of {where} has a source that is not a JSON Pointer (§6.2)")
            if entry["requirement"] in evidence:
                raise malformed(f"{where}'s copy names the requirement {entry['requirement']!r} twice (§6.2)")
            evidence.append(entry["requirement"])
        return facts, evidence

    def rule(self, rule, name: str, scope: dict):
        """§6.3: a derivation rule, version 1. Returns its fact targets, its evidence targets, the
        fields its leaves look up, and the pointers its claim forms take facts from."""
        closed(rule, f"source {name!r}'s rule", ("ruleVersion", "parameters", "clauses"))
        if rule["ruleVersion"] != "1":
            raise malformed(f"source {name!r}'s rule's ruleVersion is not the string \"1\" (§6.3)")
        parameters = rule["parameters"]
        if not isinstance(parameters, dict):
            raise malformed(f"source {name!r}'s rule's parameters is not an object (§6.3)")
        for parameter, kind in parameters.items():
            if kind not in TYPES:
                raise malformed(f"source {name!r}'s rule declares {parameter!r} of a type other than string, integer and timestamp (§6.3)")
            if scope.get(parameter) != kind:
                raise malformed(f"source {name!r}'s rule declares {parameter!r} as {kind}, which is not a {kind} parameter of its scope (§6.3)")
        clauses = rule["clauses"]
        if not (isinstance(clauses, list) and clauses):
            raise malformed(f"source {name!r}'s rule's clauses is not an array of one to 64 clauses (§6.3)")
        facts: list[str] = []
        evidence: list[str] = []
        fields: list[str] = []
        selected: list[str] = []
        for position, clause in enumerate(clauses):
            where = f"source {name!r}'s clause {position}"
            closed(clause, where, ("when", "claim", "reason"))
            self.condition(clause["when"], where, parameters, fields)
            if not isinstance(clause["reason"], str):
                raise malformed(f"{where}'s reason is not a string (§6.3)")
            claim = closed(clause["claim"], f"{where}'s claim", ("facts", "evidence", "acquisitionStatus"))
            if not isinstance(claim["facts"], list):
                raise malformed(f"{where}'s claim facts is not an array (§6.3)")
            written = []
            for entry in claim["facts"]:
                closed(entry, f"a fact of {where}'s claim", ("pointer", "from"))
                if not fact_target_ok(entry["pointer"]):
                    raise malformed(f"a fact of {where}'s claim has a pointer that is not a fact target (§6.3, §8.1)")
                if not pointer_ok(entry["from"]):
                    raise malformed(f"a fact of {where}'s claim has a from that is not a JSON Pointer (§6.3)")
                if entry["pointer"] in written:
                    raise malformed(f"{where}'s claim writes the fact target {entry['pointer']!r} twice (§8.1)")
                written.append(entry["pointer"])
                selected.append(entry["from"])
                if entry["pointer"] not in facts:
                    facts.append(entry["pointer"])
            if not isinstance(claim["evidence"], dict):
                raise malformed(f"{where}'s claim evidence is not an object (§6.3)")
            for requirement, availability in claim["evidence"].items():
                if requirement == "":
                    raise malformed(f"{where}'s claim names an empty requirement id (§6.3)")
                if availability not in AVAILABILITIES:
                    raise malformed(f"{where}'s claim gives {requirement!r} {availability!r}, not present, absent or unknown (§6.3)")
                if requirement not in evidence:
                    evidence.append(requirement)
            if claim["acquisitionStatus"] not in ACQUISITION_STATUSES:
                raise malformed(f"{where}'s claim's acquisitionStatus is not resolved, absent or unknown (§6.3)")
        if clauses[-1]["when"] != {"op": "always"}:
            raise malformed(f"source {name!r}'s rule's last clause's when is not {{\"op\": \"always\"}} (§6.3)")
        return facts, evidence, fields, selected

    def condition(self, condition, where: str, parameters: dict, fields: list[str]) -> None:
        """A condition of §6.3's table, of exactly the members shown."""
        if not isinstance(condition, dict) or not isinstance(condition.get("op"), str):
            raise malformed(f"a condition of {where} is not an object with an op (§6.3)")
        members = CONDITIONS.get(condition["op"])
        if members is None:
            raise malformed(f"a condition of {where} has the unknown op {condition['op']!r} (§6.3)")
        closed(condition, f"a condition {condition['op']} of {where}", ("op",) + members)
        if "field" in members:
            if not pointer_ok(condition["field"]):
                raise malformed(f"a condition {condition['op']} of {where} has a field that is not a JSON Pointer (§6.3)")
            fields.append(condition["field"])
        for member in ("param", "asOf", "maxAge"):
            if member in members and not (isinstance(condition[member], str) and condition[member] in parameters):
                raise malformed(f"a condition {condition['op']} of {where} names {condition[member]!r}, not a parameter its rule declares (§6.3)")
        if condition["op"] in ("all", "any"):
            if not isinstance(condition["of"], list):
                raise malformed(f"a condition {condition['op']} of {where} does not list its conditions (§6.3)")
            for item in condition["of"]:
                self.condition(item, where, parameters, fields)
        elif condition["op"] == "not":
            self.condition(condition["of"], where, parameters, fields)

    def reconciliation(self, source: dict, scope: dict, index: int, sources: list) -> list[str]:
        """§6.4: {"sources": [S, ...], "rule": R} on a version-3 research source."""
        name = source["name"]
        read = closed(source["read"], f"research source {name!r}'s reconciliation read", ("sources", "rule"))
        listed = read["sources"]
        if not (isinstance(listed, list) and listed):
            raise malformed(f"research source {name!r}'s read names no earlier sources (§6.4)")
        earlier = {s["name"]: s["kind"] for s in sources[:index]}
        for other in listed:
            if not isinstance(other, str) or other not in earlier or earlier[other] != "research":
                raise malformed(f"research source {name!r}'s read names {other!r}, which is not an earlier research source (§6.4)")
        if len(set(listed)) != len(listed):
            raise malformed(f"research source {name!r}'s read names an earlier source twice (§6.4)")
        facts, _, fields, _ = self.rule(read["rule"], name, scope)
        entries = {f"/current/fields/{escape(f)}" for f in self.fields[name]}
        for other in listed:
            entries |= {f"/sources/{escape(other)}/fields/{escape(f)}" for f in self.fields.get(other, ())}
        for pointer in fields:
            if not any(pointer == e or pointer.startswith(e + "/") for e in entries):
                raise malformed(f"research source {name!r}'s rule reads {pointer!r}, which is not within a declared field of a source it names (§6.4)")
        clauses = read["rule"]["clauses"]
        for clause in clauses:
            if clause["claim"]["evidence"] != {}:
                raise malformed(f"research source {name!r}'s reconciliation writes evidence; its claim forms' evidence is {{}} (§6.4)")
        last = clauses[-1]["claim"]
        if last["facts"] != [] or last["acquisitionStatus"] not in ("unknown", "absent"):
            raise malformed(f"research source {name!r}'s last always clause has facts or a status other than unknown or absent (§6.4)")
        every = [c for clause in clauses for c in conditions(clause["when"])]
        for position, clause in enumerate(clauses):
            for entry in clause["claim"]["facts"]:
                field = selected_entry(entry["from"], entries)
                if field is None:
                    raise malformed(f"research source {name!r} takes a fact from {entry['from']!r}, not a declared field's value (§6.4)")
                found = guard(field, "found")
                when = clause["when"]
                if not (when == found or (when.get("op") == "all" and found in when["of"])):
                    raise malformed(f"research source {name!r}'s clause {position} selects {field} without the guard that its status is found (§6.4)")
                for status in ("not-found", "stale", "conflicting"):
                    if guard(field, status) not in every:
                        raise malformed(f"research source {name!r}'s rule has no guard for {field} as {status} (§6.4)")
                if {"op": "not", "of": {"op": "exists", "field": field}} not in every:
                    raise malformed(f"research source {name!r}'s rule has no guard for {field}'s absence (§6.4)")
        return facts

    # Targets and admission (§8) --------------------------------------------------------------

    def targets(self) -> None:
        held = [(owner, t) for owner, targets in self.fact_targets.items() for t in targets]
        for i, (owner, target) in enumerate(held):
            for other_owner, other in held[i + 1:]:
                if target == other:
                    raise malformed(f"the fact target {target!r} of {owner!r} is also one of {other_owner!r} (§8.1)")
                if other.startswith(target + "/") or target.startswith(other + "/"):
                    raise malformed(f"the fact target {target!r} of {owner!r} and {other!r} of {other_owner!r} are one a prefix of the other (§8.1)")
        seen: dict[str, str] = {}
        for owner, requirements in self.evidence_targets.items():
            for requirement in requirements:
                if requirement in seen:
                    raise malformed(f"the requirement {requirement!r} is an evidence target of {seen[requirement]!r} and {owner!r} (§8.1)")
                seen[requirement] = owner

    def admits(self, admits) -> None:
        if admits is None and "admits" not in self.document:
            return
        closed(admits, "admits", (), ("facts", "evidence"))
        written = {"facts": {t for ts in self.fact_targets.values() for t in ts}, "evidence": {r for rs in self.evidence_targets.values() for r in rs}}
        for member in ("facts", "evidence"):
            if member not in admits:
                continue
            listed = admits[member]
            if not isinstance(listed, dict):
                raise malformed(f"admits.{member} is not an object (§8.2)")
            self.one_spelling(f"admits.{member}", listed)
            for target, classes in listed.items():
                if member == "facts" and not fact_target_ok(target):
                    raise malformed(f"admits.facts names {target!r}, which is not a fact target (§8.2)")
                if not (isinstance(classes, list) and all(c in CLASSES for c in classes)):
                    raise malformed(f"admits.{member}.{target} is not an array of classes (§8.2)")
                if target not in written[member]:
                    raise malformed(f"admits.{member} names {target!r}, which no source writes (§8.2)")


CONDITIONS = {
    "always": (),
    "exists": ("field",),
    "equals": ("field", "to"),
    "equalsParam": ("field", "param"),
    "isTrue": ("field",),
    "isDecimalString": ("field",),
    "freshWithin": ("field", "asOf", "maxAge"),
    "all": ("of",),
    "any": ("of",),
    "not": ("of",),
}


def template_form(value) -> bool:
    return isinstance(value, dict) and any(isinstance(n, str) and n.startswith("$") for n in value)


def placeholders(text: str, name: str) -> list[str]:
    """§4.1: a placeholder is {{, a parameter name and the next }}; a {{ with no }} after it is refused."""
    found = []
    position = 0
    while True:
        start = text.find("{{", position)
        if start < 0:
            return found
        end = text.find("}}", start + 2)
        if end < 0:
            raise malformed(f"a $text of source {name!r} has a {{{{ with no }}}} after it (§4.1)")
        found.append(text[start + 2:end])
        position = end + 2


def research_pointer_ok(pointer: str, declared: list[str]) -> bool:
    """§4.3's closed list: /fields, /fields/<name>, /fields/<name>/value and its descendants,
    /fields/<name>/status, /fields/<name>/values/<index>/value (and its descendants, a range's endpoints
    or a list's items), and /fields/<name>/cites, each <name> a declared field."""
    path = tokens(pointer)
    if path == ["fields"]:
        return True
    if len(path) < 2 or path[0] != "fields" or path[1] not in declared:
        return False
    rest = path[2:]
    if rest in ([], ["status"], ["cites"]) or rest[:1] == ["value"]:
        return True
    return len(rest) >= 3 and rest[0] == "values" and INDEX.fullmatch(rest[1]) is not None and rest[2] == "value"


def conditions(condition):
    """Every condition, at any depth, of a `when`."""
    yield condition
    if condition.get("op") in ("all", "any"):
        for item in condition["of"]:
            yield from conditions(item)
    elif condition.get("op") == "not":
        yield from conditions(condition["of"])


def guard(entry: str, status: str) -> dict:
    return {"op": "equals", "field": f"{entry}/status", "to": status}


def selected_entry(pointer: str, entries: set[str]) -> str | None:
    """The field entry a reconciliation's `from` selects: <entry>/value or a descendant, else None."""
    for entry in entries:
        if pointer == entry + "/value" or pointer.startswith(entry + "/value/"):
            return entry
    return None

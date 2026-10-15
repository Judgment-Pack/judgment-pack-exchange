"""The catalog's own form checker (tests/dialect_form.py), on hand-written documents.

Each document here is written for these tests, from RFC 0018 §§2–8 and 12 as round 8 amends them; none
is taken from the specification's vectors or its readers. Every form the checker reads has a passing
document, and every refusal it implements has a document refused with its code and a detail naming the
rule.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialect_form  # noqa: E402
from dialect_form import check, classification, unbound_sources  # noqa: E402

D = "sha256:" + "a" * 64
E = "sha256:" + "b" * 64


def encode(document) -> bytes:
    return json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def operation_document() -> dict:
    """Version 2: a bound operation with a calculation and both template forms; a second operation taking
    a source parameter from the first, read by a rule using every condition; a local file; admission,
    unmapped pointers and requirements; and the members version 2 alone has."""
    return {
        "version": 2,
        "case": {
            "parameters": {
                "amount": {"pointer": "/amount", "type": "string"},
                "count": {"pointer": "/count", "type": "integer"},
                "since": {"pointer": "/since", "type": "timestamp"},
            },
            "facts": [{"target": "/request", "source": "/request"}],
            "evidence": [{"requirement": "intake-form", "source": "/evidence/intake-form"}],
        },
        "sources": [
            {
                "name": "fx",
                "kind": "operation",
                "profile": "fx",
                "profileDigest": D,
                "maxAge": 300,
                "arguments": {"tool": "convert", "arguments": {"amount": {"$param": "amount"}, "row": {"$text": "row {{count}}"}, "keep": [1, "two", None]}},
                "read": {"copy": {"facts": [{"target": "/converted", "source": "/facts/converted"}], "evidence": [{"requirement": "rates", "source": "/evidence/rates"}]}},
                "calculation": {"inputs": {"amount": "amount", "count": "count"}, "tables": {"ecb-rates": 86400}},
            },
            {
                "name": "vendor",
                "kind": "operation",
                "profile": "vendor",
                "profileDigest": E,
                "maxAge": 86400,
                "parameters": {"converted": {"from": "fx", "pointer": "/converted", "type": "string"}},
                "arguments": {"tool": "lookup", "arguments": {"value": {"$param": "converted"}}},
                "read": {
                    "unwrap": ["/content/0/text"],
                    "rule": {
                        "ruleVersion": "1",
                        "parameters": {"runAt": "timestamp", "count": "integer", "converted": "string"},
                        "clauses": [
                            {
                                "when": {"op": "all", "of": [
                                    {"op": "exists", "field": "/vendor"},
                                    {"op": "equals", "field": "/vendor/state", "to": {"any": ["json", 1, True, None]}},
                                    {"op": "equalsParam", "field": "/vendor/amount", "param": "converted"},
                                    {"op": "isTrue", "field": "/vendor/ok"},
                                    {"op": "isDecimalString", "field": "/vendor/id"},
                                    {"op": "freshWithin", "field": "/vendor/at", "asOf": "runAt", "maxAge": "count"},
                                ]},
                                "claim": {"facts": [{"pointer": "/vendor/id", "from": "/vendor/id"}], "evidence": {"vendor-record": "present"}, "acquisitionStatus": "resolved"},
                                "reason": "an active vendor",
                            },
                            {
                                "when": {"op": "any", "of": [{"op": "not", "of": {"op": "exists", "field": "/vendor"}}]},
                                "claim": {"facts": [], "evidence": {"vendor-record": "absent"}, "acquisitionStatus": "absent"},
                                "reason": "",
                            },
                            {
                                "when": {"op": "always"},
                                "claim": {"facts": [], "evidence": {"vendor-record": "unknown"}, "acquisitionStatus": "unknown"},
                                "reason": "otherwise",
                            },
                        ],
                    },
                },
            },
            {
                "name": "upload",
                "kind": "selected-file",
                "provider": "local-file",
                "read": {"copy": {"facts": [{"target": "/upload", "source": "/document"}], "evidence": []}},
            },
        ],
        "admits": {"facts": {"/upload": ["asserted", "record"]}, "evidence": {"rates": ["record"]}},
        "unmapped": ["/elsewhere", ""],
        "unmappedEvidence": ["sensitive-data-approvals"],
        "provider": "",
        "facts": None,
        "evidence": None,
    }


def unbound_document() -> dict:
    """Version 3: one unbound operation (§4.4) and one bound; a Drive file; written the one way."""
    return {
        "version": 3,
        "case": {"parameters": {"item": {"pointer": "/item", "type": "string"}}, "facts": [], "evidence": []},
        "sources": [
            {
                "name": "items",
                "kind": "operation",
                "platform": "azure-devops",
                "operation": "wit_get_work_item",
                "shape": "http",
                "record": "azure-devops",
                "maxAge": 60,
                "arguments": {"method": "GET", "path": {"$text": "items"}, "query": {"id": {"$param": "item"}}},
                "read": {"copy": {"facts": [{"target": "/item/state", "source": "/fields/state"}], "evidence": []}},
            },
            {
                "name": "rates",
                "kind": "operation",
                "profile": "rates",
                "profileDigest": D,
                "maxAge": 60,
                "arguments": {"tool": "rates", "arguments": {}},
                "read": {"copy": {"facts": [{"target": "/rates", "source": "/rates"}], "evidence": []}},
            },
            {
                "name": "spec",
                "kind": "selected-file",
                "provider": "google-drive",
                "profile": "drive",
                "profileDigest": E,
                "maxAge": 600,
                "arguments": {"fileId": {"$param": "item"}},
                "read": {"copy": {"facts": [{"target": "/spec", "source": ""}], "evidence": []}},
            },
        ],
    }


FIELDS = [
    {"name": "company-id", "type": "text", "required": True, "description": "The company's identifier."},
    {"name": "employee-count", "type": "integer", "required": False, "description": "Employees, as cited."},
    {"name": "revenue", "type": "decimal", "required": False, "description": "Revenue."},
    {"name": "active", "type": "boolean", "required": False, "description": "Whether it trades."},
    {"name": "roles", "type": "text-list", "required": False, "description": "Roles it hires for."},
    {"name": "band", "type": "range", "required": False, "description": "Its band of employees."},
]
COUNT = [{"name": "employee-count", "type": "integer", "required": False, "description": "Employees, as cited."}]


def research(name: str, read: dict, fields=None, capabilities=None, bound: bool = False) -> dict:
    capabilities = ["answer"] if capabilities is None else capabilities
    source = {
        "name": name,
        "kind": "research",
        "maxAge": 600,
        "question": {"$param": "company"},
        "constraints": {"region": "EU", "synthetic": True},
        "model": "model-a",
        "evidence": ["the page that states the headcount"],
        "fields": copy.deepcopy(FIELDS if fields is None else fields),
        "capabilities": capabilities,
        "read": read,
    }
    if bound:
        source.update(profile="ai", profileDigest=D, webProfiles={c: {"profile": "web", "profileDigest": E} for c in capabilities if c != "answer"})
    return source


def guard(entry: str, status: str) -> dict:
    return {"op": "equals", "field": f"{entry}/status", "to": status}


def absent(entry: str) -> dict:
    return {"op": "not", "of": {"op": "exists", "field": entry}}


def unavailable(entry: str) -> dict:
    return {"op": "any", "of": [absent(entry), guard(entry, "not-found"), guard(entry, "stale")]}


def clause(when, reason, target=None, origin=None, status="unknown") -> dict:
    facts = [{"pointer": target, "from": origin}] if target else []
    return {"when": when, "claim": {"facts": facts, "evidence": {}, "acquisitionStatus": status}, "reason": reason}


PRIMARY = "/sources/primary/fields/employee-count"
SECONDARY = "/sources/secondary/fields/employee-count"
CURRENT = "/current/fields/employee-count"


def reconciliation_rule() -> dict:
    return {
        "ruleVersion": "1",
        "parameters": {},
        "clauses": [
            clause(guard(PRIMARY, "found"), "the primary found it", "/count", PRIMARY + "/value", "resolved"),
            clause({"op": "all", "of": [unavailable(PRIMARY), guard(SECONDARY, "found")]}, "the secondary found it", "/count", SECONDARY + "/value", "resolved"),
            clause({"op": "any", "of": [guard(e, "conflicting") for e in (PRIMARY, SECONDARY, CURRENT)]}, "a conflict is not chosen"),
            clause({"op": "all", "of": [unavailable(SECONDARY), guard(CURRENT, "found")]}, "this source found it", "/count", CURRENT + "/value", "resolved"),
            clause(unavailable(CURRENT), "no candidate is left"),
            clause({"op": "always"}, "otherwise"),
        ],
    }


def research_document() -> dict:
    """Version 3, round 8: an unbound research source copying its fields; one read by a plain rule over
    the closed pointer list; a bound one with a web assignment; and a reconciliation of two of them."""
    plain_rule = {
        "ruleVersion": "1",
        "parameters": {},
        "clauses": [
            clause({"op": "all", "of": [guard("/fields/band", "found"), {"op": "exists", "field": "/fields/band/value/min"}]}, "found", "/band", "/fields/band/value", "resolved"),
            clause({"op": "exists", "field": "/fields/roles/values/1/value"}, "observed"),
            clause({"op": "exists", "field": "/fields/roles/cites"}, "cited"),
            clause({"op": "always"}, "otherwise"),
        ],
    }
    return {
        "version": 3,
        "case": {"parameters": {"company": {"pointer": "/company", "type": "string"}}, "facts": [{"target": "/case/company", "source": "/company"}], "evidence": []},
        "sources": [
            research("company", {"copy": {"facts": [{"target": "/company/fields", "source": "/fields"}], "evidence": []}}),
            research("banded", {"rule": plain_rule}, capabilities=["answer", "search", "page"]),
            research("primary", {"copy": {"facts": [{"target": "/observed/primary", "source": "/fields/employee-count/status"}], "evidence": []}}, COUNT),
            research("secondary", {"copy": {"facts": [{"target": "/observed/secondary", "source": "/fields/employee-count/value/0"}], "evidence": []}}, COUNT, ["answer", "page"], bound=True),
            research("combined", {"sources": ["primary", "secondary"], "rule": reconciliation_rule()}, COUNT),
        ],
        "admits": {"facts": {"/company/fields": ["generated"], "/band": ["generated"], "/count": ["generated"]}},
    }


def unread_kind_source(kind: str) -> dict:
    """A well-formed source of a kind version 3 proposes and the checker does not read (§4.3)."""
    common = {"name": f"by-{kind}", "kind": kind, "profile": kind, "profileDigest": D, "maxAge": 60,
              "read": {"copy": {"facts": [{"target": f"/{kind}", "source": "/value"}], "evidence": []}}}
    return {
        "http": {**common, "method": "POST", "path": {"$text": "items/{{count}}"}, "query": {"q": {"$param": "item"}}, "body": {"id": {"$param": "count"}}, "headers": ["Accept"]},
        "sql": {**common, "statement": "select state from items where id = :id", "bindings": [{"name": "id", "type": "string", "value": {"$param": "item"}}]},
        "web": {**common, "url": {"$param": "item"}},
    }[kind]


def with_unread_kinds() -> dict:
    """Version 3 with an integer case parameter, and one source of each kind the checker does not read."""
    document = unbound_document()
    document["case"]["parameters"]["count"] = {"pointer": "/count", "type": "integer"}
    document["sources"] += [unread_kind_source(k) for k in ("http", "sql", "web")]
    return document


def source(document: dict, name: str) -> dict:
    return next(s for s in document["sources"] if s["name"] == name)


def refused(test: unittest.TestCase, document, code: str, fragment: str) -> None:
    data = document if isinstance(document, bytes) else encode(document)
    answer = check(data)
    test.assertIsNotNone(answer, f"admitted; expected {code}: {fragment}")
    test.assertEqual(code, answer[0], answer)
    test.assertIn(fragment, answer[1], answer)


def altered(base, alter):
    document = base()
    alter(document)
    return document


class PassingDocuments(unittest.TestCase):
    def test_each_form_the_checker_reads(self):
        for label, document in {
            "version 2, bound operations, a rule and a local file": operation_document(),
            "version 3, an unbound operation, a bound one and a Drive file": unbound_document(),
            "version 3, research of round 8": research_document(),
            "a case-only document of version 2": {"version": 2, "case": {"facts": [], "evidence": []}},
            "a case-only document of version 3": {"version": 3, "case": {"facts": [], "evidence": []}},
            "version 2 with its empty members written": {"version": 2, "case": {"parameters": {}, "facts": [], "evidence": []}, "sources": [], "unmapped": [], "unmappedEvidence": []},
            "admits written empty in version 3": {**unbound_document(), "admits": {}},
            "a copy's arrays written empty": altered(unbound_document, lambda d: d["sources"][1]["read"].update(copy={"facts": [], "evidence": []})),
            "a bound research source asking for answer alone": altered(research_document, lambda d: d["sources"].__setitem__(0, research("company", d["sources"][0]["read"], bound=True))),
            "a minus zero": altered(operation_document, lambda d: source(d, "fx")["arguments"].update(zero=0)),
            "a research read with an unwrap on the closed list": altered(research_document, lambda d: d["sources"][0]["read"].update(unwrap=["/fields/company-id/value", "/fields/roles/value/0"])),
        }.items():
            with self.subTest(label):
                self.assertIsNone(check(encode(document)))

    def test_minus_zero_is_an_integer(self):
        data = encode(operation_document()).replace(b'"maxAge":300', b'"maxAge":300,"x":-0', 1)
        self.assertIn("has the member 'x'", check(data)[1])  # read as an integer: only its member is refused
        data = encode(operation_document()).replace(b'"keep":[1,', b'"keep":[-0,', 1)
        self.assertIsNone(check(data))

    def test_the_classification(self):
        operation = {"kind": "operation"}
        catalog = {"platform": "p", "operation": "o", "shape": "mcp", "record": "r"}
        binding = {"profile": "x", "profileDigest": D}
        self.assertEqual("unbound", classification({**operation, **catalog}))
        self.assertEqual("bound", classification({**operation, **binding}))
        self.assertEqual("partial", classification({**operation, **catalog, "profile": "x"}))
        self.assertEqual("partial", classification({**operation, "platform": "p", "operation": "o", "shape": "mcp"}))
        self.assertEqual("partial", classification({**operation, "profile": "x"}))
        self.assertEqual("partial", classification(operation))
        self.assertEqual("partial", classification({**operation, **binding, "record": "r"}))
        research_ = {"kind": "research"}
        self.assertEqual("unbound", classification(research_))
        self.assertEqual("bound", classification({**research_, **binding, "webProfiles": {}}))
        self.assertEqual("partial", classification({**research_, **binding}))
        self.assertEqual("partial", classification({**research_, "webProfiles": {}}))
        self.assertEqual("partial", classification({**research_, "platform": "p"}))
        self.assertIsNone(classification({"kind": "selected-file", "provider": "local-file"}))
        self.assertEqual({"items"}, set(unbound_sources(unbound_document())))
        self.assertEqual({"company", "banded", "primary", "combined"}, set(unbound_sources(research_document())))
        self.assertEqual({}, unbound_sources(operation_document()))


class ByteBounds(unittest.TestCase):
    """§12's bounds on bytes, measured before the document is read."""

    def padded(self, size: int) -> bytes:
        document = {"version": 3, "case": {"facts": [], "evidence": []}, "unmappedEvidence": [""]}
        body = encode(document)
        return body.replace(b'[""]', b'["' + b"x" * (size - len(body)) + b'"]')

    def test_the_document_is_at_most_131072_bytes(self):
        self.assertEqual(131072, len(self.padded(131072)))
        self.assertIsNone(check(self.padded(131072)))
        refused(self, self.padded(131073), "input-over-bound", "131073 bytes, over 131,072")

    def test_nesting_is_at_most_64_levels(self):
        def nested(depth: int) -> bytes:
            # root (1), sources (2), the source (3), arguments (4): the pad adds depth - 4 levels.
            document = operation_document()
            value = []
            for _ in range(depth - 5):
                value = [value]
            source(document, "fx")["arguments"]["pad"] = value
            return encode(document)

        self.assertIsNone(check(nested(64)))
        refused(self, nested(65), "input-over-bound", "deeper than 64 levels")
        # brackets inside a string are not nesting
        document = operation_document()
        document["unmappedEvidence"] = ["[" * 100]
        self.assertIsNone(check(encode(document)))

    def test_a_number_literal_is_at_most_128_characters_with_an_exponent_of_at_most_308(self):
        def with_number(literal: bytes) -> bytes:
            return encode(operation_document()).replace(b'"keep":[1,', b'"keep":[' + literal + b",", 1)

        self.assertIsNone(check(with_number(b"1" * 16)))
        refused(self, with_number(b"1" * 129), "input-over-bound", "129 characters, over 128")
        # A literal of 128 characters is measured, then read: as a number beyond 2^53-1 it is no integer.
        refused(self, with_number(b"1" * 128), "input-malformed", "not an integer")
        refused(self, with_number(b"1e309"), "input-over-bound", "exponent")
        refused(self, with_number(b"1E+309"), "input-over-bound", "exponent")
        refused(self, with_number(b"1e308"), "input-malformed", "not an integer")
        refused(self, with_number(b"1e-0309"), "input-over-bound", "exponent")


class StrictRead(unittest.TestCase):
    """§1: one JSON value, no member twice, well-formed strings; the canon domain (§2)."""

    def test_each_refusal(self):
        valid = encode(operation_document())
        cases = {
            "not UTF-8": (b"\xff" + valid, "not UTF-8"),
            "a byte-order mark": ("﻿".encode("utf-8") + valid, "not one JSON value"),
            "two values": (valid + b" {}", "not one JSON value"),
            "a member twice": (valid.replace(b'"version":2', b'"version":2,"version":2', 1), "given twice"),
            "a member twice in a nested object": (valid.replace(b'"maxAge":300', b'"maxAge":300,"maxAge":300', 1), "given twice"),
            "an escaped lone surrogate": (valid.replace(b'"sensitive-data-approvals"', b'"\\ud800"', 1), "lone surrogate"),
            "NaN": (valid.replace(b'"keep":[1,', b'"keep":[NaN,', 1), "not a JSON value"),
            "a fraction": (valid.replace(b'"keep":[1,', b'"keep":[1.0,', 1), "the number 1.0"),
            "an exponent": (valid.replace(b'"keep":[1,', b'"keep":[1e2,', 1), "the number 1e2"),
            "2^53": (valid.replace(b'"keep":[1,', b'"keep":[9007199254740992,', 1), "9007199254740992"),
            "not an object": (b"[]", "not an object"),
        }
        for label, (data, fragment) in cases.items():
            with self.subTest(label):
                refused(self, data, "input-malformed", fragment)
        self.assertIsNone(check(b" \t\r\n" + valid + b"\n"))
        self.assertIsNone(check(valid.replace(b'"keep":[1,', b'"keep":[9007199254740991,', 1)))


class CountBounds(unittest.TestCase):
    """§12's counts: over a maximum is input-over-bound; at it, the document is read."""

    def test_each_maximum(self):
        def sources(n):
            def alter(d):
                template = d["sources"][2]
                d["sources"] = [{**copy.deepcopy(template), "name": f"f{i}", "read": {"copy": {"facts": [{"target": f"/f{i}", "source": ""}], "evidence": []}}} for i in range(n)]
                d.pop("admits")
            return alter

        def scope(case: int, own: int) -> dict:
            """A case of `case` parameters, and a local file whose `own` parameters come from an earlier one."""
            return {
                "version": 2,
                "case": {"parameters": {f"p{i}": {"pointer": "/p", "type": "string"} for i in range(case)}, "facts": [], "evidence": []},
                "sources": [
                    {"name": "first", "kind": "selected-file", "provider": "local-file", "read": {"copy": {"facts": [{"target": "/x", "source": ""}], "evidence": []}}},
                    {"name": "second", "kind": "selected-file", "provider": "local-file", "parameters": {f"q{i}": {"from": "first", "pointer": "/x", "type": "string"} for i in range(own)}, "read": {"copy": {"facts": [], "evidence": []}}},
                ],
            }

        def clauses(n):
            def alter(d):
                rule = source(d, "vendor")["read"]["rule"]
                rule["clauses"] = [copy.deepcopy(rule["clauses"][1]) for _ in range(n - 1)] + [rule["clauses"][-1]]
            return alter

        def conditions(n):
            return lambda d: source(d, "vendor")["read"]["rule"]["clauses"][1]["when"]["of"].extend([{"op": "always"}] * (n - 1))

        def unwrap(n):
            return lambda d: source(d, "vendor")["read"].update(unwrap=["/x"] * n)

        def fact_targets(n):
            return lambda d: source(d, "upload")["read"]["copy"]["facts"].extend({"target": f"/u/{i}", "source": ""} for i in range(n))

        def evidence_targets(n):
            return lambda d: source(d, "upload")["read"]["copy"].update(evidence=[{"requirement": f"r{i}", "source": ""} for i in range(n)])

        cases = {
            # name: (base, alter at the maximum, alter over it, fragment)
            "16 sources": (operation_document, sources(16), sources(17), "17 sources, over 16"),
            "64 parameters in the case's scope, runAt included": (lambda: scope(63, 0), lambda d: None, lambda d: d.update(scope(64, 0)), "the case's scope holds 65 parameters"),
            "64 parameters in a source's scope, runAt included": (lambda: scope(1, 62), lambda d: None, lambda d: d.update(scope(1, 63)), "the scope of source 'second' holds 65 parameters"),
            "64 clauses": (operation_document, clauses(64), clauses(65), "65 clauses, over 64"),
            "64 conditions in one any": (operation_document, conditions(64), conditions(65), "65 conditions, over 64"),
            "4 unwrap pointers": (operation_document, unwrap(4), unwrap(5), "5 unwrap pointers, over 4"),
            "256 fact targets": (operation_document, fact_targets(256 - 4), fact_targets(256 - 3), "257 fact targets, over 256"),
            "128 evidence targets": (operation_document, evidence_targets(128 - 3), evidence_targets(128 - 2), "129 evidence targets, over 128"),
            "64 fields": (research_document, lambda d: d["sources"][0].update(fields=[{**FIELDS[0], "name": f"f{i}"} for i in range(64)]), lambda d: d["sources"][0].update(fields=[{**FIELDS[0], "name": f"f{i}"} for i in range(65)]), "65 fields, over 64"),
            "a field name of 64 bytes": (research_document, lambda d: d["sources"][0]["fields"][0].update(name="é" * 32), lambda d: d["sources"][0]["fields"][0].update(name="é" * 32 + "x"), "over 64 UTF-8 bytes"),
            "a description of 2048 bytes": (research_document, lambda d: d["sources"][0]["fields"][0].update(description="é" * 1024), lambda d: d["sources"][0]["fields"][0].update(description="é" * 1024 + "x"), "over 2048 UTF-8 bytes"),
            "a model of 256 bytes": (research_document, lambda d: d["sources"][0].update(model="m" * 256), lambda d: d["sources"][0].update(model="m" * 257), "over 256 UTF-8 bytes"),
            "an evidence instruction of 4096 bytes": (research_document, lambda d: d["sources"][0].update(evidence=["e" * 4096]), lambda d: d["sources"][0].update(evidence=["e" * 4097]), "over 4096 UTF-8 bytes"),
            "three capabilities": (research_document, lambda d: None, lambda d: d["sources"][1].update(capabilities=["answer", "search", "page", "page"]), "4 capabilities, over 3"),
            "two web assignments": (research_document, lambda d: None, lambda d: d["sources"][3].update(webProfiles={c: {"profile": "w", "profileDigest": E} for c in ("search", "page", "answer")}), "3 web assignments, over 2"),
            "15 earlier sources in a reconciliation": (research_document, lambda d: None, lambda d: source(d, "combined")["read"].update(sources=["primary"] * 16), "16 earlier sources, over 15"),
        }
        for label, (base, at, over, fragment) in cases.items():
            with self.subTest(label):
                self.assertIsNone(check(encode(altered(base, at))), label)
                refused(self, altered(base, over), "input-over-bound", fragment)


class VersionAndKindsNotRead(unittest.TestCase):
    """A version or a source kind the checker does not read is refused by name (RFC 0019 §3)."""

    def test_a_version_other_than_2_and_3(self):
        for version in (1, 4, 0, -1):
            with self.subTest(version):
                refused(self, {**operation_document(), "version": version}, "version-unread", f"dialect version {version} is not one")
        for version in ("3", 3.0, True, None):
            with self.subTest(repr(version)):
                refused(self, {**operation_document(), "version": version}, "input-malformed", "")

    def test_http_sql_and_web(self):
        # §11, phases 5 and 6: each is held to its form first, and refused as unread only once every form holds.
        refused(self, with_unread_kinds(), "kind-unread", "source kind http is not one the catalog's form checker reads")
        for kind in ("http", "sql", "web"):
            with self.subTest(kind):
                document = unbound_document()
                document["case"]["parameters"]["count"] = {"pointer": "/count", "type": "integer"}
                document["sources"].append(unread_kind_source(kind))
                refused(self, document, "kind-unread", f"source kind {kind} is not one the catalog's form checker reads")
                incomplete = copy.deepcopy(document)
                incomplete["sources"][-1].pop("maxAge")
                refused(self, incomplete, "input-malformed", "has no member maxAge")
                document["version"] = 2
                refused(self, document, "input-malformed", f"a version-2 document names source kind {kind}")


def refusal_cases() -> dict:
    """Every form refusal the checker implements, by the rule it breaks: (base, alteration, fragment)."""
    op = lambda d: source(d, "fx")  # noqa: E731
    vendor = lambda d: source(d, "vendor")  # noqa: E731
    rule = lambda d: vendor(d)["read"]["rule"]  # noqa: E731
    first = lambda d: rule(d)["clauses"][0]  # noqa: E731
    items = lambda d: source(d, "items")  # noqa: E731
    company = lambda d: source(d, "company")  # noqa: E731
    banded = lambda d: source(d, "banded")  # noqa: E731
    secondary = lambda d: source(d, "secondary")  # noqa: E731
    combined = lambda d: source(d, "combined")  # noqa: E731
    clauses = lambda d: combined(d)["read"]["rule"]["clauses"]  # noqa: E731
    O, U, R = operation_document, unbound_document, research_document  # noqa: N806
    return {
        # §2, the document
        "a member §2 does not list": (O, lambda d: d.update(extra=1), "has the member 'extra'"),
        "no case": (O, lambda d: d.pop("case"), "has no member case"),
        "no version": (O, lambda d: d.pop("version"), "has no member version"),
        "provider other than empty": (O, lambda d: d.update(provider="runner"), "provider is not the string"),
        "facts not null in version 2": (O, lambda d: d.update(facts=[]), "facts is not null"),
        "provider in version 3": (U, lambda d: d.update(provider=""), "provider is a member of version 2 alone"),
        "facts in version 3": (U, lambda d: d.update(facts=None), "facts is a member of version 2 alone"),
        "evidence in version 3": (U, lambda d: d.update(evidence=None), "evidence is a member of version 2 alone"),
        "sources not an array": (O, lambda d: d.update(sources={}), "sources is not an array"),
        "sources written empty in version 3": (U, lambda d: d.update(sources=[]), "sources is written empty"),
        "unmapped not pointers": (O, lambda d: d.update(unmapped=["elsewhere"]), "unmapped is not an array of pointers"),
        "unmapped with a bad escape": (O, lambda d: d.update(unmapped=["/a~2"]), "unmapped is not an array of pointers"),
        "unmapped twice": (O, lambda d: d.update(unmapped=["/a", "/a"]), "unmapped names a pointer twice"),
        "unmapped written empty in version 3": (U, lambda d: d.update(unmapped=[]), "unmapped is written empty"),
        "unmappedEvidence empty string": (O, lambda d: d.update(unmappedEvidence=[""]), "unmappedEvidence is not an array of non-empty strings"),
        "unmappedEvidence twice": (O, lambda d: d.update(unmappedEvidence=["a", "a"]), "unmappedEvidence names a requirement twice"),
        "unmappedEvidence written empty in version 3": (U, lambda d: d.update(unmappedEvidence=[]), "unmappedEvidence is written empty"),
        # §3, the case and parameters
        "case not closed": (O, lambda d: d["case"].update(extra=1), "case has the member 'extra'"),
        "case without evidence": (O, lambda d: d["case"].pop("evidence"), "case has no member evidence"),
        "case parameters written empty in version 3": (U, lambda d: d["case"].update(parameters={}), "case.parameters is written empty"),
        "a case parameter named runAt": (O, lambda d: d["case"]["parameters"].update(runAt={"pointer": "/t", "type": "timestamp"}), "named runAt, which is reserved"),
        "a case parameter with an empty name": (O, lambda d: d["case"]["parameters"].update({"": {"pointer": "/t", "type": "string"}}), "name is empty"),
        "a case parameter of another type": (O, lambda d: d["case"]["parameters"]["amount"].update(type="number"), "type is not string, integer or timestamp"),
        "a case parameter's pointer": (O, lambda d: d["case"]["parameters"]["amount"].update(pointer="amount"), "pointer is not a JSON Pointer"),
        "a case parameter not closed": (O, lambda d: d["case"]["parameters"]["amount"].update(default="0"), "has the member 'default'"),
        "a source parameter named as a case parameter": (O, lambda d: vendor(d)["parameters"].update(amount={"from": "fx", "pointer": "/converted", "type": "string"}), "has the name of a case parameter"),
        "a source parameter from a later source": (O, lambda d: vendor(d)["parameters"]["converted"].update({"from": "upload"}), "is not an earlier source"),
        "a source parameter from itself": (O, lambda d: vendor(d)["parameters"]["converted"].update({"from": "vendor"}), "is not an earlier source"),
        "a source parameter at no fact target": (O, lambda d: vendor(d)["parameters"]["converted"].update(pointer="/elsewhere"), "is not a fact target of 'fx'"),
        "a source parameter of another type": (O, lambda d: vendor(d)["parameters"]["converted"].update(type="boolean"), "type is not string, integer or timestamp"),
        "a source parameter not closed": (O, lambda d: vendor(d)["parameters"]["converted"].update(extra=1), "has the member 'extra'"),
        "a source's parameters written empty in version 3": (U, lambda d: items(d).update(parameters={}), "parameters is written empty"),
        # §4, sources
        "a source that is not an object": (O, lambda d: d["sources"].append("fx"), "is not an object"),
        "a source without a read": (O, lambda d: op(d).pop("read"), "has no member read"),
        "a source named case": (O, lambda d: op(d).update(name="case"), "name is not a non-empty string other than case"),
        "a source name twice": (O, lambda d: source(d, "upload").update(name="fx"), "the source name 'fx' is given twice"),
        "an undefined kind": (O, lambda d: op(d).update(kind="ftp"), "which RFC 0018 does not define"),
        "research in version 2": (O, lambda d: d["sources"].append({"name": "r", "kind": "research", "read": {}}), "a version-2 document names source kind research"),
        # §4.1, operation
        "an operation not closed": (O, lambda d: op(d).update(timeout=5), "has the member 'timeout'"),
        "an operation without maxAge": (O, lambda d: op(d).pop("maxAge"), "has no member maxAge"),
        "an empty profile": (O, lambda d: op(d).update(profile=""), "profile is not a non-empty string"),
        "a profileDigest not a digest": (O, lambda d: op(d).update(profileDigest="sha256:A"), "profileDigest is not a digest"),
        "maxAge 0": (O, lambda d: op(d).update(maxAge=0), "maxAge is not an integer from 1 to 86400"),
        "maxAge 86401": (O, lambda d: op(d).update(maxAge=86401), "maxAge is not an integer from 1 to 86400"),
        "maxAge a string": (O, lambda d: op(d).update(maxAge="300"), "maxAge is not an integer from 1 to 86400"),
        "arguments an array": (O, lambda d: op(d).update(arguments=[]), "arguments is not an object"),
        "arguments a template form": (O, lambda d: op(d).update(arguments={"$param": "amount"}), "arguments is not an object"),
        "a template form with a member more": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$param": "amount", "y": 1}), "a template form that is not exactly"),
        "an unknown template form": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$value": 1}), "a template form that is not exactly"),
        "a $param that is not a string": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$param": 1}), "a template form that is not exactly"),
        "a $param outside the scope": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$param": "converted"}), "names 'converted', which is not in its scope"),
        "a $param naming runAt": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$param": "runAt"}), "names runAt, which no request can carry"),
        "a placeholder of a string parameter": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$text": "{{amount}}"}), "which is not an integer parameter"),
        "a placeholder of runAt": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$text": "{{runAt}}"}), "names runAt"),
        "a {{ with no }}": (O, lambda d: op(d)["arguments"]["arguments"].update(x={"$text": "row {{count"}), "with no }} after it"),
        "a template in a list": (O, lambda d: op(d)["arguments"]["arguments"]["keep"].append({"$param": "nothing"}), "names 'nothing'"),
        # §4.4, the unbound operation
        "an unbound source in version 2": (U, lambda d: d.update(version=2), "a version-2 document has the unbound source 'items'"),
        "an unbound operation without record": (U, lambda d: items(d).pop("record"), "neither its bound form"),
        "an unbound operation with a profile": (U, lambda d: items(d).update(profile="p"), "neither its bound form"),
        "a bound operation with a catalog member": (U, lambda d: source(d, "rates").update(shape="mcp"), "neither its bound form"),
        "a bound operation without profileDigest": (U, lambda d: source(d, "rates").pop("profileDigest"), "neither its bound form"),
        "an empty platform": (U, lambda d: items(d).update(platform=""), "platform is not a non-empty string"),
        "a record that is not a string": (U, lambda d: items(d).update(record=7), "record is not a non-empty string"),
        "a shape of command": (U, lambda d: items(d).update(shape="command"), "shape is not airbyte, mcp or http"),
        "an unbound operation not closed": (U, lambda d: items(d).update(webProfiles={}), "has the member 'webProfiles'"),
        # §7, calculations
        "a calculation not closed": (O, lambda d: op(d)["calculation"].update(extra=1), "has the member 'extra'"),
        "a calculation input bound to runAt": (O, lambda d: op(d)["calculation"]["inputs"].update(at="runAt"), "not a parameter of its scope other than runAt"),
        "a calculation input bound outside the scope": (O, lambda d: op(d)["calculation"]["inputs"].update(at="nothing"), "not a parameter of its scope"),
        "a calculation table of 0 seconds": (O, lambda d: op(d)["calculation"]["tables"].update(t=0), "is not an integer from 1 to 315360000"),
        "a calculation table over ten years": (O, lambda d: op(d)["calculation"]["tables"].update(t=315360001), "is not an integer from 1 to 315360000"),
        "a calculation's inputs an array": (O, lambda d: op(d)["calculation"].update(inputs=[]), "calculation.inputs is not an object"),
        # §4.3, the kinds version 3 proposes, held to their forms before they are refused as unread
        "an http source without its path": (with_unread_kinds, lambda d: source(d, "by-http").pop("path"), "has no member path"),
        "an http source with a member more": (with_unread_kinds, lambda d: source(d, "by-http").update(timeout=1), "has the member 'timeout'"),
        "an http method other than GET and POST": (with_unread_kinds, lambda d: source(d, "by-http").update(method="PUT"), "method is not GET or POST"),
        "an http path that is not a string template": (with_unread_kinds, lambda d: source(d, "by-http").update(path=["items"]), "path is not a string template"),
        "an http path naming an integer parameter": (with_unread_kinds, lambda d: source(d, "by-http").update(path={"$param": "count"}), "path names 'count', not a string or timestamp parameter"),
        "an http query that is a template form": (with_unread_kinds, lambda d: source(d, "by-http").update(query={"$param": "item"}), "query is not an object of string templates"),
        "an http query member that is no string template": (with_unread_kinds, lambda d: source(d, "by-http")["query"].update(n=1), "query is not a string template"),
        "an http body beside GET": (with_unread_kinds, lambda d: source(d, "by-http").update(method="GET"), "has a body beside GET"),
        "an http body naming no parameter in scope": (with_unread_kinds, lambda d: source(d, "by-http").update(body={"$param": "elsewhere"}), "names 'elsewhere', which is not in its scope"),
        "http headers with an empty name": (with_unread_kinds, lambda d: source(d, "by-http").update(headers=[""]), "headers is not an array of header names"),
        "an http source's read malformed": (with_unread_kinds, lambda d: source(d, "by-http")["read"]["copy"]["facts"][0].update(target=""), "is not a fact target"),
        "a sql statement that is a template": (with_unread_kinds, lambda d: source(d, "by-sql").update(statement={"$param": "item"}), "statement is not a string, and is never a template"),
        "sql bindings that are not an array": (with_unread_kinds, lambda d: source(d, "by-sql").update(bindings={}), "bindings is not an array"),
        "a sql binding with a member more": (with_unread_kinds, lambda d: source(d, "by-sql")["bindings"][0].update(position=1), "has the member 'position'"),
        "a sql binding with an empty name": (with_unread_kinds, lambda d: source(d, "by-sql")["bindings"][0].update(name=""), "name or type that is not a non-empty string"),
        "a sql binding's value not a $param form": (with_unread_kinds, lambda d: source(d, "by-sql")["bindings"][0].update(value="1"), "value that is not a $param form"),
        "a sql binding naming runAt": (with_unread_kinds, lambda d: source(d, "by-sql")["bindings"][0].update(value={"$param": "runAt"}), "names runAt"),
        "a web url that is no string or $param": (with_unread_kinds, lambda d: source(d, "by-web").update(url={"$text": "x"}), "url is not a string or a $param form"),
        "a web url naming an integer parameter": (with_unread_kinds, lambda d: source(d, "by-web").update(url={"$param": "count"}), "url names 'count', not a string parameter"),
        "a web source without its profile": (with_unread_kinds, lambda d: source(d, "by-web").pop("profile"), "has no member profile"),
        "a web source's target overlapping another's": (with_unread_kinds, lambda d: source(d, "by-web")["read"]["copy"]["facts"][0].update(target="/item/state/x"), "one a prefix of the other"),
        "admits naming a target no source writes beside a web source": (with_unread_kinds, lambda d: d.update(admits={"facts": {"/nothing": ["record"]}}), "which no source writes"),
        # §4.2, selected-file
        "a selected file of another provider": (O, lambda d: source(d, "upload").update(provider="dropbox"), "provider is not local-file or google-drive"),
        "a local file with a profile": (O, lambda d: source(d, "upload").update(profile="p"), "has the member 'profile'"),
        "a Drive file without maxAge": (U, lambda d: source(d, "spec").pop("maxAge"), "has no member maxAge"),
        "a Drive file's arguments a template form": (U, lambda d: source(d, "spec").update(arguments={"$param": "item"}), "arguments is not an object"),
        # §6, reads
        "a read with copy and rule": (O, lambda d: vendor(d)["read"].update(copy={"facts": [], "evidence": []}), "not exactly one of copy and rule"),
        "a read with neither": (O, lambda d: source(d, "upload")["read"].pop("copy"), "not exactly one of copy and rule"),
        "a read not closed": (O, lambda d: source(d, "upload")["read"].update(map={}), "has the member 'map'"),
        "an empty unwrap": (O, lambda d: vendor(d)["read"].update(unwrap=[]), "unwrap is not an array of one to four pointers"),
        "an unwrap that is no pointer": (O, lambda d: vendor(d)["read"].update(unwrap=["content"]), "unwrap is not an array of one to four pointers"),
        "a reconciliation read on an operation": (U, lambda d: items(d).update(read={"sources": ["rates"], "rule": {}}), "has a reconciliation read, which only a research source has"),
        # §6.2, copies
        "a copy without facts": (O, lambda d: op(d)["read"]["copy"].pop("facts"), "has no member facts"),
        "a copy's facts not an array": (O, lambda d: op(d)["read"]["copy"].update(facts={}), "copy facts is not an array"),
        "a fact copy not closed": (O, lambda d: op(d)["read"]["copy"]["facts"][0].update(extra=1), "has the member 'extra'"),
        "a fact copy to the empty pointer": (O, lambda d: op(d)["read"]["copy"]["facts"][0].update(target=""), "is not a fact target"),
        "a fact copy from no pointer": (O, lambda d: op(d)["read"]["copy"]["facts"][0].update(source="facts"), "is not a JSON Pointer"),
        "a copy writing one target twice": (O, lambda d: op(d)["read"]["copy"]["facts"].append({"target": "/converted", "source": "/x"}), "writes the fact target '/converted' twice"),
        "an evidence copy of an empty requirement": (O, lambda d: op(d)["read"]["copy"]["evidence"][0].update(requirement=""), "requirement that is not a non-empty string"),
        "a copy naming a requirement twice": (O, lambda d: op(d)["read"]["copy"]["evidence"].append({"requirement": "rates", "source": "/x"}), "names the requirement 'rates' twice"),
        "the case's copy to the empty pointer": (O, lambda d: d["case"]["facts"][0].update(target=""), "is not a fact target"),
        # §6.3, rules
        "a rule not closed": (O, lambda d: rule(d).update(extra=1), "has the member 'extra'"),
        "a ruleVersion of 2": (O, lambda d: rule(d).update(ruleVersion="2"), "ruleVersion is not the string \"1\""),
        "a ruleVersion of the integer 1": (O, lambda d: rule(d).update(ruleVersion=1), "ruleVersion is not the string \"1\""),
        "a rule without parameters": (O, lambda d: rule(d).pop("parameters"), "has no member parameters"),
        "a rule parameter of a fourth type": (O, lambda d: rule(d)["parameters"].update(count="number"), "of a type other than string, integer and timestamp"),
        "a rule parameter of another type than its scope's": (O, lambda d: rule(d)["parameters"].update(count="string"), "which is not a string parameter of its scope"),
        "a rule parameter outside the scope": (O, lambda d: rule(d)["parameters"].update(other="string"), "'other' as string, which is not a string parameter of its scope"),
        "no clauses": (O, lambda d: rule(d).update(clauses=[]), "clauses is not an array of one to 64 clauses"),
        "a last clause that is not always": (O, lambda d: rule(d)["clauses"].pop(), "last clause's when is not"),
        "a clause not closed": (O, lambda d: first(d).update(extra=1), "has the member 'extra'"),
        "a reason that is not a string": (O, lambda d: first(d).update(reason=None), "reason is not a string"),
        "an unknown op": (O, lambda d: first(d)["when"]["of"].append({"op": "matches", "field": "/x"}), "unknown op 'matches'"),
        "an op that is not a string": (O, lambda d: first(d)["when"]["of"].append({"op": ["exists"], "field": "/x"}), "is not an object with an op"),
        "a condition with a member more": (O, lambda d: first(d)["when"]["of"][0].update(to=1), "has the member 'to'"),
        "a condition without its field": (O, lambda d: first(d)["when"]["of"][3].pop("field"), "has no member field"),
        "a field that is no pointer": (O, lambda d: first(d)["when"]["of"][3].update(field="ok"), "field that is not a JSON Pointer"),
        "always with a member more": (O, lambda d: rule(d)["clauses"][-1]["when"].update(field="/x"), "has the member 'field'"),
        "equalsParam naming an undeclared parameter": (O, lambda d: first(d)["when"]["of"][2].update(param="amount"), "names 'amount', not a parameter its rule declares"),
        "freshWithin's asOf undeclared": (O, lambda d: first(d)["when"]["of"][5].update(asOf="since"), "names 'since', not a parameter its rule declares"),
        "freshWithin's maxAge not a name": (O, lambda d: first(d)["when"]["of"][5].update(maxAge=60), "names 60"),
        "all without a list": (O, lambda d: first(d)["when"].update(of={"op": "always"}), "does not list its conditions"),
        "not of a list": (O, lambda d: rule(d)["clauses"][1]["when"]["of"][0].update(of=[]), "is not an object with an op"),
        "a claim not closed": (O, lambda d: first(d)["claim"].update(extra=1), "has the member 'extra'"),
        "a claim fact not closed": (O, lambda d: first(d)["claim"]["facts"][0].update(extra=1), "has the member 'extra'"),
        "a claim fact to the empty pointer": (O, lambda d: first(d)["claim"]["facts"][0].update(pointer=""), "pointer that is not a fact target"),
        "a claim fact from no pointer": (O, lambda d: first(d)["claim"]["facts"][0].update({"from": "id"}), "from that is not a JSON Pointer"),
        "a claim writing one target twice": (O, lambda d: first(d)["claim"]["facts"].append({"pointer": "/vendor/id", "from": "/x"}), "writes the fact target '/vendor/id' twice"),
        "a claim's evidence an array": (O, lambda d: first(d)["claim"].update(evidence=[]), "claim evidence is not an object"),
        "an empty requirement id": (O, lambda d: first(d)["claim"]["evidence"].update({"": "present"}), "an empty requirement id"),
        "an availability of another value": (O, lambda d: first(d)["claim"]["evidence"].update({"vendor-record": "maybe"}), "not present, absent or unknown"),
        "an acquisitionStatus of another value": (O, lambda d: first(d)["claim"].update(acquisitionStatus="found"), "acquisitionStatus is not resolved, absent or unknown"),
        # §8, targets and admission
        "a fact target equal to another source's": (O, lambda d: source(d, "upload")["read"]["copy"]["facts"][0].update(target="/converted"), "is also one of"),
        "a fact target equal to the case's": (O, lambda d: source(d, "upload")["read"]["copy"]["facts"][0].update(target="/request"), "is also one of"),
        "a fact target below another's": (O, lambda d: source(d, "upload")["read"]["copy"]["facts"][0].update(target="/converted/amount"), "one a prefix of the other"),
        "a fact target below one of its own source's": (O, lambda d: op(d)["read"]["copy"]["facts"].append({"target": "/converted/x", "source": "/x"}), "one a prefix of the other"),
        "a requirement of two sources": (O, lambda d: source(d, "upload")["read"]["copy"]["evidence"].append({"requirement": "rates", "source": "/x"}), "is an evidence target of 'fx' and 'upload'"),
        "a requirement of the case and a source": (O, lambda d: op(d)["read"]["copy"]["evidence"].append({"requirement": "intake-form", "source": "/x"}), "is an evidence target of 'case' and 'fx'"),
        "admits not closed": (O, lambda d: d["admits"].update(other={}), "admits has the member 'other'"),
        "admits null": (O, lambda d: d.update(admits=None), "admits is not an object"),
        "admits naming a target no source writes": (O, lambda d: d["admits"]["facts"].update({"/elsewhere": ["record"]}), "names '/elsewhere', which no source writes"),
        "admits naming a requirement no source writes": (O, lambda d: d["admits"]["evidence"].update({"other": ["record"]}), "names 'other', which no source writes"),
        "admits of another class": (O, lambda d: d["admits"]["facts"].update({"/upload": ["model"]}), "is not an array of classes"),
        "admits.facts written empty in version 3": (U, lambda d: d.update(admits={"facts": {}}), "admits.facts is written empty"),
        "admits.evidence written empty in version 3": (U, lambda d: d.update(admits={"evidence": {}}), "admits.evidence is written empty"),
        # §4.3, research
        "a research source without fields": (R, lambda d: company(d).pop("fields"), "has no member fields"),
        "a research source without capabilities": (R, lambda d: company(d).pop("capabilities"), "has no member capabilities"),
        "a research source with arguments": (R, lambda d: company(d).update(arguments={}), "has the member 'arguments'"),
        "a question that is a number": (R, lambda d: company(d).update(question=1), "question is not a string template"),
        "a question that is a plain object": (R, lambda d: company(d).update(question={"text": "x"}), "question is not a string template"),
        "a question naming an integer parameter": (R, lambda d: (d["case"]["parameters"].update(n={"pointer": "/n", "type": "integer"}), company(d).update(question={"$param": "n"})), "not a string or timestamp parameter"),
        "a question naming no parameter in scope": (R, lambda d: company(d).update(question={"$param": "elsewhere"}), "which is not in its scope"),
        "constraints an array": (R, lambda d: company(d).update(constraints=[]), "constraints is not an object"),
        "an empty model": (R, lambda d: company(d).update(model=""), "model is not a non-empty string"),
        "evidence not an array": (R, lambda d: company(d).update(evidence="x"), "evidence is not an array of non-empty strings"),
        "an empty evidence instruction": (R, lambda d: company(d).update(evidence=[""]), "evidence is not an array of non-empty strings"),
        "no field declared": (R, lambda d: company(d).update(fields=[]), "fields is not an array of 1 to 64 declarations"),
        "a field declaration with a member more": (R, lambda d: company(d)["fields"][0].update(unit="x"), "has the member 'unit'"),
        "a field named case": (R, lambda d: company(d)["fields"][0].update(name="case"), "name is not a non-empty string other than case"),
        "a field declared twice": (R, lambda d: company(d)["fields"][1].update(name="company-id"), "declares the field 'company-id' twice"),
        "a field of another type": (R, lambda d: company(d)["fields"][0].update(type="float"), "type is not one of integer, decimal"),
        "a field whose required is a string": (R, lambda d: company(d)["fields"][0].update(required="yes"), "required is not a boolean"),
        "a field with an empty description": (R, lambda d: company(d)["fields"][0].update(description=""), "description is not a non-empty string"),
        "no capability": (R, lambda d: company(d).update(capabilities=[]), "capabilities is not a non-empty array of names"),
        "capabilities without answer": (R, lambda d: company(d).update(capabilities=["search"]), "answer among them"),
        "capabilities out of order": (R, lambda d: banded(d).update(capabilities=["answer", "page", "search"]), "in that order"),
        "a capability twice": (R, lambda d: banded(d).update(capabilities=["answer", "search", "search"]), "distinct names"),
        "an unknown capability": (R, lambda d: company(d).update(capabilities=["answer", "browse"]), "distinct names"),
        "research maxAge 0": (R, lambda d: company(d).update(maxAge=0), "maxAge is not an integer from 1 to 86400"),
        # §4.4, research binding
        "research with profile alone": (R, lambda d: company(d).update(profile="ai"), "partial binding members"),
        "research with profile and profileDigest, no webProfiles": (R, lambda d: secondary(d).pop("webProfiles"), "partial binding members"),
        "research with webProfiles alone": (R, lambda d: company(d).update(webProfiles={}), "partial binding members"),
        "research with an operation catalog member": (R, lambda d: company(d).update(platform="ai"), "has the operation catalog member platform"),
        "a bound research source with a catalog member": (R, lambda d: secondary(d).update(record="ai"), "has the operation catalog member record"),
        "webProfiles missing a requested capability": (R, lambda d: secondary(d).update(webProfiles={}), "not exactly the web capabilities"),
        "webProfiles assigning an unrequested capability": (R, lambda d: secondary(d)["webProfiles"].update(search={"profile": "w", "profileDigest": E}), "not exactly the web capabilities"),
        "webProfiles assigning answer": (R, lambda d: secondary(d)["webProfiles"].update(answer={"profile": "w", "profileDigest": E}), "not exactly the web capabilities"),
        "webProfiles an array": (R, lambda d: secondary(d).update(webProfiles=[]), "webProfiles is not an object"),
        "a web assignment with a member more": (R, lambda d: secondary(d)["webProfiles"]["page"].update(model="m"), "has the member 'model'"),
        "a web assignment's digest": (R, lambda d: secondary(d)["webProfiles"]["page"].update(profileDigest="web"), "profileDigest is not a digest"),
        "a bound research source's empty profile": (R, lambda d: secondary(d).update(profile=""), "profile is not a non-empty string"),
        # §4.3, reading fields
        "a copy of the whole record": (R, lambda d: company(d)["read"]["copy"]["facts"][0].update(source=""), "reads '', which is not among"),
        "a copy of a retained response": (R, lambda d: company(d)["read"]["copy"]["facts"][0].update(source="/responses/0/result"), "which is not among"),
        "a copy of an undeclared field": (R, lambda d: company(d)["read"]["copy"]["facts"][0].update(source="/fields/headcount/value"), "which is not among"),
        "a pointer below a status": (R, lambda d: company(d)["read"]["copy"]["facts"][0].update(source="/fields/active/status/0"), "which is not among"),
        "a copy from under values": (R, lambda d: company(d)["read"]["copy"]["facts"][0].update(source="/fields/roles/values/0/value"), "under values"),
        "a rule's from under values": (R, lambda d: banded(d)["read"]["rule"]["clauses"][0]["claim"]["facts"][0].update({"from": "/fields/band/values/0/value"}), "under values"),
        "an observation index of another form": (R, lambda d: banded(d)["read"]["rule"]["clauses"][1]["when"].update(field="/fields/roles/values/01/value"), "which is not among"),
        "a condition on an undeclared field": (R, lambda d: banded(d)["read"]["rule"]["clauses"][2]["when"].update(field="/fields/headcount/cites"), "which is not among"),
        "an evidence copy outside the list": (R, lambda d: company(d)["read"]["copy"]["evidence"].append({"requirement": "r", "source": "/responses"}), "which is not among"),
        "an unwrap outside the list": (R, lambda d: company(d)["read"].update(unwrap=["/responses/0/result/text"]), "which is not among"),
        "an unwrap, then a copy under responses": (R, lambda d: company(d)["read"].update(unwrap=["/fields/company-id/value"], copy={"facts": [{"target": "/company/fields", "source": "/responses/secret"}], "evidence": []}), "reads '/responses/secret', which is not among"),
        "an unwrap, then a copy under values": (R, lambda d: company(d)["read"].update(unwrap=["/fields/company-id/value"], copy={"facts": [{"target": "/company/fields", "source": "/fields/roles/values/0/value"}], "evidence": []}), "takes a value from '/fields/roles/values/0/value', under values"),
        "an invalid second unwrap pointer": (R, lambda d: company(d)["read"].update(unwrap=["/fields/company-id/value", "/responses/0/result"]), "reads '/responses/0/result', which is not among"),
        "an unwrap from values": (R, lambda d: company(d)["read"].update(unwrap=["/fields/roles/values/0/value"]), "takes a value from '/fields/roles/values/0/value', under values"),
        "an evidence copy from under values": (R, lambda d: company(d)["read"]["copy"]["evidence"].append({"requirement": "r", "source": "/fields/roles/values/0/value"}), "under values"),
        "a condition below an observation's value": (R, lambda d: banded(d)["read"]["rule"]["clauses"][1]["when"].update(field="/fields/roles/values/1/value/0"), "reads '/fields/roles/values/1/value/0', which is not among"),
        "a condition at an observation, not its value": (R, lambda d: banded(d)["read"]["rule"]["clauses"][1]["when"].update(field="/fields/roles/values/1"), "which is not among"),
        # §6.4, reconciliation
        "a reconciliation with an unwrap": (R, lambda d: combined(d)["read"].update(unwrap=["/x"]), "has the member 'unwrap'"),
        "a reconciliation with a copy": (R, lambda d: combined(d)["read"].update(copy={"facts": [], "evidence": []}), "has the member 'copy'"),
        "a reconciliation naming no source": (R, lambda d: combined(d)["read"].update(sources=[]), "names no earlier sources"),
        "a reconciliation naming a source twice": (R, lambda d: combined(d)["read"]["sources"].append("primary"), "names an earlier source twice"),
        "a reconciliation naming itself": (R, lambda d: combined(d)["read"]["sources"].append("combined"), "names 'combined', which is not an earlier research source"),
        "a reconciliation naming a later source": (R, lambda d: d["sources"].insert(2, d["sources"].pop(4)), "which is not an earlier research source"),
        "a reconciliation naming no such source": (R, lambda d: combined(d)["read"]["sources"].append("elsewhere"), "names 'elsewhere'"),
        "a reconciliation naming a non-research source": (R, lambda d: (d["sources"].insert(0, {"name": "op", "kind": "operation", "profile": "p", "profileDigest": D, "maxAge": 1, "arguments": {}, "read": {"copy": {"facts": [], "evidence": []}}}), combined(d)["read"]["sources"].append("op")), "names 'op', which is not an earlier research source"),
        "a reconciliation's from under values": (R, lambda d: clauses(d)[0]["claim"]["facts"][0].update({"from": PRIMARY + "/values/0/value"}), "not a declared field's value"),
        "a reconciliation's from of a status": (R, lambda d: clauses(d)[0]["claim"]["facts"][0].update({"from": PRIMARY + "/status"}), "not a declared field's value"),
        "a reconciliation's from of an undeclared field": (R, lambda d: clauses(d)[0]["claim"]["facts"][0].update({"from": "/sources/primary/fields/revenue/value"}), "not a declared field's value"),
        "a reconciliation reading a source it does not name": (R, lambda d: combined(d)["read"].update(sources=["primary"]), "which is not within a declared field of a source it names"),
        "a reconciliation condition outside a field entry": (R, lambda d: clauses(d)[4]["when"]["of"].append({"op": "exists", "field": "/sources/primary/responses"}), "which is not within a declared field"),
        "a selecting clause without its found guard": (R, lambda d: clauses(d)[0].update(when={"op": "exists", "field": PRIMARY + "/value"}), "without the guard that its status is found"),
        "a found guard nested below an all": (R, lambda d: clauses(d)[1].update(when={"op": "all", "of": [unavailable(PRIMARY), {"op": "all", "of": [guard(SECONDARY, "found")]}]}), "without the guard that its status is found"),
        "a selected field without its not-found guard": (R, lambda d: clauses(d)[1]["when"]["of"].__setitem__(0, {"op": "any", "of": [absent(PRIMARY), guard(PRIMARY, "stale")]}), "as not-found"),
        "a selected field without its stale guard": (R, lambda d: clauses(d)[1]["when"]["of"].__setitem__(0, {"op": "any", "of": [absent(PRIMARY), guard(PRIMARY, "not-found")]}), "as stale"),
        "a selected field without its conflicting guard": (R, lambda d: clauses(d)[2]["when"]["of"].pop(0), "as conflicting"),
        "a selected field without its absence guard": (R, lambda d: clauses(d)[1]["when"]["of"].__setitem__(0, {"op": "any", "of": [guard(PRIMARY, "not-found"), guard(PRIMARY, "stale")]}), "'s absence"),
        "a reconciliation claim writing evidence": (R, lambda d: clauses(d)[2]["claim"]["evidence"].update(r="unknown"), "writes evidence"),
        "a last clause that resolves": (R, lambda d: clauses(d)[-1]["claim"].update(acquisitionStatus="resolved"), "last always clause"),
        "a last clause with a fact": (R, lambda d: clauses(d)[-1]["claim"]["facts"].append({"pointer": "/count", "from": CURRENT + "/value"}), "last always clause"),
        "a reconciliation's target overlapping another's": (R, lambda d: clauses(d)[0]["claim"]["facts"][0].update(pointer="/observed/primary/count"), "one a prefix of the other"),
        "a reconciliation's rule malformed": (R, lambda d: combined(d)["read"]["rule"].update(ruleVersion="2"), "ruleVersion is not the string"),
    }


class FormRefusals(unittest.TestCase):
    """Every form refusal, input-malformed, with a detail naming the rule."""

    def test_each_rule(self):
        for label, (base, alter, fragment) in refusal_cases().items():
            with self.subTest(label):
                refused(self, altered(base, alter), "input-malformed", fragment)

    def test_the_cases_are_distinct_documents(self):
        seen = {}
        for label, (base, alter, _) in refusal_cases().items():
            data = encode(altered(base, alter))
            self.assertNotIn(data, seen, f"{label} is the document of {seen.get(data)}")
            seen[data] = label

    def test_kind_unread_comes_after_every_form(self):
        # §11: phase 5 (every document's form, each source's against its kind's, whatever its kind) before
        # phase 6 (a kind the reader does not read).
        for label, alter, fragment in [
            ("the case", lambda d: d["case"].update(extra=1), "case has the member 'extra'"),
            ("a read source's form", lambda d: source(d, "items").pop("maxAge"), "has no member maxAge"),
            ("an unread source's read", lambda d: source(d, "by-web").update(read={}), "not exactly one of copy and rule"),
            ("the targets", lambda d: source(d, "by-sql")["read"]["copy"]["facts"][0].update(target="/web"), "is also one of"),
            ("admission", lambda d: d.update(admits={"evidence": {"nothing": ["record"]}}), "which no source writes"),
        ]:
            with self.subTest(label):
                refused(self, altered(with_unread_kinds, alter), "input-malformed", fragment)

    def test_the_observation_pointers(self):
        # §4.3: descendants are given to /fields/<name>/value alone; /fields/<name>/values/<index>/value is
        # admitted exactly.
        declared = ["band", "roles"]
        for pointer in ["/fields/band/value", "/fields/band/value/min", "/fields/roles/value/0/x", "/fields/roles/values/0/value", "/fields/roles/values/12/value"]:
            with self.subTest(pointer):
                self.assertTrue(dialect_form.research_pointer_ok(pointer, declared))
        for pointer in ["/fields/roles/values/0/value/0", "/fields/band/values/0/value/min", "/fields/roles/values/0", "/fields/roles/values", "/fields/roles/values/01/value", "/fields/roles/values/0/status", "/fields/roles/status/0", "/fields/roles/cites/0"]:
            with self.subTest(pointer):
                self.assertFalse(dialect_form.research_pointer_ok(pointer, declared))

    def test_the_checker_imports_no_reader(self):
        with open(dialect_form.__file__, encoding="utf-8") as handle:
            text = handle.read()
        for name in ("dialect_verify", "importlib", "subprocess", ".spec"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()

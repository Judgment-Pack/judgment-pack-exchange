"""Holds the release evidence gate's adoption to the workflows it reads (exchange #38).

The gate itself is the development kit's (lib/release_evidence.py, vendored as
scripts/dev/release_evidence.py), with its own tests in the kit. These tests hold this repository's
side: .github/ci-evidence.json names jobs, a workflow and input paths that exist; the checks it lets
a release reuse are the dev.json checks that read the commit's tree, and every other dev.json check
is run again at the tag by the release; ci.yml records the evidence the gate reads; release.yml runs
the gate before anything is written and keeps its decision record; and the vendored copy is the
kit's file. Standard library only: the workflows are read as text.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".github" / "ci-evidence.json"
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
GATE = ROOT / "scripts" / "dev" / "release_evidence.py"

# The kit release the gate is vendored from, and the git blob id of lib/release_evidence.py at that
# release's tag (`git rev-parse v0.10.0:lib/release_evidence.py` in a clone of the kit). A re-vendor
# changes both, from the kit's tag, with the other vendored scripts.
KIT_RELEASE = "v0.10.0"
KIT_BLOB = "d00e4d489ab5d34ecb56ec55e4c97b2dc9b88261"


def load_gate():
    spec = importlib.util.spec_from_file_location("release_evidence", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job_block(workflow: str, job_id: str) -> str:
    """The text of one job under `jobs:`, from its key to the next job's key."""
    match = re.search(r"^  %s:\n((?:(?:    .*)?\n)*)" % re.escape(job_id), workflow.split("\njobs:\n", 1)[1], re.M)
    return match.group(1) if match else ""


def needs(block: str) -> list[str]:
    match = re.search(r"^    needs:(?: (\S+)\n|\n((?:      - \S+\n)+))", block, re.M)
    if not match:
        return []
    return [match.group(1)] if match.group(1) else re.findall(r"- (\S+)", match.group(2))


def step(block: str, name: str) -> str:
    """The text of one step of a job, by its name, to the next step."""
    match = re.search(r"^      - name: %s\n((?:(?!      - ).*\n)*)" % re.escape(name), block, re.M)
    return match.group(0) if match else ""


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def dev_checks() -> list[str]:
    return [row["name"] for row in json.loads((ROOT / "dev.json").read_text(encoding="utf-8"))["checks"]]


def history_checks(ci: str) -> list[str]:
    found = re.findall(r"^      HISTORY_CHECKS: (\S+)$", ci, re.M)
    return found[0].split(",") if len(found) == 1 else []


class EvidenceConfiguration(unittest.TestCase):
    """.github/ci-evidence.json against the real ci.yml, dev.json and tree, so the two cannot drift."""

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    ci = CI.read_text(encoding="utf-8")

    def test_the_gate_accepts_the_configuration(self):
        gate = load_gate()
        try:
            gate.check_config(self.config)
        except gate.Refusal as refusal:
            self.fail(f"{refusal.code}: {refusal.detail}")
        self.assertEqual(self.config["repository"], "Judgment-Pack/judgment-pack-exchange")
        self.assertEqual(self.config["branch"], "main")

    def test_every_input_path_is_a_file_of_the_tree(self):
        for path in self.config["inputs"]:
            with self.subTest(path):
                self.assertTrue((ROOT / path).is_file(), f"{path} is not a file of the repository")

    def test_the_workflow_is_ci_yml_by_path_and_name(self):
        for key, workflow in self.config["workflows"].items():
            with self.subTest(key):
                self.assertEqual(workflow["path"], ".github/workflows/ci.yml")
                self.assertTrue((ROOT / workflow["path"]).is_file())
                self.assertEqual(re.findall(r"^name: (.+)$", self.ci, re.M), [workflow["name"]])
                # Only a push to main is evidence: the workflow is not dispatched (the fresh route
                # re-runs main's run), and no skipped job is permitted.
                self.assertEqual(workflow["events"], ["push"])
                self.assertNotIn("skipped_jobs", workflow)

    def test_every_required_job_is_a_job_of_ci_yml_on_its_labels(self):
        jobs = re.findall(r"^  ([A-Za-z0-9_-]+):\n", self.ci.split("\njobs:\n", 1)[1], re.M)
        for key, workflow in self.config["workflows"].items():
            self.assertEqual(sorted(spec["job_id"] for spec in workflow["jobs"].values()), sorted(jobs))
            for job_key, spec in workflow["jobs"].items():
                with self.subTest(job=job_key):
                    block = job_block(self.ci, spec["job_id"])
                    self.assertIn("    name: %s\n" % spec["name"], block)
                    self.assertEqual(re.findall(r"^    runs-on: (\S+)$", block, re.M), spec["labels"])
                    self.assertNotIn("strategy:", block)
                    self.assertNotIn("\n    if:", block)

    def test_the_reused_checks_and_the_tag_context_checks_are_dev_json_split_in_two(self):
        history = history_checks(self.ci)
        self.assertEqual(history, ["entries"])
        for job_key, spec in self.config["workflows"]["ci"]["jobs"].items():
            with self.subTest(job=job_key):
                self.assertIsInstance(spec["checks"], list, "\"all\" would take the history checks from main")
                self.assertEqual(spec.get("optional_skips", []), [])
                self.assertFalse(set(spec["checks"]) & set(history), "a history check is reused from main")
                self.assertEqual(sorted(spec["checks"] + history), sorted(dev_checks()))

    def test_the_evidence_log_is_read_as_the_gate_reads_it(self):
        # A summary block as scripts/dev/check.sh prints it, written by hand.
        gate = load_gate()
        spec = self.config["workflows"]["ci"]["jobs"]["entries"]
        block = (
            "== check summary (dev.json) ==\n"
            "handover: boundary 1 paths, shared 2 paths; see AGENTS.md \"Before you hand over\"\n"
            "PASS     local-paths              0s\n"
            "PASS     agent-docs               0s\n"
            "    sync-agent-docs: CLAUDE.md matches AGENTS.md\n"
            "PASS     diff-check               0s\n"
            "== 3 passed, 0 failed, 0 skipped, 0 not run ==\n"
        )
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            for name, text, expected in [
                ("reused", block, None),
                ("with entries", block.replace("== 3", "PASS     entries                  6s\n== 4"), "check-coverage"),
                ("a check missing", block.replace("PASS     diff-check               0s\n", ""), "check-coverage"),
                ("a check skipped", block.replace("PASS     diff-check", "SKIP     diff-check"), "check-result"),
            ]:
                with self.subTest(name):
                    log = Path(scratch) / "checks.log"
                    log.write_text(text, encoding="utf-8")
                    try:
                        coverage = gate.coverage(spec, [("check", str(log))])
                        outcome = None
                    except gate.Refusal as refusal:
                        coverage, outcome = None, refusal.code
                    self.assertEqual(outcome, expected)
                    if expected is None:
                        self.assertEqual(coverage, {"local-paths": "PASS", "agent-docs": "PASS", "diff-check": "PASS"})

    def test_ci_records_the_evidence_on_a_push_to_main_after_the_checks(self):
        block = job_block(self.ci, "entries")
        checks = step(block, "Checks")
        self.assertIn("          CHECK_LOG: ${{ runner.temp }}/checks.log\n", checks)
        self.assertIn('scripts/dev/check.sh --all --skip "$HISTORY_CHECKS" | tee "$CHECK_LOG" || status=1\n', checks)
        self.assertIn('scripts/dev/check.sh --all --only "$HISTORY_CHECKS" || status=1\n', checks)
        self.assertIn("set -o pipefail\n", checks)
        capture = step(block, "Record exact CI inputs and coverage")
        upload = step(block, "Upload immutable CI evidence")
        main_push = "        if: github.ref == 'refs/heads/main' && github.event_name == 'push'\n"
        for key, workflow in self.config["workflows"].items():
            for job_key in workflow["jobs"]:
                with self.subTest(job=job_key):
                    self.assertIn(main_push, capture)
                    self.assertIn(
                        "python3 scripts/dev/release_evidence.py capture --workflow %s --job %s "
                        '--check-log "${{ runner.temp }}/checks.log" --output "${{ runner.temp }}/evidence.json"\n'
                        % (key, job_key), capture)
                    self.assertIn(main_push, upload)
                    self.assertIn("name: ci-evidence-%s-%s-${{ github.run_attempt }}\n" % (key, job_key), upload)
                    self.assertIn("path: ${{ runner.temp }}/evidence.json\n", upload)
                    self.assertIn("if-no-files-found: error\n", upload)
        steps = re.findall(r"^      - name: (.+)$", block, re.M)
        self.assertEqual(steps[-3:], ["Checks", "Record exact CI inputs and coverage", "Upload immutable CI evidence"])


class ReleaseWorkflow(unittest.TestCase):
    """release.yml takes the evidence before the tag-context run and the package, and fails closed."""

    release = RELEASE.read_text(encoding="utf-8")
    ci = CI.read_text(encoding="utf-8")

    def test_the_gate_runs_after_admission_and_keeps_its_record(self):
        block = job_block(self.release, "evidence")
        self.assertIn("    name: CI evidence at the tag\n", block)
        self.assertEqual(needs(block), ["admit"])
        self.assertIn("    permissions:\n      contents: read\n      # Reading the CI runs, their jobs and their evidence artifacts.\n"
                      "      actions: read\n    steps:\n", block)
        gate = step(block, "Reuse exact-commit main CI evidence, or refuse")
        self.assertIn("          GH_TOKEN: ${{ github.token }}\n", gate)
        self.assertIn('run: python3 scripts/dev/release_evidence.py verify --output "${{ runner.temp }}/release-evidence.json"\n', gate)
        self.assertNotIn("continue-on-error", block)
        self.assertNotIn("    if:", block.split("    steps:\n", 1)[0])
        # The decision record is kept on a refusal too: the upload runs unless the run was cancelled.
        record = step(block, "Keep the decision record")
        self.assertIn("        if: ${{ !cancelled() }}\n", record)
        self.assertIn("          name: release-evidence-${{ github.run_attempt }}\n", record)
        self.assertIn("          path: ${{ runner.temp }}/release-evidence.json\n          if-no-files-found: error\n", record)

    def test_the_gate_sets_up_the_python_ci_yml_ran_with(self):
        # The profile compares python3 with this runner's, so both jobs set it up in the same words.
        block, ci_block = job_block(self.release, "evidence"), job_block(self.ci, "entries")
        for name in ["Read the toolchains from dev.json", "Set up Python"]:
            with self.subTest(name):
                self.assertTrue(step(block, name))
                self.assertEqual(step(block, name), step(ci_block, name))

    def test_the_tag_context_run_follows_the_gate_and_the_package_waits_for_both(self):
        verify = job_block(self.release, "verify")
        self.assertIn("    name: CI at the tag\n", verify)
        self.assertEqual(needs(verify), ["admit", "evidence"])
        self.assertIn("    uses: ./.github/workflows/ci.yml\n    with:\n      tag-context: true\n", verify)
        self.assertEqual(needs(job_block(self.release, "package")), ["admit", "evidence", "verify"])
        self.assertEqual(self.release.count("uses: ./.github/workflows/ci.yml"), 1)

    def test_ci_runs_the_history_checks_alone_in_the_tag_context(self):
        self.assertIn("  workflow_call:\n    inputs:\n      tag-context:\n", self.ci)
        self.assertIn("        type: boolean\n        default: false\n", self.ci)
        checks = step(job_block(self.ci, "entries"), "Checks")
        self.assertIn("          TAG_CONTEXT: ${{ inputs.tag-context }}\n", checks)
        self.assertIn('          elif [ "$TAG_CONTEXT" = true ]; then\n'
                      '            scripts/dev/check.sh --all --only "$HISTORY_CHECKS"\n', checks)

    def test_a_tag_push_starts_no_second_run_at_the_tag(self):
        # The release's call is the one run in the tag's context; ci.yml's push trigger is held to
        # branches, and the release workflow is the one started by a tag.
        trigger = self.ci.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn('  push:\n    branches: ["**"]\n', trigger)
        self.assertEqual(re.findall(r"^\s*(tags|tags-ignore|branches-ignore|paths|paths-ignore):", trigger, re.M), [])
        self.assertIn('    tags:\n      # Narrowed here, held exactly to the grammar by the first step.\n'
                      '      - "v[0-9]+.[0-9]+.[0-9]+"\n', self.release)


class VendoredGate(unittest.TestCase):
    """scripts/dev/release_evidence.py is the kit's lib/release_evidence.py with the release on line 2."""

    data = GATE.read_bytes()

    def test_line_two_names_the_kit_release(self):
        self.assertEqual(self.data.split(b"\n")[1].decode("utf-8"),
                         f"# from judgment-pack-devkit {KIT_RELEASE} (lib/release_evidence.py)")

    def test_the_rest_is_the_kits_file_byte_for_byte(self):
        lines = self.data.split(b"\n")
        self.assertEqual(git_blob_id(b"\n".join(lines[:1] + lines[2:])), KIT_BLOB)

    def test_the_vendored_scripts_name_one_kit_release(self):
        versions = {}
        for path in ["scripts/dev/check.sh", "scripts/dev/changed_checks.py", "scripts/dev/handover_check.sh",
                     "scripts/dev/release_evidence.py"]:
            line = (ROOT / path).read_text(encoding="utf-8").splitlines()[1]
            versions[path] = re.fullmatch(r"# from judgment-pack-devkit (v\S+) \(\S+\)", line).group(1)
        self.assertEqual(set(versions.values()), {KIT_RELEASE}, versions)


if __name__ == "__main__":
    unittest.main()

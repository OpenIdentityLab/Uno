import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UnoRuntimeTest(unittest.TestCase):
    def build_demo(self, tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
        bundle_path = tmp_path / "bundle.json"
        witnessed_bundle_path = tmp_path / "bundle_witnessed.json"
        state_path = tmp_path / "state"
        witness_state_path = tmp_path / "witness_state"
        manifest_path = tmp_path / "build_manifest.json"

        subprocess.run(
            [
                "python3",
                "runtime/uno_runtime.py",
                "build-demo",
                "--output",
                str(bundle_path),
                "--witnessed-output",
                str(witnessed_bundle_path),
                "--state-dir",
                str(state_path),
                "--witness-state-dir",
                str(witness_state_path),
                "--build-manifest-output",
                str(manifest_path),
                "--builder",
                "test-builder",
                "--external-witness-name",
                "Test Portable Witness",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return bundle_path, witnessed_bundle_path, state_path, witness_state_path, manifest_path

    def verify_bundle(self, bundle_path: Path, manifest_path: Path | None = None) -> dict:
        command = ["python3", "runtime/uno_runtime.py", "verify", "--bundle", str(bundle_path)]
        if manifest_path is not None:
            command.extend(["--expected-build-manifest", str(manifest_path)])
        verify = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(verify.stdout)

    def test_bundle_without_external_witness_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bundle_path, _, _, _, manifest_path = self.build_demo(tmp_path)
            payload = self.verify_bundle(bundle_path, manifest_path)
            self.assertEqual(payload["verdict"], "warning")
            self.assertEqual(payload["agentTrust"], "warning")
            self.assertEqual(payload["buildTrust"], "trust")
            self.assertIn("no external witness receipts provided", payload["missingOrWeakProofs"])

    def test_bundle_with_external_witness_is_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _, witnessed_bundle_path, _, _, manifest_path = self.build_demo(tmp_path)
            payload = self.verify_bundle(witnessed_bundle_path, manifest_path)
            self.assertEqual(payload["verdict"], "trust")
            self.assertEqual(payload["agentTrust"], "trust")
            self.assertEqual(payload["buildTrust"], "trust")
            self.assertTrue(any("Valid external witness receipts verified" in reason for reason in payload["reasons"]))

    def test_verify_without_expected_build_manifest_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _, witnessed_bundle_path, _, _, _ = self.build_demo(tmp_path)
            payload = self.verify_bundle(witnessed_bundle_path)
            self.assertEqual(payload["verdict"], "warning")
            self.assertEqual(payload["agentTrust"], "trust")
            self.assertEqual(payload["buildTrust"], "warning")
            self.assertIn("no expected build manifest supplied for comparison", payload["missingOrWeakProofs"])

    def test_external_witness_receipt_tamper_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _, witnessed_bundle_path, _, _, manifest_path = self.build_demo(tmp_path)
            tampered_bundle_path = tmp_path / "tampered_bundle.json"
            bundle = json.loads(witnessed_bundle_path.read_text(encoding="utf-8"))
            bundle["witnessReceipts"][0]["witnessId"] = bundle["agentId"]["id"]
            tampered_bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            payload = self.verify_bundle(tampered_bundle_path, manifest_path)
            self.assertEqual(payload["verdict"], "not-trusted")
            self.assertEqual(payload["agentTrust"], "not-trusted")
            self.assertTrue(any("reuses the agent identity" in reason for reason in payload["reasons"]))

    def test_branch_event_at_tip_degrades_to_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            state_path = tmp_path / "state"
            manifest_path = tmp_path / "build_manifest.json"
            bundle_path = tmp_path / "branch_bundle.json"

            subprocess.run(
                [
                    "python3",
                    "runtime/uno_runtime.py",
                    "init-agent",
                    "--controller",
                    "local",
                    "--display-name",
                    "Branch Demo",
                    "--kind",
                    "agent",
                    "--role",
                    "assistant",
                    "--context",
                    "offline",
                    "--state-dir",
                    str(state_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    "runtime/uno_runtime.py",
                    "append-event",
                    "--state-dir",
                    str(state_path),
                    "--event-type",
                    "branch",
                    "--note",
                    "Non-canonical tip branch for V1 warning check",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    "runtime/uno_runtime.py",
                    "build-manifest",
                    "--output",
                    str(manifest_path),
                    "--code-path",
                    "runtime/uno_runtime.py",
                    "--code-path",
                    "runtime/uno_witness.py",
                    "--builder",
                    "test-builder",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "python3",
                    "runtime/uno_runtime.py",
                    "export-bundle",
                    "--state-dir",
                    str(state_path),
                    "--output",
                    str(bundle_path),
                    "--build-manifest",
                    str(manifest_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self.verify_bundle(bundle_path, manifest_path)
            self.assertEqual(payload["verdict"], "warning")
            self.assertEqual(payload["agentTrust"], "warning")
            self.assertTrue(any("forbids branches" in reason for reason in payload["reasons"]))

    def test_verify_with_mismatched_expected_build_manifest_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _, witnessed_bundle_path, _, _, manifest_path = self.build_demo(tmp_path)
            mismatched_manifest_path = tmp_path / "expected_manifest.json"

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["builder"] = "different-builder"
            mismatched_manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            payload = self.verify_bundle(witnessed_bundle_path, mismatched_manifest_path)
            self.assertEqual(payload["verdict"], "not-trusted")
            self.assertEqual(payload["agentTrust"], "trust")
            self.assertEqual(payload["buildTrust"], "not-trusted")
            self.assertTrue(any("Expected build manifest does not match" in reason for reason in payload["reasons"]))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["CALL_MODULES"] = "tests.test_commands_support"
    cwd = ROOT
    if extra_env:
        cwd = Path(extra_env.pop("CALL_CWD", cwd))
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "call.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class CallCliTests(unittest.TestCase):
    def test_positional_args(self) -> None:
        result = run_cli("add", "1", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3")
        self.assertEqual(result.stderr.strip(), "")

    def test_named_args(self) -> None:
        result = run_cli("add", "-a", "1", "-b", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3")
        self.assertEqual(result.stderr.strip(), "")

    def test_mixed_args(self) -> None:
        result = run_cli("add", "1", "-b", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3")
        self.assertEqual(result.stderr.strip(), "")

    def test_missing_args(self) -> None:
        result = run_cli("add", "1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing required argument", result.stderr)
        self.assertIn("b", result.stderr)

    def test_extra_args_warn(self) -> None:
        result = run_cli("add", "1", "2", "3")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3")
        self.assertIn("warning: Unused positional arguments", result.stderr)
        self.assertIn("'3'", result.stderr)

    def test_unknown_named_args_warn(self) -> None:
        result = run_cli("add", "1", "2", "-c", "3")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3")
        self.assertIn("warning: Unknown named arguments", result.stderr)
        self.assertIn("c='3'", result.stderr)

    def test_log_redirection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "call.log"
            result = run_cli("emit", "hello", "--log", str(log_path))
            self.assertEqual(result.returncode, 0)
            self.assertIn("OUT: hello", result.stdout)
            self.assertIn("ERR: hello", result.stderr)

            log_contents = log_path.read_text(encoding="utf-8")
            self.assertIn("OUT: hello", log_contents)
            self.assertIn("ERR: hello", log_contents)

    def test_modules_file_in_cwd_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "CALL_MODULES").write_text("tests.test_commands_support\n", encoding="utf-8")

            result = run_cli(
                "add",
                "1",
                "2",
                extra_env={"CALL_MODULES": "", "CALL_CWD": str(tmp_path)},
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "3")

    def test_modules_file_in_parent_dir_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            nested = tmp_path / "one" / "two"
            nested.mkdir(parents=True)
            (tmp_path / "CALL_MODULES").write_text("tests.test_commands_support\n", encoding="utf-8")

            result = run_cli(
                "add",
                "1",
                "2",
                extra_env={"CALL_MODULES": "", "CALL_CWD": str(nested)},
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "3")

    def test_modules_file_can_load_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            module_path = tmp_path / "commands" / "custom.py"
            module_path.parent.mkdir(parents=True)
            module_path.write_text(
                "from call import call\n\n"
                "@call\n"
                "def triple(value: int) -> None:\n"
                "    print(value * 3)\n",
                encoding="utf-8",
            )
            (tmp_path / "CALL_MODULES").write_text("commands/custom.py\n", encoding="utf-8")

            result = run_cli(
                "triple",
                "7",
                extra_env={"CALL_MODULES": "", "CALL_CWD": str(tmp_path)},
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "21")


if __name__ == "__main__":
    unittest.main()

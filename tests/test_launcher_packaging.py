import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
ZSH = "/bin/zsh"
ENTRY_POINTS = ("video-compress", "launch-in-terminal")
HELPER_NAMES = ("video-compress-fs.zsh", "video-compress-progress.zsh")
SCRIPT_NAMES = ENTRY_POINTS + HELPER_NAMES
EXECUTE_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def snapshot_tree(root):
    snapshot = {}
    for path in [root] + sorted(root.rglob("*")):
        info = path.lstat()
        content = None
        if path.is_symlink():
            content = os.readlink(str(path))
        elif path.is_file():
            content = path.read_bytes()
        snapshot[str(path.relative_to(root))] = (
            info.st_mode, info.st_mtime_ns, content
        )
    return snapshot


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.caller = self.root / "caller"
        self.terminal = self.root / "terminal"
        self.bin_dir = self.root / "bin with 'quotes'"
        for directory in (self.caller, self.terminal, self.bin_dir):
            directory.mkdir()
        self.launcher = self.bin_dir / "launch-in-terminal"
        shutil.copy2(str(REPO_ROOT / "bin/launch-in-terminal"), str(self.launcher))
        worker = self.bin_dir / "video-compress"
        worker.write_text(
            '#!/bin/zsh\n'
            'printf \'%s\\0\' "$SHOW_PROGRESS" "$@" > "$TEST_ARGUMENTS"\n'
            'exit "${TEST_EXIT_CODE:-0}"\n',
            encoding="utf-8",
        )
        worker.chmod(0o755)
        self.arguments = self.root / "arguments"
        self.env = os.environ.copy()
        self.env.update(DRY_RUN="1", TEST_ARGUMENTS=str(self.arguments))

    def run_launcher(self, targets, mode="--flat", trace=False):
        command = [ZSH, "-f"]
        if trace:
            command.append("-x")
        command.extend([str(self.launcher), mode] + list(targets))
        return subprocess.run(
            command, cwd=str(self.caller), env=self.env,
            capture_output=True, text=True, check=False,
        )

    def assert_no_terminal_calls(self, result):
        self.assertNotIn("/usr/bin/mktemp", result.stderr)
        self.assertNotIn("/usr/bin/open", result.stderr)
        self.assertNotIn("/bin/chmod", result.stderr)
        self.assertFalse(self.arguments.exists())

    def assert_command_targets(self, targets, expected, mode="--flat", exit_code=0):
        if self.arguments.exists():
            self.arguments.unlink()
        result = self.run_launcher(targets, mode=mode)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("SHOW_PROGRESS=1 "))
        self.assertFalse(self.arguments.exists())
        env = self.env.copy()
        env["TEST_EXIT_CODE"] = str(exit_code)
        # Only the copied launcher and recording stub run, never the real worker.
        executed = subprocess.run(
            [ZSH, "-f", "-c", result.stdout], cwd=str(self.terminal), env=env,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(executed.returncode, exit_code, executed.stderr)
        recorded = self.arguments.read_bytes().split(b"\0")
        self.assertEqual(recorded.pop(), b"")
        self.assertEqual(
            [os.fsdecode(value) for value in recorded],
            ["1", mode] + [str(path) for path in expected],
        )
        return executed

    def test_cwd_relative_targets_in_both_modes(self):
        folder = self.caller / "videos"
        folder.mkdir()
        for mode in ("--flat", "--recursive"):
            with self.subTest(mode=mode):
                self.assert_command_targets(
                    ["videos", "./videos", ".", "..", "/"],
                    [folder, folder, self.caller, self.root, Path("/")],
                    mode=mode,
                )

    def test_whitespace_quotes_and_newline_targets(self):
        names = [
            "space and\ttab", "single' and double\" quotes", "-leading-dash",
            "$(touch injected); $HOME & `echo test` [*]",
            "line\nbreak", "trailing\n", "trailing\n\n",
        ]
        folders = [self.caller / name for name in names]
        for folder in folders:
            folder.mkdir()
        self.assert_command_targets(names, folders)
        self.assert_command_targets([str(folder) for folder in folders], folders)
        self.assertFalse((self.terminal / "injected").exists())

    def test_symlinks_and_parent_components_resolve_physically(self):
        physical = self.root / "physical" / "nested"
        physical.mkdir(parents=True)
        link = self.caller / "link"
        link.symlink_to(physical, target_is_directory=True)
        self.assert_command_targets(
            ["link", "link/..", str(link)],
            [physical, physical.parent, physical],
        )

    def test_invalid_targets_are_rejected_before_serializing(self):
        regular_file = self.caller / "file"
        regular_file.write_text("not a directory", encoding="utf-8")
        (self.caller / "dangling").symlink_to(self.caller / "missing")
        before = snapshot_tree(self.root)
        for target in ("missing", "file", "file/child", "dangling", ""):
            with self.subTest(target=target):
                result = self.run_launcher([".", target], trace=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)
                self.assert_no_terminal_calls(result)
                self.assertEqual(snapshot_tree(self.root), before)

    def test_dry_run_has_no_side_effects(self):
        before = snapshot_tree(self.root)
        result = self.run_launcher(["."], trace=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_no_terminal_calls(result)
        self.assertEqual(snapshot_tree(self.root), before)

    def test_missing_target_and_usage_behavior(self):
        result = self.run_launcher([], trace=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assert_no_terminal_calls(result)
        for mode, expected_code in (("--help", 0), ("--invalid", 2)):
            with self.subTest(mode=mode):
                result = self.run_launcher([], mode=mode)
                self.assertEqual(result.returncode, expected_code)
                self.assertIn("--flat|--recursive", result.stdout)

    def test_terminal_command_preserves_exit_status_and_messages(self):
        success = self.assert_command_targets(["."], [self.caller])
        self.assertIn("\u5904\u7406\u5b8c\u6210", success.stdout)
        failure = self.assert_command_targets(["."], [self.caller], exit_code=7)
        self.assertIn("\u6709\u5931\u8d25\u9879", failure.stdout)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo with 'quotes'"
        self.repo.mkdir()
        for directory in ("bin", "scripts", "workflows"):
            shutil.copytree(str(REPO_ROOT / directory), str(self.repo / directory))
        for name in HELPER_NAMES:
            helper = self.repo / "bin" / name
            if not helper.exists():
                helper.write_text("# Sourced zsh packaging fixture.\n", encoding="utf-8")
                helper.chmod(0o644)
        self.resources = sorted(
            (self.repo / "workflows").glob("*.workflow/Contents/Resources")
        )
        self.assertEqual(len(self.resources), 2)

    def run_sync(self, *args):
        return subprocess.run(
            [str(self.repo / "scripts/sync-workflows")] + list(args),
            cwd=str(self.root), capture_output=True, text=True, check=False,
        )

    def sync_successfully(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_check_is_read_only(self, valid, path=None):
        before = snapshot_tree(self.repo)
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 0 if valid else 1, result.stderr)
        if path is not None:
            self.assertIn(str(path), result.stderr)
        self.assertEqual(snapshot_tree(self.repo), before)

    def test_sync_copies_all_scripts_and_executable_bits_to_both_workflows(self):
        protected = {
            path: path.read_bytes()
            for path in (self.repo / "workflows").rglob("*")
            if path.is_file() and path.name not in SCRIPT_NAMES
        }
        for resource_dir in self.resources:
            for name in SCRIPT_NAMES:
                destination = resource_dir / name
                destination.write_bytes(b"stale content\n")
                destination.chmod(0o644)
        self.sync_successfully()
        for resource_dir in self.resources:
            for name in SCRIPT_NAMES:
                source = self.repo / "bin" / name
                destination = resource_dir / name
                self.assertEqual(destination.read_bytes(), source.read_bytes())
                self.assertEqual(
                    destination.stat().st_mode & EXECUTE_BITS,
                    source.stat().st_mode & EXECUTE_BITS,
                )
        self.assertEqual({path: path.read_bytes() for path in protected}, protected)
        self.assert_check_is_read_only(valid=True)

    def test_check_detects_content_drift_in_every_bundled_script(self):
        for resource_dir in self.resources:
            for name in SCRIPT_NAMES:
                with self.subTest(workflow=resource_dir, script=name):
                    self.sync_successfully()
                    destination = resource_dir / name
                    destination.write_bytes(destination.read_bytes() + b"\n# drift\n")
                    self.assert_check_is_read_only(valid=False, path=destination)

    def test_check_detects_each_executable_bit_mismatch(self):
        for resource_dir in self.resources:
            for name in SCRIPT_NAMES:
                for bit in (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH):
                    with self.subTest(workflow=resource_dir, script=name, bit=bit):
                        self.sync_successfully()
                        destination = resource_dir / name
                        destination.chmod(stat.S_IMODE(destination.stat().st_mode) ^ bit)
                        self.assert_check_is_read_only(valid=False, path=destination)

    def test_sourced_helpers_do_not_require_executable_bits(self):
        for name in HELPER_NAMES:
            (self.repo / "bin" / name).chmod(0o644)
        self.sync_successfully()
        for resource_dir in self.resources:
            for name in HELPER_NAMES:
                self.assertEqual((resource_dir / name).stat().st_mode & EXECUTE_BITS, 0)
        self.assert_check_is_read_only(valid=True)

    def test_check_detects_missing_bundled_scripts_without_recreating_them(self):
        for resource_dir in self.resources:
            for name in SCRIPT_NAMES:
                with self.subTest(workflow=resource_dir, script=name):
                    self.sync_successfully()
                    destination = resource_dir / name
                    destination.unlink()
                    self.assert_check_is_read_only(valid=False, path=destination)

    def test_check_rejects_missing_or_non_executable_canonical_scripts(self):
        self.sync_successfully()
        source = self.repo / "bin/video-compress"
        mode = stat.S_IMODE(source.stat().st_mode)
        source.chmod(0o644)
        self.assert_check_is_read_only(valid=False, path=source)
        source.chmod(mode)
        source.unlink()
        self.assert_check_is_read_only(valid=False, path=source)

    def test_check_requires_both_workflow_resources(self):
        self.sync_successfully()
        shutil.rmtree(str(self.resources[0]))
        self.assert_check_is_read_only(valid=False)

    def test_invalid_options_do_not_write(self):
        before = snapshot_tree(self.repo)
        for args in (("--invalid",), ("--check", "unexpected")):
            with self.subTest(args=args):
                result = self.run_sync(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(snapshot_tree(self.repo), before)


if __name__ == "__main__":
    unittest.main()

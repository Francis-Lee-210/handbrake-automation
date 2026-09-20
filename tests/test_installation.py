import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    "压缩视频-当前文件夹.workflow",
    "压缩视频-所有视频.workflow",
)
RESOURCES = (
    "video-compress", "launch-in-terminal", "video-compress-fs.zsh",
    "video-compress-progress.zsh", "video-compress-config.zsh",
)
ROOT_FILES = (
    "VERSION", "LICENSE", "README.md", "README.zh-CN.md", "config.example",
    "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md",
)
DOC_FILES = ("usage.md", "configuration.md", "troubleshooting.md", "open-source-design.md")
BACKUPS = ".handbrake-automation-backups"


def snapshot_tree(root):
    result = {}
    for path in [root] + sorted(root.rglob("*")):
        info = path.lstat()
        content = None
        if path.is_symlink():
            content = os.readlink(str(path))
        elif path.is_file():
            content = path.read_bytes()
        result[str(path.relative_to(root))] = (info.st_mode, content)
    return result


@unittest.skipUnless(sys.platform == "darwin", "macOS packaging and Finder workflows")
class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="handbrake-install-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "checkout with 'quotes'"
        self.repo.mkdir()
        for directory in ("bin", "scripts", "workflows"):
            shutil.copytree(REPO / directory, self.repo / directory)
        self.home = self.root / "home"
        self.home.mkdir()
        self.services = self.home / "Library/Services"
        self.env = dict(os.environ, HOME=str(self.home), VIDEO_COMPRESS_CONFIG="none")

    def run_script(self, name, *args, **env):
        return subprocess.run(
            [str(self.repo / "scripts" / name), *map(str, args)],
            cwd=self.root, env=dict(self.env, **env),
            capture_output=True, text=True, timeout=30,
        )

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def install(self, destination=None):
        result = self.run_script("install", "--services-dir", destination or self.services)
        self.assert_ok(result)
        return result

    def add_release_files(self):
        for name in ROOT_FILES:
            shutil.copy2(REPO / name, self.repo / name)
        (self.repo / "docs").mkdir()
        for name in DOC_FILES:
            shutil.copy2(REPO / "docs" / name, self.repo / "docs" / name)
        self.assert_ok(self.run_script("sync-workflows"))

    def test_help_and_invalid_options_do_not_write(self):
        before = snapshot_tree(self.root)
        for script in ("install", "uninstall", "package-release"):
            self.assert_ok(self.run_script(script, "--help"))
            option = "--output-dir" if script == "package-release" else "--services-dir"
            for args in (("--invalid",), (option,), (option, ""), (option, "--invalid")):
                with self.subTest(script=script, args=args):
                    result = self.run_script(script, *args)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(snapshot_tree(self.root), before)

    def test_dry_run_uses_home_and_writes_nothing(self):
        before = snapshot_tree(self.root)
        result = self.run_script("install", "--dry-run")
        self.assert_ok(result)
        self.assertIn(str(self.services), result.stdout)
        self.assertEqual(snapshot_tree(self.root), before)
        self.assertFalse(self.services.exists())

    def test_install_quotes_actual_destination_and_runs_both_entry_points(self):
        services = self.root / 'Services with \'single\' "double" $(touch injected)\nline'
        selected = self.root / "videos with 'quotes'"
        selected.mkdir()
        self.install(services)
        for workflow, mode in zip(WORKFLOWS, ("--flat", "--recursive")):
            with self.subTest(workflow=workflow):
                source = self.repo / "workflows" / workflow / "Contents/Resources"
                installed = services / workflow / "Contents/Resources"
                for name in RESOURCES:
                    self.assertEqual((installed / name).read_bytes(), (source / name).read_bytes())
                    self.assertEqual(
                        stat.S_IMODE((installed / name).stat().st_mode),
                        stat.S_IMODE((source / name).stat().st_mode),
                    )
                document = plistlib.loads((installed / "document.wflow").read_bytes())
                command = document["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
                result = subprocess.run(
                    ["/bin/zsh", "-f", "-c", command, "workflow", str(selected)],
                    cwd=self.root, env=dict(self.env, DRY_RUN="1"),
                    capture_output=True, text=True, timeout=10,
                )
                self.assert_ok(result)
                self.assertIn(mode, result.stdout)
                self.assertIn("SHOW_PROGRESS=1", result.stdout)
                self.assertIn("video-compress", result.stdout)
        self.assertFalse((self.root / "injected").exists())
        self.assertFalse((services / BACKUPS).exists())

    def test_upgrade_preserves_previous_workflows_and_user_configuration(self):
        self.install()
        old_contents = {}
        for name in WORKFLOWS:
            bundle = self.services / name
            (bundle / "local-marker").write_text("local customization\n", encoding="utf-8")
            old_contents[name] = snapshot_tree(bundle)
        config = self.home / ".config/handbrake-automation/config"
        config.parent.mkdir(parents=True)
        config.write_text("HANDBRAKE_PRESET=My local preset\n", encoding="utf-8")
        before_config = config.read_bytes()
        result = self.install()
        backups = list((self.services / BACKUPS).glob("install-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn(str(backups[0]), result.stdout)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(backups[0].parent.stat().st_mode), 0o700)
        for name in WORKFLOWS:
            self.assertEqual(snapshot_tree(backups[0] / name), old_contents[name])
            self.assertFalse((self.services / name / "local-marker").exists())
        self.assertEqual(config.read_bytes(), before_config)

    def test_unknown_same_named_workflow_prevents_all_changes(self):
        self.services.mkdir(parents=True)
        shutil.copytree(self.repo / "workflows" / WORKFLOWS[0], self.services / WORKFLOWS[0])
        unknown = self.services / WORKFLOWS[1] / "Contents"
        unknown.mkdir(parents=True)
        (unknown / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "other.project"}))
        before = snapshot_tree(self.root)
        for script in ("install", "uninstall"):
            with self.subTest(script=script):
                result = self.run_script(script, "--services-dir", self.services)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Unrecognized", result.stderr)
                self.assertEqual(snapshot_tree(self.root), before)

    def test_regular_file_conflict_is_not_overwritten(self):
        self.services.mkdir(parents=True)
        (self.services / WORKFLOWS[1]).write_text("keep me", encoding="utf-8")
        before = snapshot_tree(self.root)
        result = self.run_script("install")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(snapshot_tree(self.root), before)

    def test_symlink_services_workflow_and_backup_are_rejected(self):
        actual = self.root / "actual"
        actual.mkdir()
        self.services.parent.mkdir(parents=True)
        self.services.symlink_to(actual, target_is_directory=True)
        for target in ("services", "workflow", "backup"):
            with self.subTest(target=target):
                if target == "workflow":
                    self.services.unlink()
                    self.services.mkdir()
                    (self.services / WORKFLOWS[1]).symlink_to(actual, target_is_directory=True)
                elif target == "backup":
                    (self.services / WORKFLOWS[1]).unlink()
                    (self.services / BACKUPS).symlink_to(actual, target_is_directory=True)
                before = snapshot_tree(self.root)
                for script in ("install", "uninstall"):
                    result = self.run_script(script)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("symlink", result.stderr)
                    self.assertEqual(snapshot_tree(self.root), before)

    def test_nested_source_or_installed_symlink_is_rejected(self):
        self.install()
        installed = self.services / WORKFLOWS[0] / "Contents/Resources/video-compress"
        installed.unlink()
        installed.symlink_to(self.repo / "bin/video-compress")
        before = snapshot_tree(self.root)
        for script in ("install", "uninstall"):
            result = self.run_script(script)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr)
            self.assertEqual(snapshot_tree(self.root), before)
        installed.unlink()
        shutil.copy2(self.repo / "bin/video-compress", installed)
        source = self.repo / "workflows" / WORKFLOWS[1] / "Contents/Resources/video-compress"
        source.unlink()
        source.symlink_to(self.repo / "bin/video-compress")
        before = snapshot_tree(self.root)
        result = self.run_script("install")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(snapshot_tree(self.root), before)

    def test_uninstall_keeps_recoverable_workflows_configuration_and_videos(self):
        self.install()
        expected = {name: snapshot_tree(self.services / name) for name in WORKFLOWS}
        config = self.home / ".config/handbrake-automation/config"
        config.parent.mkdir(parents=True)
        config.write_text("HANDBRAKE_PRESET=My preset\n", encoding="utf-8")
        video = self.home / "source.mp4"
        video.write_bytes(b"source video")
        before = snapshot_tree(self.root)
        self.assert_ok(self.run_script("uninstall", "--dry-run"))
        self.assertEqual(snapshot_tree(self.root), before)
        self.assert_ok(self.run_script("uninstall"))
        backups = list((self.services / BACKUPS).glob("uninstall-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o700)
        for name in WORKFLOWS:
            self.assertFalse((self.services / name).exists())
            self.assertEqual(snapshot_tree(backups[0] / name), expected[name])
        self.assertEqual(config.read_text(encoding="utf-8"), "HANDBRAKE_PRESET=My preset\n")
        self.assertEqual(video.read_bytes(), b"source video")
        before = snapshot_tree(self.root)
        self.assert_ok(self.run_script("uninstall"))
        self.assertEqual(snapshot_tree(self.root), before)

    def test_uninstall_absent_services_is_read_only(self):
        before = snapshot_tree(self.root)
        self.assert_ok(self.run_script("uninstall"))
        self.assertEqual(snapshot_tree(self.root), before)

    def test_second_install_move_failure_restores_both_previous_workflows(self):
        self.install()
        expected = {}
        for name in WORKFLOWS:
            bundle = self.services / name
            (bundle / "local-marker").write_text("local customization", encoding="utf-8")
            expected[name] = snapshot_tree(bundle)
        wrapper = (
            'function /bin/mv { '
            'if [[ "$1" == *"/.handbrake-install."*"/$TEST_FAIL_WORKFLOW" ]]; then '
            'print -ru2 -- "fixture install move failure"; return 23; fi; '
            'command /bin/mv "$@"; }; source "$@"'
        )
        result = subprocess.run(
            ["/bin/zsh", "-f", "-c", wrapper, "fixture", str(self.repo / "scripts/install"),
             "--services-dir", str(self.services)],
            cwd=self.root, env=dict(self.env, TEST_FAIL_WORKFLOW=WORKFLOWS[1]),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        for name in WORKFLOWS:
            self.assertEqual(snapshot_tree(self.services / name), expected[name])
        self.assertFalse(list(self.services.glob(".handbrake-install.*")))

    def test_second_uninstall_move_failure_restores_both_workflows(self):
        self.install()
        expected = {name: snapshot_tree(self.services / name) for name in WORKFLOWS}
        wrapper = (
            'function /bin/mv { '
            'if [[ "$1" == "$TEST_FAIL_SOURCE" ]]; then '
            'print -ru2 -- "fixture uninstall move failure"; return 29; fi; '
            'command /bin/mv "$@"; }; source "$@"'
        )
        result = subprocess.run(
            ["/bin/zsh", "-f", "-c", wrapper, "fixture", str(self.repo / "scripts/uninstall"),
             "--services-dir", str(self.services)],
            cwd=self.root, env=dict(self.env, TEST_FAIL_SOURCE=str(self.services / WORKFLOWS[1])),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 29, result.stdout + result.stderr)
        for name in WORKFLOWS:
            self.assertEqual(snapshot_tree(self.services / name), expected[name])

    def test_release_contains_only_allowlisted_files_and_valid_checksum(self):
        self.add_release_files()
        for directory in ("reviews", ".git", "tests", "test-bin", "local"):
            private = self.repo / directory
            private.mkdir(exist_ok=True)
            (private / "private-marker").write_text("do not distribute", encoding="utf-8")
        (self.repo / "config").write_text("private config", encoding="utf-8")
        resources = self.repo / "workflows" / WORKFLOWS[0] / "Contents/Resources"
        (resources / "private-marker").write_text("do not distribute", encoding="utf-8")
        output = self.root / "releases with 'quotes'"
        self.assert_ok(self.run_script("package-release", "--output-dir", output))
        version = (self.repo / "VERSION").read_text(encoding="utf-8").strip()
        prefix = "handbrake-automation-" + version
        archive = output / (prefix + ".zip")
        expected = set(ROOT_FILES)
        expected.update("scripts/" + name for name in ("install", "uninstall"))
        expected.update("docs/" + name for name in DOC_FILES)
        expected.update("bin/" + name for name in RESOURCES)
        for workflow in WORKFLOWS:
            expected.add("workflows/" + workflow + "/Contents/Info.plist")
            expected.add("workflows/" + workflow + "/Contents/Resources/document.wflow")
            expected.update("workflows/" + workflow + "/Contents/Resources/" + name for name in RESOURCES)
        with zipfile.ZipFile(archive) as packaged:
            actual = {item.filename[len(prefix) + 1:] for item in packaged.infolist() if not item.is_dir()}
            self.assertEqual(actual, expected)
            for name in ("scripts/install", "scripts/uninstall", "bin/video-compress", "bin/launch-in-terminal"):
                self.assertTrue((packaged.getinfo(prefix + "/" + name).external_attr >> 16) & stat.S_IXUSR)
        digest, filename = (output / "SHA256SUMS").read_text(encoding="utf-8").strip().split("  ", 1)
        self.assertEqual(filename, archive.name)
        self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
        # Exercise the macOS extraction path, including executable permissions,
        # and install the distribution without access to checkout-only scripts.
        extracted = self.root / "extracted"
        result = subprocess.run(
            ["/usr/bin/ditto", "-x", "-k", str(archive), str(extracted)],
            capture_output=True, text=True, timeout=30,
        )
        self.assert_ok(result)
        release_install = extracted / prefix / "scripts/install"
        destination = self.root / "installed from release"
        result = subprocess.run(
            [str(release_install), "--services-dir", str(destination)],
            cwd=self.root, env=self.env, capture_output=True, text=True, timeout=30,
        )
        self.assert_ok(result)
        for workflow in WORKFLOWS:
            self.assertTrue((destination / workflow / "Contents/Resources/video-compress").is_file())

    def test_release_refuses_unsynchronized_resources_without_artifacts(self):
        self.add_release_files()
        resource = self.repo / "workflows" / WORKFLOWS[0] / "Contents/Resources/video-compress"
        resource.write_bytes(resource.read_bytes() + b"\n# unsynchronized fixture\n")
        before = snapshot_tree(self.root)
        result = self.run_script("package-release")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs", result.stderr)
        self.assertEqual(snapshot_tree(self.root), before)

    def test_release_refuses_symlink_inputs_and_output_conflicts(self):
        self.add_release_files()
        original = self.repo / "README.md"
        saved = self.root / "readme-source"
        original.rename(saved)
        original.symlink_to(saved)
        result = self.run_script("package-release")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.repo / "dist").exists())
        original.unlink()
        saved.rename(original)
        output = self.root / "releases"
        output.mkdir()
        existing = self.root / "existing-checksum"
        existing.write_text("keep me", encoding="utf-8")
        (output / "SHA256SUMS").symlink_to(existing)
        before = snapshot_tree(self.root)
        result = self.run_script("package-release", "--output-dir", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(snapshot_tree(self.root), before)


if __name__ == "__main__":
    unittest.main()

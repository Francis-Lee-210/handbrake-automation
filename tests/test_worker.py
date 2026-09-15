import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import unicodedata
import unittest


REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "bin/video-compress"
ORIGINALS = "\u539f\u59cb\u89c6\u9891"
COMPRESSED = "\u538b\u7f29\u89c6\u9891"


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handbrake-test-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "input"
        self.root.mkdir()
        self.calls = self.base / "calls"
        self.env = os.environ.copy()
        self.env.update(
            HANDBRAKECLI=str(REPO / "test-bin/HandBrakeCLI"),
            FFPROBE=str(REPO / "test-bin/ffprobe"),
            FAKE_HANDBRAKE_CALLS=str(self.calls),
            DISABLE_NOTIFICATIONS="1",
            SHOW_PROGRESS="1",
        )

    def video(self, name, root=None):
        path = (root or self.root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"source video fixture")
        return path

    def run_worker(self, *roots, mode="--flat", **env):
        result = subprocess.run(
            ["/bin/zsh", str(WORKER), mode, *map(str, roots or [self.root])],
            env=dict(self.env, **env), capture_output=True, text=True, timeout=45,
        )
        return result

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def call_paths(self):
        if not self.calls.exists():
            return []
        return [Path(os.fsdecode(item)) for item in self.calls.read_bytes().split(b"\0") if item]

    def outputs(self, root=None):
        directory = (root or self.root) / COMPRESSED
        return sorted(directory.glob("*.mp4"))

    def test_natural_order_and_verified_rerun(self):
        for name in ["10.mp4", "2.mp4", "1.mp4"]:
            self.video(name)
        self.assert_success(self.run_worker())
        self.assertEqual([p.name for p in self.call_paths()], ["1.mp4", "2.mp4", "10.mp4"])
        self.assertEqual(len(self.outputs()), 3)
        self.assert_success(self.run_worker())
        self.assertEqual(len(self.call_paths()), 3)
        self.assertFalse((self.root / COMPRESSED / ".video-compress-state/lock").exists())

    def test_recursive_order_overlap_and_managed_pruning(self):
        for directory in ["10", "2", "1"]:
            self.video("clip.mp4", self.root / directory)
        self.assert_success(self.run_worker(self.root / "2", self.root, mode="--recursive"))
        self.assertEqual([p.parent.parent.name for p in self.call_paths()], ["1", "2", "10"])
        self.assert_success(self.run_worker(mode="--recursive"))
        self.assertEqual(len(self.call_paths()), 3)

    def test_flat_does_not_process_children(self):
        child = self.video("nested.mp4", self.root / "child")
        self.assert_success(self.run_worker())
        self.assertTrue(child.exists())
        self.assertFalse(self.calls.exists())

    def test_recursive_does_not_follow_descendant_symlink(self):
        outside = self.base / "outside"
        source = self.video("1.mp4", outside)
        (self.root / "linked-child").symlink_to(outside, target_is_directory=True)
        self.assert_success(self.run_worker(mode="--recursive"))
        self.assertTrue(source.exists())
        self.assertFalse(self.calls.exists())

    def test_quiet_mode_and_no_ffprobe_fallback(self):
        self.video("1.mp4")
        result = self.run_worker(SHOW_PROGRESS="0", FFPROBE="/not-installed", PATH="/usr/bin:/bin:/usr/sbin")
        self.assert_success(result)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(self.outputs()), 1)

    def test_unavailable_ownership_query_fails_closed(self):
        script = REPO / "bin/video-compress-fs.zsh"
        result = subprocess.run(
            ["/bin/zsh", "-fc", 'source "$1"; ownership_enabled() { return 1; }; safe_directory "$2"',
             "test", str(script), str(self.root)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_collision_names_all_compress_and_stay_stable(self):
        names = ["1.mp4", "1.mov", "1 (mov).mp4"]
        for name in names:
            self.video(name)
        self.assert_success(self.run_worker())
        outputs = self.outputs()
        self.assertEqual(len(outputs), 3)
        self.assertEqual({p.read_text().strip() for p in outputs}, {"fake compressed: " + n for n in names})
        self.assert_success(self.run_worker())
        self.assertEqual(self.outputs(), outputs)
        self.assertEqual(len(self.call_paths()), 3)

    def test_case_folded_stems_do_not_collide(self):
        self.video("A.mp4")
        self.video("a.mov")
        self.assert_success(self.run_worker())
        self.assertEqual(len({p.name.casefold() for p in self.outputs()}), 2)

    def test_legacy_empty_output_is_preserved_but_not_skipped(self):
        self.video("1.mp4")
        legacy = self.root / COMPRESSED / "1.mp4"
        legacy.parent.mkdir()
        legacy.touch()
        self.assert_success(self.run_worker())
        self.assertEqual(legacy.stat().st_size, 0)
        self.assertEqual(len(self.call_paths()), 1)
        self.assertEqual(len(self.outputs()), 2)
        self.assert_success(self.run_worker())
        self.assertEqual(len(self.call_paths()), 1)

    def test_failure_partial_output_is_not_published_and_can_retry(self):
        self.video("1.mp4")
        result = self.run_worker(FAKE_HANDBRAKE_FAIL_PATTERN="*")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / ORIGINALS / "1.mp4").exists())
        self.assertEqual(self.outputs(), [])
        self.assertEqual(list((self.root / COMPRESSED / ".video-compress-state").glob("job.*")), [])
        self.assert_success(self.run_worker())
        self.assertEqual(len(self.outputs()), 1)

    def test_empty_success_is_rejected(self):
        self.video("1.mp4")
        result = self.run_worker(FAKE_HANDBRAKE_EMPTY_SUCCESS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.outputs(), [])

    def test_changed_source_and_changed_output_invalidate_receipt(self):
        self.video("1.mp4")
        self.assert_success(self.run_worker())
        self.outputs()[0].write_bytes(b"damaged")
        self.assert_success(self.run_worker())
        self.assertEqual(len(self.call_paths()), 2)
        (self.root / ORIGINALS / "1.mp4").write_bytes(b"replacement source")
        self.assert_success(self.run_worker())
        self.assertEqual(len(self.call_paths()), 3)

    def test_adding_conflicting_source_does_not_reencode_completed_file(self):
        self.video("1.mp4")
        self.assert_success(self.run_worker())
        self.video("1.mov")
        self.assert_success(self.run_worker())
        self.assertEqual([p.name for p in self.call_paths()], ["1.mp4", "1.mov"])

    def test_special_and_long_names(self):
        names = ["quote' space.mp4", "line\n\x1b[31m.mp4", "\u89c6" * 80 + ".mov", "%F{red}.mp4"]
        for name in names:
            self.video(name)
        result = self.run_worker()
        self.assert_success(result)
        self.assertEqual(len(self.outputs()), len(names))
        self.assertNotIn("\x1b", result.stdout)
        self.assertTrue(all(len(os.fsencode(p.name)) <= 255 for p in self.outputs()))

    def test_managed_directory_links_rejected_before_move(self):
        for name in [ORIGINALS, COMPRESSED]:
            with self.subTest(name=name):
                root = self.base / ("case-" + name)
                root.mkdir()
                source = self.video("1.mp4", root)
                outside = self.base / (name + "-outside")
                outside.mkdir()
                (root / name).symlink_to(outside, target_is_directory=True)
                result = self.run_worker(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(source.exists())
                self.assertEqual(list(outside.iterdir()), [])

    def test_log_symlink_hardlink_and_fifo_rejected(self):
        for kind in ["symlink", "hardlink", "fifo"]:
            with self.subTest(kind=kind):
                root = self.base / kind
                root.mkdir()
                source = self.video("1.mp4", root)
                compressed = root / COMPRESSED
                compressed.mkdir()
                sentinel = self.base / (kind + "-sentinel")
                sentinel.write_bytes(b"unchanged")
                log = compressed / "video-compress.log"
                if kind == "symlink":
                    log.symlink_to(sentinel)
                elif kind == "hardlink":
                    os.link(sentinel, log)
                else:
                    os.mkfifo(log)
                result = self.run_worker(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(sentinel.read_bytes(), b"unchanged")
                self.assertTrue(source.exists())

    def test_dangling_output_and_receipt_links_are_rejected(self):
        self.video("1.mp4")
        compressed = self.root / COMPRESSED
        compressed.mkdir()
        outside = self.base / "must-not-exist"
        link = compressed / "1.mp4"
        link.symlink_to(outside)
        self.assertNotEqual(self.run_worker().returncode, 0)
        self.assertFalse(outside.exists())
        link.unlink()
        state = compressed / ".video-compress-state"
        state.mkdir(mode=0o700)
        (state / "record.done").symlink_to(outside)
        self.assertNotEqual(self.run_worker().returncode, 0)
        self.assertFalse(outside.exists())

    def test_shared_writable_directory_and_ancestor_rejected(self):
        source = self.video("1.mp4")
        self.root.chmod(0o777)
        self.assertNotEqual(self.run_worker().returncode, 0)
        self.assertTrue(source.exists())
        self.root.chmod(0o700)
        self.base.chmod(0o777)
        self.assertNotEqual(self.run_worker().returncode, 0)
        self.assertTrue(source.exists())
        self.base.chmod(0o700)

    def test_allow_acl_rejected(self):
        source = self.video("1.mp4")
        subprocess.run(["/bin/chmod", "+a", "everyone allow add_file", str(self.root)], check=True)
        try:
            self.assertNotEqual(self.run_worker().returncode, 0)
            self.assertTrue(source.exists())
        finally:
            subprocess.run(["/bin/chmod", "-N", str(self.root)], check=True)

    def test_configuration_cannot_escape_root(self):
        source = self.video("1.mp4")
        for key in ["ORIGINAL_DIR_NAME", "COMPRESSED_DIR_NAME", "LOG_FILE_NAME"]:
            with self.subTest(key=key):
                self.assertNotEqual(self.run_worker(**{key: "../escape"}).returncode, 0)
        self.assertTrue(source.exists())

    def test_filesystem_aliases_cannot_merge_managed_directories(self):
        source = self.video("1.mp4")
        (self.root / "Media").mkdir()
        (self.root / "media").mkdir(exist_ok=True)
        if not (self.root / "Media").samefile(self.root / "media"):
            self.skipTest("requires a case-insensitive filesystem")
        result = self.run_worker(ORIGINAL_DIR_NAME="Media", COMPRESSED_DIR_NAME="media")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(source.exists())
        self.assertFalse(self.calls.exists())

    def test_existing_lock_is_not_stolen(self):
        source = self.video("1.mp4")
        lock = self.root / COMPRESSED / ".video-compress-state/lock"
        lock.mkdir(parents=True)
        self.assertNotEqual(self.run_worker().returncode, 0)
        self.assertTrue(lock.exists())
        self.assertTrue(source.exists())

    def test_progress_is_observable_before_encoder_exits(self):
        self.video("1.mp4")
        proc = subprocess.Popen(
            ["/bin/zsh", str(WORKER), "--flat", str(self.root)],
            env=dict(self.env, FAKE_HANDBRAKE_STEP_DELAY="0.5"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
        observed = False
        try:
            for line in proc.stdout:
                if re.search(r"\u5f53\u524d\s+25\.0%", line):
                    observed = proc.poll() is None
                    break
            stdout, stderr = proc.communicate(timeout=20)
            self.assertEqual(proc.returncode, 0, stdout + stderr)
            self.assertTrue(observed, "25% progress was buffered until process exit")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()

    def test_duration_weighted_overall_progress(self):
        self.video("1.mp4")
        self.video("2-long.mp4")
        result = self.run_worker()
        self.assert_success(result)
        self.assertRegex(result.stdout, r"\[1/2\] \u603b\u4f53\s+20\.0%.*\u5f53\u524d\s+100\.0%")

    def test_terminal_text_fits_width_and_does_not_expand_percent(self):
        script = REPO / "bin/video-compress-progress.zsh"
        text = "\u89c6\u9891" * 30 + "%F{red}\x1b\n.mp4"
        result = subprocess.run(
            ["/bin/zsh", "-fc", 'source "$1"; COLUMNS=40; fit_terminal_text "$2"', "test", str(script), text],
            capture_output=True, text=True, check=True,
        )
        width = sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in result.stdout)
        self.assertLessEqual(width, 39)
        self.assertNotIn("\x1b", result.stdout)
        self.assertNotIn("\n", result.stdout)

    def test_sigterm_preserves_source_and_releases_owned_lock(self):
        self.video("1.mp4")
        proc = subprocess.Popen(
            ["/bin/zsh", str(WORKER), "--flat", str(self.root)],
            env=dict(self.env, FAKE_HANDBRAKE_STEP_DELAY="2"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 15
            while not self.calls.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.calls.exists())
            os.killpg(proc.pid, signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 143, repr((stdout, stderr)))
            self.assertTrue((self.root / ORIGINALS / "1.mp4").exists())
            self.assertEqual(self.outputs(), [])
            self.assertFalse((self.root / COMPRESSED / ".video-compress-state/lock").exists(), repr((proc.returncode, stdout, stderr)))
            self.assert_success(self.run_worker())
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()


if __name__ == "__main__":
    unittest.main()

import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "bin/video-compress-fs.zsh"


class FilesystemPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handbrake-policy-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def query_policy(self, info, path="/Volumes/Personal/videos", device="/dev/disk9876s1"):
        fixture = self.base / "volume.plist"
        fixture.write_bytes(plistlib.dumps(info))
        command = (
            'source "$1"; '
            'function /bin/df { printf "Filesystem blocks used available capacity mount\\n%s 1 1 1 1%% /\\n" "$TEST_DEVICE"; }; '
            'function /usr/sbin/diskutil { /bin/cat "$TEST_PLIST"; }; '
            'volume_policy "$2" 123 && print -r -- "$REPLY"'
        )
        return subprocess.run(
            ["/bin/zsh", "-fc", command, "test", str(HELPER), path],
            env=dict(os.environ, TEST_PLIST=str(fixture), TEST_DEVICE=device),
            capture_output=True, text=True, timeout=10,
        )

    def external_info(self, **changes):
        info = dict(GlobalPermissionsEnabled=False, Internal=False,
                    WritableVolume=True, FilesystemType="apfs",
                    MountPoint="/Volumes/Personal")
        info.update(changes)
        return info

    def test_local_external_noowners_volume_is_supported(self):
        for filesystem in ("apfs", "hfs"):
            with self.subTest(filesystem=filesystem):
                result = self.query_policy(self.external_info(FilesystemType=filesystem))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "personal")

    def test_owned_volume_keeps_strict_policy(self):
        result = self.query_policy(dict(GlobalPermissionsEnabled=True), path="/Users/test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "owned")

    def test_exception_is_not_applied_to_unknown_internal_readonly_or_network_volumes(self):
        for info in [dict(), self.external_info(Internal=True),
                     self.external_info(WritableVolume=False),
                     self.external_info(FilesystemType="exfat"),
                     self.external_info(MountPoint="/somewhere/Personal")]:
            with self.subTest(info=info):
                self.assertNotEqual(self.query_policy(info).returncode, 0)
        self.assertNotEqual(self.query_policy(self.external_info(), device="server:/share").returncode, 0)

    def test_personal_policy_requires_path_inside_its_mount(self):
        for path in ("/Users/test", "/Volumes/Personal-other", "/Volumes/Personal/../Other"):
            with self.subTest(path=path):
                self.assertNotEqual(self.query_policy(self.external_info(), path=path).returncode, 0)

    def run_personal_checks(self, body, *arguments):
        command = (
            'source "$1"; shift; '
            'volume_policy() { '
            'if [[ "$1" == "$TEST_VOLUME" || "$1" == "$TEST_VOLUME"/* ]]; then REPLY=personal; '
            'else REPLY=owned; fi; }; '
            + body
        )
        return subprocess.run(
            ["/bin/zsh", "-fc", command, "test", str(HELPER), *map(str, arguments)],
            env=dict(os.environ, TEST_VOLUME=str(self.base / "volume")),
            capture_output=True, text=True, timeout=10,
        )

    def test_personal_directories_files_and_log_do_not_require_posix_ownership_permissions(self):
        volume = self.base / "volume"
        volume.mkdir(mode=0o775)
        volume.chmod(0o775)
        video = volume / "video.mp4"
        video.write_bytes(b"fixture")
        video.chmod(0o666)
        logfile = volume / "video-compress.log"
        logfile.write_bytes(b"")
        logfile.chmod(0o666)
        result = self.run_personal_checks(
            'safe_directory "$1" && safe_regular_file "$2" && open_folder_log "$3" && log_line "$3" verified',
            volume, video, logfile,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified", logfile.read_text())

    def test_personal_policy_still_rejects_links_and_fifos(self):
        volume = self.base / "volume"
        volume.mkdir()
        original = volume / "original"
        original.write_bytes(b"unchanged")
        linked_file = volume / "symlink"
        linked_file.symlink_to(original)
        hardlink = volume / "hardlink"
        os.link(original, hardlink)
        fifo = volume / "fifo"
        os.mkfifo(fifo)
        linked_directory = volume / "linked-directory"
        linked_directory.symlink_to(self.base, target_is_directory=True)
        for path in (linked_file, hardlink, fifo):
            with self.subTest(path=path.name):
                self.assertNotEqual(self.run_personal_checks('safe_regular_file "$1"', path).returncode, 0)
        self.assertNotEqual(self.run_personal_checks('safe_directory "$1"', linked_directory).returncode, 0)
        self.assertEqual(original.read_bytes(), b"unchanged")

    def test_personal_policy_does_not_relax_ancestors_outside_the_volume(self):
        volume = self.base / "volume"
        volume.mkdir()
        self.base.chmod(0o777)
        try:
            result = self.run_personal_checks('safe_directory "$1"', volume)
            self.assertNotEqual(result.returncode, 0)
        finally:
            self.base.chmod(0o700)

    def test_personal_policy_still_rejects_allow_acl(self):
        volume = self.base / "volume"
        volume.mkdir()
        subprocess.run(["/bin/chmod", "+a", "everyone allow add_file", str(volume)], check=True)
        try:
            self.assertNotEqual(self.run_personal_checks('safe_directory "$1"', volume).returncode, 0)
        finally:
            subprocess.run(["/bin/chmod", "-N", str(volume)], check=True)


if __name__ == "__main__":
    unittest.main()

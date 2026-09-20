import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
KEYS = (
    "HANDBRAKECLI", "FFPROBE", "HANDBRAKE_PRESET", "HANDBRAKE_IMPORT_GUI",
    "ORIGINAL_DIR_NAME", "COMPRESSED_DIR_NAME", "LOG_FILE_NAME", "SHOW_PROGRESS",
    "DISABLE_NOTIFICATIONS", "VIDEO_COMPRESS_CONFIG", "XDG_CONFIG_HOME",
)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handbrake-config-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / "config with 'quotes'"
        self.env = {key: value for key, value in os.environ.items() if key not in KEYS}
        self.env.update(
            XDG_CONFIG_HOME=str(self.root / "xdg"),
            DISABLE_NOTIFICATIONS="1",
        )

    def values(self, **overrides):
        script = (
            'source "$1"; load_video_compress_config || exit; shift; '
            'for key in "$@"; do printf "%s\\0" "${(P)key}"; done'
        )
        return subprocess.run(
            ["/bin/zsh", "-fc", script, "test",
             str(REPO / "bin/video-compress-config.zsh"), *KEYS[:9]],
            env=dict(self.env, **overrides), cwd=self.root,
            capture_output=True, check=False,
        )

    def parsed(self, **overrides):
        result = self.values(**overrides)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return dict(zip(KEYS[:9], result.stdout.decode().split("\0")[:-1]))

    def test_missing_default_config_uses_portable_defaults_without_writing(self):
        before = sorted(self.root.rglob("*"))
        values = self.parsed()
        self.assertEqual(values["HANDBRAKE_PRESET"], "Fast 1080p30")
        self.assertEqual(values["HANDBRAKE_IMPORT_GUI"], "0")
        self.assertEqual(sorted(self.root.rglob("*")), before)

    def test_configuration_quotes_whitespace_and_environment_precedence(self):
        self.config.write_text(
            " # comment\nHANDBRAKE_PRESET = 'My GUI preset'\n"
            'HANDBRAKE_IMPORT_GUI=1\nORIGINAL_DIR_NAME="Original Videos"\n'
        )
        values = self.parsed(VIDEO_COMPRESS_CONFIG=str(self.config))
        self.assertEqual(values["HANDBRAKE_PRESET"], "My GUI preset")
        self.assertEqual(values["ORIGINAL_DIR_NAME"], "Original Videos")
        self.assertEqual(values["HANDBRAKE_IMPORT_GUI"], "1")
        values = self.parsed(VIDEO_COMPRESS_CONFIG=str(self.config), HANDBRAKE_PRESET="Override")
        self.assertEqual(values["HANDBRAKE_PRESET"], "Override")

    def test_default_xdg_location_and_explicit_disable(self):
        target = Path(self.env["XDG_CONFIG_HOME"]) / "handbrake-automation/config"
        target.parent.mkdir(parents=True)
        target.write_text("HANDBRAKE_PRESET=Custom\n")
        self.assertEqual(self.parsed()["HANDBRAKE_PRESET"], "Custom")
        self.assertEqual(self.parsed(VIDEO_COMPRESS_CONFIG="none")["HANDBRAKE_PRESET"], "Fast 1080p30")

    def test_commands_and_variables_remain_literal(self):
        sentinel = self.root / "must-not-exist"
        value = f'$(touch {sentinel}); `touch {sentinel}` $HOME ~'
        self.config.write_text("HANDBRAKE_PRESET=" + value + "\n")
        self.assertEqual(self.parsed(VIDEO_COMPRESS_CONFIG=str(self.config))["HANDBRAKE_PRESET"], value)
        self.assertFalse(sentinel.exists())

    def test_rejects_missing_explicit_file_and_invalid_configuration(self):
        result = self.values(VIDEO_COMPRESS_CONFIG=str(self.config))
        self.assertNotEqual(result.returncode, 0)
        for content in (
            "export HANDBRAKE_PRESET=Custom\n", "touch /tmp/never\n",
            "PATH=/tmp\n", "SHOW_PROGRESS=2\n",
            "HANDBRAKE_PRESET=One\nHANDBRAKE_PRESET=Two\n",
        ):
            with self.subTest(content=content):
                self.config.write_text(content)
                result = self.values(VIDEO_COMPRESS_CONFIG=str(self.config))
                self.assertNotEqual(result.returncode, 0)

    def test_executable_discovery_and_explicit_relative_path(self):
        commands = self.root / "commands"
        commands.mkdir()
        for name in ("HandBrakeCLI", "ffprobe"):
            executable = commands / name
            executable.write_text("#!/bin/zsh\nexit 0\n")
            executable.chmod(0o755)
        values = self.parsed(PATH=str(commands) + ":/usr/bin:/bin")
        self.assertEqual(values["HANDBRAKECLI"], str(commands / "HandBrakeCLI"))
        self.assertEqual(values["FFPROBE"], str(commands / "ffprobe"))
        values = self.parsed(HANDBRAKECLI="commands/HandBrakeCLI", FFPROBE="/not-installed")
        self.assertEqual(values["HANDBRAKECLI"], str(commands / "HandBrakeCLI"))
        self.assertEqual(values["FFPROBE"], "/not-installed")

    def test_doctor_checks_exact_preset_and_never_encodes(self):
        calls = self.root / "calls"
        executable = self.root / "HandBrakeCLI"
        executable.write_text(
            '#!/bin/zsh\nprintf "%s\\n" "$@" >> "$TEST_CALLS"\n'
            'print -r -- "    Fast 1080p30"\n'
        )
        executable.chmod(0o755)
        for preset, expected in (("Fast 1080p30", 0), ("Fast 1080p3", 1)):
            with self.subTest(preset=preset):
                result = subprocess.run(
                    [str(REPO / "bin/video-compress"), "--doctor"],
                    env=dict(self.env, HANDBRAKECLI=str(executable), HANDBRAKE_PRESET=preset,
                             TEST_CALLS=str(calls)),
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(calls.read_text().splitlines(), ["--preset-list", "--preset-list"])

    def test_gui_preset_import_is_explicit(self):
        calls = self.root / "calls"
        executable = self.root / "HandBrakeCLI"
        executable.write_text(
            '#!/bin/zsh\nprintf "%s\\n" "$@" > "$TEST_CALLS"\n'
            'print -r -- "    My GUI preset"\n'
        )
        executable.chmod(0o755)
        self.config.write_text("HANDBRAKE_PRESET=My GUI preset\nHANDBRAKE_IMPORT_GUI=1\n")
        result = subprocess.run(
            [str(REPO / "bin/video-compress"), "--doctor"],
            env=dict(self.env, VIDEO_COMPRESS_CONFIG=str(self.config), HANDBRAKECLI=str(executable),
                     TEST_CALLS=str(calls)), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls.read_text().splitlines(), ["--preset-import-gui", "--preset-list"])

    def test_terminal_overrides_survive_changed_cwd_and_fresh_environment(self):
        caller = self.root / "caller"
        terminal = self.root / "terminal"
        caller.mkdir()
        terminal.mkdir()
        self.config.write_text("HANDBRAKE_PRESET=Fast 1080p30\n")
        target = caller / "videos"
        target.mkdir()
        # Use a recording worker so no folders are changed and no Terminal opens.
        copied_bin = self.root / "bin"
        copied_bin.mkdir()
        launcher = copied_bin / "launch-in-terminal"
        launcher.write_bytes((REPO / "bin/launch-in-terminal").read_bytes())
        launcher.chmod(0o755)
        worker = copied_bin / "video-compress"
        worker.write_text('#!/bin/zsh\nprintf "%s\\0" "$VIDEO_COMPRESS_CONFIG" "$HANDBRAKECLI" "$HANDBRAKE_PRESET"\n')
        worker.chmod(0o755)
        handbrake = caller / "custom cli"
        handbrake.write_text("#!/bin/zsh\nexit 0\n")
        handbrake.chmod(0o755)
        preset = 'A \'quoted\' preset; $(touch SHOULD_NOT_EXIST)'
        launched = subprocess.run(
            [str(launcher), "--flat", str(target)], cwd=caller,
            env=dict(self.env, DRY_RUN="1", VIDEO_COMPRESS_CONFIG="../" + self.config.name,
                     HANDBRAKECLI="custom cli", PATH=".:/usr/bin:/bin", HANDBRAKE_PRESET=preset),
            capture_output=True, text=True,
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)
        executed = subprocess.run(
            ["/bin/zsh", "-fc", launched.stdout], cwd=terminal, env=self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout.split("\0")[:3], [str(self.config), str(handbrake), preset])
        self.assertFalse((terminal / "SHOULD_NOT_EXIST").exists())

    def test_notification_arguments_are_not_applescript_source(self):
        payload = '\\" & (do shell script "touch SHOULD_NOT_EXIST") & "'
        # Intercept osascript while sourcing the worker; record argv and script separately.
        wrapper = (
            'function /usr/bin/osascript { printf "%s\\0" "$@" > "$ARGUMENTS"; '
            '/bin/cat > "$SOURCE_TEXT"; }; source "$1" --doctor'
        )
        args = self.root / "arguments"
        source = self.root / "applescript"
        result = subprocess.run(
            ["/bin/zsh", "-fc", wrapper, "test", str(REPO / "bin/video-compress")],
            cwd=self.root, env=dict(self.env, HANDBRAKECLI=payload, DISABLE_NOTIFICATIONS="0",
                                    ARGUMENTS=str(args), SOURCE_TEXT=str(source)),
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(payload, args.read_text())
        self.assertNotIn(payload, source.read_text())
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())


if __name__ == "__main__":
    unittest.main()

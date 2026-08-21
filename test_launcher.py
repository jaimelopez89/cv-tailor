"""Tests for the macOS app launcher.

The launcher's job is lifecycle, not UI: bring a server up, hand the window to
Chrome, and clean up exactly what it started. CVTAILOR_BROWSER lets these tests
stand in a plain command for Chrome so that logic is exercisable headlessly.
"""

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

BASE = Path(__file__).parent
LAUNCHER = BASE / "scripts" / "cvtailor"
BUNDLE = BASE / "CV Tailor.app"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _answers(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _wait_for(port: int, up: bool, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _answers(port) == up:
            return True
        time.sleep(0.2)
    return False


def _run_launcher(port: int, browser: str, timeout: int = 60):
    env = {**os.environ, "CVTAILOR_PORT": str(port), "CVTAILOR_BROWSER": browser}
    return subprocess.run([str(LAUNCHER)], env=env, timeout=timeout,
                          capture_output=True, text=True)


class TestLauncherScript:
    def test_launcher_is_executable(self):
        assert LAUNCHER.exists(), f"{LAUNCHER} missing"
        assert os.access(LAUNCHER, os.X_OK), "launcher must be executable"

    def test_serves_the_app_while_the_window_is_open(self):
        """The window command must find a live server when it runs."""
        port = _free_port()
        probe = BASE / f".probe-{port}"
        # The stand-in "browser" records whether the app answered while it ran.
        browser = f'bash -c "curl -sf http://127.0.0.1:{port}/api/templates -o {probe} || true"'
        try:
            _run_launcher(port, browser)
            assert probe.exists() and probe.stat().st_size > 0, \
                "app was not serving when the window opened"
        finally:
            probe.unlink(missing_ok=True)

    def test_stops_the_server_it_started_when_the_window_closes(self):
        port = _free_port()
        _run_launcher(port, "true")
        assert _wait_for(port, up=False, timeout=15), \
            "server outlived the window it was started for"

    def test_leaves_a_server_it_did_not_start_alive(self):
        """Launching must never take down an already-running dev server."""
        port = _free_port()
        proc = subprocess.Popen(
            ["python", "-m", "uvicorn", "app:app", "--port", str(port), "--host", "127.0.0.1"],
            cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            assert _wait_for(port, up=True), "fixture server never came up"
            _run_launcher(port, "true")
            time.sleep(1.5)
            assert _answers(port), "launcher killed a server it did not start"
            assert proc.poll() is None
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_reports_a_failure_instead_of_opening_a_dead_window(self):
        """A server that never comes up must not silently open a broken window."""
        port = _free_port()
        env = {**os.environ, "CVTAILOR_PORT": str(port), "CVTAILOR_BROWSER": "true",
               "CVTAILOR_UVICORN": "false", "CVTAILOR_TIMEOUT": "3"}
        res = subprocess.run([str(LAUNCHER)], env=env, timeout=40,
                             capture_output=True, text=True)
        assert res.returncode != 0
        assert "start" in (res.stderr + res.stdout).lower()


class TestRosettaLaunch:
    """macOS runs script-based .app bundles under Rosetta unless told otherwise.

    The base interpreter here is universal2, so it inherits the parent process's
    architecture — translated to x86_64 it cannot load the arm64 wheels in venv.
    """

    @pytest.mark.skipif(
        subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True,
                       text=True).stdout.strip() != "1",
        reason="Apple Silicon only")
    def test_serves_the_app_when_launched_translated(self):
        port = _free_port()
        probe = BASE / f".probe-rosetta-{port}"
        browser = f'bash -c "curl -sf http://127.0.0.1:{port}/api/templates -o {probe} || true"'
        env = {**os.environ, "CVTAILOR_PORT": str(port), "CVTAILOR_BROWSER": browser}
        try:
            subprocess.run(["arch", "-x86_64", str(LAUNCHER)], env=env,
                           timeout=90, capture_output=True, text=True)
            assert probe.exists() and probe.stat().st_size > 0, \
                "server did not come up when the launcher ran translated"
        finally:
            probe.unlink(missing_ok=True)


class TestInstalledCopy:
    """Spotlight will not index a symlinked .app, so installing means copying.

    A copy lives outside the repo and cannot find the project by walking up from
    its own path — the installer has to bake the location in.
    """

    def test_a_copy_outside_the_repo_still_serves_the_app(self, tmp_path):
        installer = BASE / "scripts" / "install_app.sh"
        assert installer.exists() and os.access(installer, os.X_OK), "installer missing"
        subprocess.run([str(installer), str(tmp_path)], check=True,
                       capture_output=True, text=True, timeout=60)

        stub = tmp_path / "CV Tailor.app" / "Contents" / "MacOS" / "CV Tailor"
        assert stub.exists(), "installer did not produce a bundle"
        assert not (tmp_path / "CV Tailor.app").is_symlink(), \
            "installed bundle must be a real copy, not a symlink"

        port = _free_port()
        probe = BASE / f".probe-copy-{port}"
        env = {**os.environ, "CVTAILOR_PORT": str(port),
               "CVTAILOR_BROWSER":
                   f'bash -c "curl -sf http://127.0.0.1:{port}/api/templates -o {probe} || true"'}
        try:
            subprocess.run([str(stub)], env=env, timeout=90, capture_output=True, text=True)
            assert probe.exists() and probe.stat().st_size > 0, \
                "installed copy could not find and start the project"
        finally:
            probe.unlink(missing_ok=True)


class TestAppBundle:
    def test_bundle_has_an_executable_stub(self):
        stub = BUNDLE / "Contents" / "MacOS" / "CV Tailor"
        assert stub.exists(), f"{stub} missing"
        assert os.access(stub, os.X_OK)

    def test_bundle_plist_is_valid_and_names_the_stub(self):
        plist = BUNDLE / "Contents" / "Info.plist"
        assert plist.exists()
        out = subprocess.run(["plutil", "-lint", str(plist)], capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
        name = subprocess.run(
            ["plutil", "-extract", "CFBundleExecutable", "raw", "-o", "-", str(plist)],
            capture_output=True, text=True).stdout.strip()
        assert name == "CV Tailor"

    def test_bundle_asks_for_native_execution(self):
        """Without this LaunchServices runs the script bundle under Rosetta."""
        plist = BUNDLE / "Contents" / "Info.plist"
        val = subprocess.run(
            ["plutil", "-extract", "LSRequiresNativeExecution", "raw", "-o", "-", str(plist)],
            capture_output=True, text=True)
        assert val.returncode == 0, "LSRequiresNativeExecution missing from Info.plist"
        assert val.stdout.strip() in ("true", "1")

    def test_bundle_has_an_icon(self):
        icon = BUNDLE / "Contents" / "Resources" / "cvtailor.icns"
        assert icon.exists() and icon.stat().st_size > 0

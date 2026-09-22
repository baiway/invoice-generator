"""
Tests for src/weasyprint_libs.py library path configuration.

This module tests the macOS `DYLD_FALLBACK_LIBRARY_PATH` setup that lets
WeasyPrint find its Homebrew-installed system libraries.
"""

import os
import sys
import pytest

from src import weasyprint_libs
from src.weasyprint_libs import LIBRARY_MARKER, configure_library_path

ENV_VAR = "DYLD_FALLBACK_LIBRARY_PATH"


@pytest.fixture
def homebrew_lib_dir(tmp_path, monkeypatch):
    """A fake Homebrew lib directory containing the WeasyPrint libraries."""
    lib_dir = tmp_path / "homebrew" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / LIBRARY_MARKER).touch()
    monkeypatch.setattr(weasyprint_libs, "HOMEBREW_LIB_DIRS", (str(lib_dir),))
    monkeypatch.setattr(sys, "platform", "darwin")
    return str(lib_dir)


class TestConfigureLibraryPath:
    """Tests for configure_library_path function."""

    def test_prepends_homebrew_dir_when_unset(
        self, homebrew_lib_dir, monkeypatch
    ):
        """Should put the Homebrew lib directory first in the search path."""
        monkeypatch.delenv(ENV_VAR, raising=False)

        configure_library_path()

        search_path = os.environ[ENV_VAR].split(os.pathsep)
        assert search_path[0] == homebrew_lib_dir

    def test_keeps_dyld_default_directories(
        self, homebrew_lib_dir, monkeypatch
    ):
        """Should not drop the directories dyld searches by default."""
        monkeypatch.delenv(ENV_VAR, raising=False)

        configure_library_path()

        search_path = os.environ[ENV_VAR].split(os.pathsep)
        assert "/usr/local/lib" in search_path
        assert "/usr/lib" in search_path
        assert os.path.expanduser("~/lib") in search_path

    def test_preserves_existing_search_path(
        self, homebrew_lib_dir, monkeypatch
    ):
        """Should prepend to an existing value rather than replace it."""
        monkeypatch.setenv(ENV_VAR, "/opt/custom/lib")

        configure_library_path()

        assert os.environ[ENV_VAR] == f"{homebrew_lib_dir}{os.pathsep}/opt/custom/lib"

    def test_does_not_duplicate_existing_entry(
        self, homebrew_lib_dir, monkeypatch
    ):
        """Should leave the search path alone if it already lists the dir."""
        monkeypatch.setenv(ENV_VAR, homebrew_lib_dir)

        configure_library_path()

        assert os.environ[ENV_VAR] == homebrew_lib_dir

    def test_ignores_directories_without_the_libraries(
        self, tmp_path, monkeypatch
    ):
        """Should skip a Homebrew prefix that has no WeasyPrint libraries."""
        empty_dir = tmp_path / "lib"
        empty_dir.mkdir()
        monkeypatch.setattr(
            weasyprint_libs, "HOMEBREW_LIB_DIRS", (str(empty_dir),)
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv(ENV_VAR, raising=False)

        configure_library_path()

        assert ENV_VAR not in os.environ

    def test_no_op_on_other_platforms(self, homebrew_lib_dir, monkeypatch):
        """Should do nothing off macOS, where dyld is not involved."""
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv(ENV_VAR, raising=False)

        configure_library_path()

        assert ENV_VAR not in os.environ

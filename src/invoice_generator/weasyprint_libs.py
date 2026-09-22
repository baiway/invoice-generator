"""
Locate the system libraries WeasyPrint needs on macOS.

WeasyPrint loads Cairo, Pango, GObject and friends with `dlopen()` when
it is imported. On macOS those libraries are installed by Homebrew into
a prefix that is not on dyld's default search path, so the import fails
with e.g. "cannot load library 'libgobject-2.0-0'" unless
`DYLD_FALLBACK_LIBRARY_PATH` points at the Homebrew lib directory.

Calling `configure_library_path()` before importing WeasyPrint sets that
variable in-process. dyld reads it when the libraries are `dlopen()`ed,
which happens after this runs, so no shell profile or `.env` file is
needed.
"""

import os
import sys
from pathlib import Path

# Homebrew's lib directory: /opt/homebrew on Apple Silicon, /usr/local
# on Intel.
HOMEBREW_LIB_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")

# A library that is present iff the WeasyPrint dependencies are
# installed, used to pick the right Homebrew prefix.
LIBRARY_MARKER = "libgobject-2.0.dylib"

# dyld's built-in fallback search path, which setting
# DYLD_FALLBACK_LIBRARY_PATH would otherwise replace.
DEFAULT_FALLBACK_DIRS = ("~/lib", "/usr/local/lib", "/usr/lib")


def configure_library_path() -> None:
    """Prepend the Homebrew lib directory to `DYLD_FALLBACK_LIBRARY_PATH`.

    Does nothing off macOS, or if no Homebrew directory holding the
    WeasyPrint libraries is found (in which case the user either
    installed them elsewhere or has not run `brew install weasyprint`).
    """
    if sys.platform != "darwin":
        return

    current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if current:
        search_path = current.split(os.pathsep)
    else:
        search_path = [
            str(Path(directory).expanduser())
            for directory in DEFAULT_FALLBACK_DIRS
        ]

    missing = [
        directory for directory in HOMEBREW_LIB_DIRS
        if directory not in search_path
        and (Path(directory) / LIBRARY_MARKER).exists()
    ]
    if missing:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
            missing + search_path
        )

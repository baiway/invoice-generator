"""
Tests for src/invoice_generator/drive_api.py Google Drive API integration.

Drive is replaced by `FakeDrive`, an in-memory tree of folders and files
that answers the same calls, so nothing here touches the network.
"""

import logging
import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from invoice_generator.drive_api import (
    FOLDER,
    DriveFile,
    LessonFolder,
    download_folder,
    drive_service,
    find_lesson_folders,
    safe_filename,
)

DOC = "application/vnd.google-apps.document"


class Request:
    """A request whose `execute()` returns `result`, or raises it if it's
    an exception."""

    def __init__(self, result):
        self.result = result

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeDrive(Resource):
    """Just enough of the Drive API's `files()` for `drive_api`. It is a
    `Resource` for the type checker only, so skips `Resource.__init__`.

    `files` maps each file's ID to a dictionary of its fields, with
    "parent" naming the folder it's in and "content" what downloading it
    gives (or an exception to raise).
    """

    def __init__(self, files, page_size=1000):
        self.files_by_id = files
        self.page_size = page_size
        self.list_calls = []
        self.exports = []

    def files(self):
        return self

    def get(self, fileId, fields, supportsAllDrives):
        return Request({"name": self.files_by_id[fileId]["name"]})

    def list(self, q, fields, orderBy, pageSize, pageToken,
             supportsAllDrives, includeItemsFromAllDrives):
        self.list_calls.append({"q": q, "pageToken": pageToken})
        parent = q.split("'")[1]
        children = sorted(
            ({"id": file_id, **{k: v for k, v in file.items()
                                if k not in ("parent", "content")}}
             for file_id, file in self.files_by_id.items()
             if file["parent"] == parent),
            key=lambda child: child["name"],
        )
        offset = int(pageToken or 0)
        page = {"files": children[offset:offset + self.page_size]}
        if offset + self.page_size < len(children):
            page["nextPageToken"] = str(offset + self.page_size)
        return Request(page)

    def get_media(self, fileId, supportsAllDrives):
        return Request(self.files_by_id[fileId]["content"])

    def export_media(self, fileId, mimeType):
        self.exports.append((fileId, mimeType))
        return Request(self.files_by_id[fileId]["content"])


def folder(name, parent, **fields):
    return {"name": name, "mimeType": FOLDER, "parent": parent,
            "webViewLink": f"https://drive.google.com/drive/folders/{name}",
            **fields}


def file(name, parent, content=b"", mime_type="application/pdf"):
    return {"name": name, "mimeType": mime_type, "parent": parent,
            "content": content}


ANYONE = [{"type": "user"}, {"type": "anyone"}]
PRIVATE = [{"type": "user"}]


class TestDriveService:
    """Tests for drive_service function."""

    def test_builds_the_drive_api_with_the_credentials(self):
        """The service should be Drive v3, signed in with `creds`."""
        creds = MagicMock()
        with patch("invoice_generator.drive_api.build") as mock_build:
            assert drive_service(creds) is mock_build.return_value
        mock_build.assert_called_once_with("drive", "v3", credentials=creds)


class TestFindLessonFolders:
    """Tests for find_lesson_folders function."""

    OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))

    def drive(self, *children, **kwargs):
        return FakeDrive({"maths": folder("Sam Maths", "root"),
                          **dict(children)}, **kwargs)

    def test_finds_dated_folders_in_the_period_in_order(self):
        """Lessons in the period are found, earliest first; those either
        side of it aren't."""
        drive = self.drive(
            ("a", folder("2026-10-13", "maths", permissions=ANYONE)),
            ("b", folder("2026-10-02", "maths", permissions=ANYONE)),
            ("c", folder("2026-09-30", "maths", permissions=ANYONE)),
            ("d", folder("2026-11-01", "maths", permissions=ANYONE)),
            ("e", folder("2026-10-31", "maths", permissions=ANYONE)),
        )

        lessons = find_lesson_folders(drive, "maths", *self.OCTOBER)

        assert [lesson.date for lesson in lessons] == [
            date(2026, 10, 2), date(2026, 10, 13), date(2026, 10, 31)
        ]
        assert lessons[0] == LessonFolder(
            date(2026, 10, 2), "b",
            "https://drive.google.com/drive/folders/2026-10-02",
            "Sam Maths", True,
        )

    def test_ignores_files_and_other_folders(self):
        """Only folders named by a date are lessons."""
        drive = self.drive(
            ("a", folder("Past papers", "maths")),
            ("b", file("2026-10-02", "maths")),
            ("c", folder("2026-10-02 mock", "maths")),
        )

        assert find_lesson_folders(drive, "maths", *self.OCTOBER) == []

    def test_warns_about_impossible_dates(self, caplog):
        """A folder named like a date that isn't one is worth a warning."""
        drive = self.drive(("a", folder("2026-10-32", "maths")))

        with caplog.at_level(logging.WARNING):
            assert find_lesson_folders(drive, "maths", *self.OCTOBER) == []
        assert "'Sam Maths/2026-10-32' looks like a lesson" in caplog.text

    @pytest.mark.parametrize("permissions, shared", [
        (ANYONE, True),
        (PRIVATE, False),
        (None, None),
    ])
    def test_says_whether_anyone_with_the_link_can_open_it(self, permissions, shared):
        """Folders shared with "anyone" are shared; Drive gives no
        permissions to those who can't share, so then it's unknown."""
        fields = {} if permissions is None else {"permissions": permissions}
        drive = self.drive(("a", folder("2026-10-02", "maths", **fields)))

        [lesson] = find_lesson_folders(drive, "maths", *self.OCTOBER)

        assert lesson.shared is shared

    def test_follows_page_tokens(self):
        """Folders with many lessons come back a page at a time."""
        drive = self.drive(
            *((str(day), folder(f"2026-10-{day:02}", "maths")) for day in range(1, 6)),
            page_size=2,
        )

        lessons = find_lesson_folders(drive, "maths", *self.OCTOBER)

        assert len(lessons) == 5
        assert [call["pageToken"] for call in drive.list_calls] == [None, "2", "4"]

    def test_lists_only_what_is_in_the_folder_and_not_binned(self):
        """The query should ask for the folder's children, minus trash."""
        drive = self.drive()

        find_lesson_folders(drive, "maths", *self.OCTOBER)

        assert drive.list_calls[0]["q"] == "'maths' in parents and trashed = false"


class TestDownloadFolder:
    """Tests for download_folder function."""

    def test_downloads_files_and_exports_google_formats(self, tmp_path):
        """Uploaded files are downloaded as they are; Google Docs are
        exported as plain text."""
        drive = FakeDrive({
            "a": file("Integration.pdf", "lesson", b"%PDF"),
            "b": file("README", "lesson", b"Read me", mime_type=DOC),
        })

        files = download_folder(drive, "lesson", tmp_path / "lesson")

        assert files == [
            DriveFile("Integration.pdf", tmp_path / "lesson" / "Integration.pdf"),
            DriveFile("README", tmp_path / "lesson" / "README.txt"),
        ]
        assert (tmp_path / "lesson" / "Integration.pdf").read_bytes() == b"%PDF"
        assert (tmp_path / "lesson" / "README.txt").read_bytes() == b"Read me"
        assert drive.exports == [("b", "text/plain")]

    def test_exports_keep_an_extension_already_there(self, tmp_path):
        """A Doc called "notes.txt" shouldn't become "notes.txt.txt"."""
        drive = FakeDrive({"a": file("notes.txt", "lesson", b"", mime_type=DOC)})

        [downloaded] = download_folder(drive, "lesson", tmp_path)

        assert downloaded.path == tmp_path / "notes.txt"

    def test_downloads_subfolders_under_their_names(self, tmp_path):
        """Files in subfolders are named by their path in the lesson."""
        drive = FakeDrive({
            "a": folder("Extra", "lesson"),
            "b": file("Hard.pdf", "a", b"%PDF"),
            "c": file("Notes.pdf", "lesson", b"%PDF"),
        })

        files = download_folder(drive, "lesson", tmp_path)

        assert files == [
            DriveFile("Notes.pdf", tmp_path / "Notes.pdf"),
            DriveFile("Extra/Hard.pdf", tmp_path / "Extra" / "Hard.pdf"),
        ]

    def test_keeps_names_of_files_with_nothing_to_download(self, tmp_path):
        """Forms and shortcuts can't be downloaded, but their names may
        still say what the lesson covered."""
        drive = FakeDrive({
            "a": file("Quiz on vectors", "lesson",
                      mime_type="application/vnd.google-apps.form"),
        })

        assert download_folder(drive, "lesson", tmp_path) == [
            DriveFile("Quiz on vectors", None)
        ]

    def test_keeps_names_of_files_that_fail_to_download(self, tmp_path, caplog):
        """A failed download is logged, and the rest carry on."""
        error = HttpError(MagicMock(status=403, reason="exportSizeLimitExceeded"),
                          b"{}")
        drive = FakeDrive({
            "a": file("Huge deck", "lesson", error,
                      mime_type="application/vnd.google-apps.presentation"),
            "b": file("Notes.pdf", "lesson", b"%PDF"),
        })

        with caplog.at_level(logging.WARNING):
            files = download_folder(drive, "lesson", tmp_path)

        assert files == [DriveFile("Huge deck", None),
                         DriveFile("Notes.pdf", tmp_path / "Notes.pdf")]
        assert "Could not download 'Huge deck'" in caplog.text


class TestSafeFilename:
    """Tests for safe_filename function."""

    @pytest.mark.parametrize("name, filename", [
        ("Notes.pdf", "Notes.pdf"),
        ("Mechanics / SUVAT.pdf", "Mechanics - SUVAT.pdf"),
        ("../../.ssh/id_rsa", "_..-..-.ssh-id_rsa"),
        (".hidden", "_.hidden"),
        ("", "_"),
    ])
    def test_names_stay_in_the_directory(self, tmp_path, name, filename):
        """Names can't climb out of the directory or hide."""
        assert safe_filename(name, tmp_path) == tmp_path / filename

    def test_names_already_taken_are_numbered(self, tmp_path):
        """Drive allows two files with one name; downloads mustn't clash."""
        (tmp_path / "Notes.pdf").touch()
        (tmp_path / "Notes (2).pdf").touch()

        assert safe_filename("Notes.pdf", tmp_path) == tmp_path / "Notes (3).pdf"

"""
Google Drive API integration.

This module finds the lessons in a student's Drive folders, each a folder
named by its date (e.g. "2026-10-02"), and downloads what's in them.
Signing in is handled by `google_auth`.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)

FOLDER = "application/vnd.google-apps.folder"
# Google's own formats (Docs, Slides, ...) have no file to download, so are
# exported as something that can be read: the MIME type and extension
EXPORTS = {
    "application/vnd.google-apps.document": ("text/plain", ".txt"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}
LESSON_FOLDER_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class LessonFolder:
    """A lesson's folder, in one of a student's folders."""

    date: date
    id: str
    url: str
    # The name of the folder it's in, e.g. "Sam Maths"
    subject: str
    # Whether anyone with the link can open it, or None if Drive won't say
    # (it only tells the people who can share a folder)
    shared: bool | None


@dataclass(frozen=True)
class DriveFile:
    """A file from a lesson's folder."""

    # As in Drive, under any subfolders of the lesson's folder, e.g.
    # "Extra questions/Integration.pdf"
    name: str
    # Where it was downloaded to, or None if it couldn't be
    path: Path | None


def drive_service(creds: Credentials) -> Resource:
    """The Google Drive API, signed in with `creds` from
    `google_auth.authenticate`."""
    return build("drive", "v3", credentials=creds)


# googleapiclient builds the per-API methods (`files()` and friends) onto
# `Resource` at runtime from the discovery document, so no type checker can
# resolve them statically. Hence `cast(Any, service)` below.


def list_folder(service: Resource, folder_id: str, fields: str) -> list[dict[str, Any]]:
    """Everything in a folder (but not its subfolders), by name.

    Args:
        service: Google Drive API, from `drive_service`
        folder_id: The folder's ID
        fields: The fields to fetch for each file, e.g. "id, name"

    Returns:
        The folder's files and folders, as dictionaries of `fields`
    """
    files: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = cast(Any, service).files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields=f"nextPageToken, files({fields})",
            orderBy="name",
            pageSize=1000,
            pageToken=page_token,
            # Folders may be on a shared drive, not just "My Drive"
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def find_lesson_folders(
    service: Resource,
    folder_id: str,
    start: date,
    end: date,
) -> list[LessonFolder]:
    """Find the lessons from `start` to `end` (inclusive) in one of a
    student's folders.

    Args:
        service: Google Drive API, from `drive_service`
        folder_id: The ID of the folder holding a folder per lesson
        start: First day of the period
        end: Last day of the period

    Returns:
        The lessons' folders, in date order
    """
    subject = cast(Any, service).files().get(
        fileId=folder_id, fields="name", supportsAllDrives=True
    ).execute()["name"]

    lessons = []
    children = list_folder(
        service, folder_id, "id, name, mimeType, webViewLink, permissions(type)"
    )
    for child in children:
        name = child["name"]
        if child["mimeType"] != FOLDER or not LESSON_FOLDER_NAME.match(name):
            continue
        try:
            lesson_date = date.fromisoformat(name)
        except ValueError:
            logger.warning(f"'{subject}/{name}' looks like a lesson but isn't a date")
            continue
        if not start <= lesson_date <= end:
            continue

        permissions = child.get("permissions")
        shared = (
            None if permissions is None
            else any(p.get("type") == "anyone" for p in permissions)
        )
        lessons.append(LessonFolder(lesson_date, child["id"], child["webViewLink"],
                                    subject, shared))

    lessons.sort(key=lambda lesson: lesson.date)
    logger.info(f"Found {len(lessons)} lessons in '{subject}'")
    return lessons


def safe_filename(name: str, directory: Path) -> Path:
    """A path in `directory` for a file named `name` in Drive.

    Drive names can contain anything, including "/" and "..", so they're
    made safe to use as a single filename, and kept distinct from files
    already there (Drive allows two files with the same name).
    """
    name = name.replace("/", "-").replace("\\", "-").strip()
    if not name or name.startswith("."):
        name = "_" + name
    path = directory / name
    stem, suffix = path.stem, path.suffix
    n = 2
    while path.exists():
        path = directory / f"{stem} ({n}){suffix}"
        n += 1
    return path


def download_folder(
    service: Resource,
    folder_id: str,
    destination: Path,
    prefix: str = "",
) -> list[DriveFile]:
    """Download everything in a lesson's folder, including its subfolders.

    Google Docs, Slides, Sheets and Drawings are exported (see `EXPORTS`).
    Files that can't be downloaded are logged and kept by name, as names
    are often the best guide to what a lesson covered.

    Args:
        service: Google Drive API, from `drive_service`
        folder_id: The lesson folder's ID
        destination: Directory to download into, created if missing
        prefix: Path of this folder within the lesson's folder, used when
            recursing into subfolders

    Returns:
        Every file in the folder, in name order, subfolders' files after
        the files beside them
    """
    destination.mkdir(parents=True, exist_ok=True)
    files: list[DriveFile] = []
    subfolders = []
    for child in list_folder(service, folder_id, "id, name, mimeType"):
        name, mime_type = child["name"], child["mimeType"]
        if mime_type == FOLDER:
            subfolders.append(child)
            continue

        if mime_type in EXPORTS:
            export_type, extension = EXPORTS[mime_type]
            request = cast(Any, service).files().export_media(
                fileId=child["id"], mimeType=export_type
            )
            filename = name if name.endswith(extension) else name + extension
        elif mime_type.startswith("application/vnd.google-apps."):
            # Forms, shortcuts, sites and the like have nothing to read
            logger.info(f"Not downloading '{prefix}{name}' ({mime_type})")
            files.append(DriveFile(prefix + name, None))
            continue
        else:
            request = cast(Any, service).files().get_media(
                fileId=child["id"], supportsAllDrives=True
            )
            filename = name

        try:
            content = request.execute()
        except HttpError as e:
            logger.warning(f"Could not download '{prefix}{name}': {e.reason}")
            files.append(DriveFile(prefix + name, None))
            continue
        path = safe_filename(filename, destination)
        path.write_bytes(content)
        files.append(DriveFile(prefix + name, path))

    for folder in subfolders:
        files.extend(download_folder(
            service, folder["id"], safe_filename(folder["name"], destination),
            f"{prefix}{folder['name']}/",
        ))
    return files

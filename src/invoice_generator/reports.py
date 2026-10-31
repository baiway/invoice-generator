"""
Lesson reports.

For each student with `reports` set in `students.json`, this module finds
their lessons in Google Drive, summarises each with Apple's on-device model
(see `summariser`), and writes a report as Typst markup, to be edited by
hand. `render_report` then turns it into a PDF styled like the invoices,
using `templates/report.typ`.
"""

import os
import re
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from importlib import resources
from pathlib import Path

import typst
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.progress import Progress

from invoice_generator.constants import (
    REPORT_TEMPLATE,
    STYLE_TEMPLATE,
    TEMPLATE_DIR,
    TEMPLATE_PACKAGE,
)
from invoice_generator.drive_api import LessonFolder, download_folder, find_lesson_folders
from invoice_generator.event_processing import Lesson
from invoice_generator.invoice_generator import covers_whole_month, get_invoice_period
from invoice_generator.lesson_files import prepare
from invoice_generator.logging_config import get_logger
from invoice_generator.models import StudentInfo
from invoice_generator.summariser import LessonMaterials, SummaryFailed, summarise

logger = get_logger(__name__)
console = Console()

# Characters with a meaning in Typst markup, which must be escaped to be
# shown as they are. "/" only matters as the start of a comment.
MARKUP_SPECIAL = re.compile(r"([\\#$*_`@<>\[\]~]|/(?=[/*]))")


class ReportError(Exception):
    """Raised when an edited report can't be rendered, saying where in
    it the problem is."""


@dataclass(frozen=True)
class Entry:
    """A line of a report: one lesson."""

    date: date
    # The lesson's folder, or None if it has none
    url: str | None
    # As Typst markup
    summary: str


@dataclass
class ReportsOutcome:
    """What happened, for the end-of-run summary."""

    written: list[Path] = field(default_factory=list)
    # Reports that already existed, so were left alone
    kept: list[Path] = field(default_factory=list)
    # Things to check before sending the reports, by student
    warnings: list[tuple[str, str]] = field(default_factory=list)


def escape_markup(text: str) -> str:
    """Escape text so Typst shows it as it is, rather than reading it as
    markup (e.g. "$" starting maths, or "*" bold)."""
    return MARKUP_SPECIAL.sub(r"\\\1", text)


def report_filename(student: str) -> str:
    """The report's filename, e.g. "jane-doe-report.typ", like the
    invoices' names."""
    return f"{student.lower()}-report.typ".replace(" ", "-")


def format_entry(entry: Entry) -> str:
    """A report's line for one lesson, as a Typst list item."""
    day = f"{entry.date:%Y-%m-%d}"
    if entry.url:
        url = entry.url.replace("\\", "\\\\").replace('"', '\\"')
        day = f'#link("{url}")[{day}]'
    return f"- {day}: {entry.summary}"


def format_report(
    student: str,
    entries: list[Entry],
    start: datetime,
    end: datetime,
) -> str:
    """A student's report, as Typst markup for `render-reports`.

    Args:
        student: The student's full name
        entries: A line per lesson, in date order
        start: Start of the report period
        end: End of the report period
    """
    first_name = escape_markup(student.split()[0])
    when = "This month" if covers_whole_month(start, end) else "Over this period"
    lines = [
        f"// Lesson report for {student}. Edit it as you like, then run",
        "// `uv run render-reports` to make it into a PDF.",
        "",
        f"= {escape_markup(student)} lesson report for "
        f"{escape_markup(get_invoice_period(start, end))}",
        "",
        f"{when} {first_name} and I have covered:",
        "",
        *(format_entry(entry) for entry in entries),
        "",
        "// Add a paragraph or two here, or delete this line.",
        "",
    ]
    return "\n".join(lines)


def find_lessons(
    drive: Resource,
    student: str,
    info: StudentInfo,
    start: date,
    end: date,
    outcome: ReportsOutcome,
) -> list[LessonFolder]:
    """The student's lessons in the period, from all their folders, noting
    folders that can't be opened in `outcome`."""
    folders = []
    for url, folder_id in zip(info.folders, info.folder_ids, strict=True):
        try:
            folders.extend(find_lesson_folders(drive, folder_id, start, end))
        except HttpError as e:
            logger.warning(f"Could not open {url} for {student}: {e}")
            outcome.warnings.append((student, f"could not open {url} ({e.reason})"))
    return folders


def summarise_lesson(
    drive: Resource,
    folder: LessonFolder,
    directory: Path,
    pool: ThreadPoolExecutor,
) -> Future[str]:
    """Download a lesson's files, then summarise them in the background,
    so the next lesson can download meanwhile."""
    files = download_folder(drive, folder.id, directory / "files")
    materials = prepare(files, directory / "work")
    lesson = LessonMaterials(folder.date, folder.subject, materials, directory)
    return pool.submit(summarise, lesson)


def write_reports(
    lessons: dict[str, list[Lesson]],
    student_data: dict[str, StudentInfo],
    start: datetime,
    end: datetime,
    drive: Resource,
    reports_dir: Path,
) -> ReportsOutcome:
    """Write a report for each student seen in the period with `reports`
    set. A report that already exists is never overwritten, as it may have
    been edited: delete it to write it again.

    The lessons in a report are those with a folder in Drive, and those in
    the calendar without one, which get a "TODO" to fill in. Lessons that
    can't be summarised get a "TODO" too, rather than stopping the rest.

    Args:
        lessons: Each student seen, mapped to their lessons in the calendar
        student_data: Dictionary mapping student names to StudentInfo models
        start: Start of the period
        end: End of the period
        drive: Google Drive API, from `drive_api.drive_service`
        reports_dir: Directory to write reports to, created if missing

    Returns:
        The reports written and kept, and anything to check in them

    Raises:
        ModelUnavailable: If Apple's model stops working altogether
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    outcome = ReportsOutcome()

    # Find every lesson before summarising any, so progress can be shown
    folders: dict[str, list[LessonFolder]] = {}
    for student in sorted(lessons):
        info = student_data[student]
        if not info.reports:
            continue
        path = reports_dir / report_filename(student)
        if path.exists():
            logger.info(f"Keeping {path}, which already exists")
            outcome.kept.append(path)
            continue
        folders[student] = find_lessons(drive, student, info, start.date(),
                                        end.date(), outcome)

    # Each lesson's summary to come, or why there won't be one
    summaries: dict[str, list[tuple[LessonFolder, Future[str] | str]]] = {}
    total = sum(len(student_folders) for student_folders in folders.values())
    with (
        tempfile.TemporaryDirectory(prefix="lesson-reports-") as tmp,
        # One lesson at a time, as there's one model on one Mac
        ThreadPoolExecutor(max_workers=1) as pool,
        Progress(console=console, transient=True) as progress,
    ):
        task = progress.add_task("[cyan]Summarising lessons", total=total)
        try:
            for student, student_folders in folders.items():
                summaries[student] = []
                for number, folder in enumerate(student_folders):
                    directory = Path(tmp) / report_filename(student) / str(number)
                    try:
                        future = summarise_lesson(drive, folder, directory, pool)
                    except HttpError as e:
                        summaries[student].append((folder, f"download failed ({e.reason})"))
                        progress.advance(task)
                        continue
                    future.add_done_callback(lambda _: progress.advance(task))
                    summaries[student].append((folder, future))

            for student, student_summaries in summaries.items():
                entries = []
                for folder, pending in student_summaries:
                    lesson = f"{folder.subject}/{folder.date:%Y-%m-%d}"
                    failure = pending if isinstance(pending, str) else None
                    if isinstance(pending, Future):
                        try:
                            summary = escape_markup(pending.result())
                        except SummaryFailed as e:
                            failure = f"summary failed ({e})"
                    if failure:
                        logger.warning(f"No summary of {lesson}: {failure}")
                        outcome.warnings.append((student, f"{lesson}: {failure}"))
                        summary = "TODO: " + escape_markup(failure)
                    if folder.shared is False:
                        outcome.warnings.append((
                            student, f"{lesson} isn't shared with anyone with "
                            "the link, so its link won't open for others"
                        ))
                    entries.append(Entry(folder.date, folder.url, summary))
                outcome.written.append(write_report(
                    student, entries, lessons[student], start, end, reports_dir,
                    outcome,
                ))
        except BaseException:
            # Don't wait for lessons still queued if summarising has
            # stopped working altogether (or the user pressed Ctrl+C)
            pool.shutdown(cancel_futures=True)
            raise

    console.print("[green]✓[/green] [cyan]Reports written[/cyan]")
    return outcome


def write_report(
    student: str,
    entries: list[Entry],
    calendar_lessons: list[Lesson],
    start: datetime,
    end: datetime,
    reports_dir: Path,
    outcome: ReportsOutcome,
) -> Path:
    """Check a student's lesson folders against their calendar, then
    write their report. Mismatches are noted in `outcome`."""
    folder_dates = {entry.date for entry in entries}
    calendar_dates = {lesson.start.date() for lesson in calendar_lessons}
    for day in sorted(calendar_dates - folder_dates):
        outcome.warnings.append((student, f"no lesson folder for {day:%Y-%m-%d}"))
        entries.append(Entry(day, None, "TODO: no lesson folder found"))
    for day in sorted(folder_dates - calendar_dates):
        outcome.warnings.append((
            student, f"a lesson folder for {day:%Y-%m-%d}, but no lesson in the calendar"
        ))
    entries.sort(key=lambda entry: entry.date)

    path = reports_dir / report_filename(student)
    path.write_text(format_report(student, entries, start, end))
    logger.info(f"Wrote {path}")
    return path


def render_report(path: Path) -> Path:
    """Render an edited report as a PDF beside it, e.g.
    `jane-doe-report.typ` as `jane-doe-report.pdf`.

    The report is included from `templates/report.typ` rather than read
    as a string, so that Typst's errors point to its lines. Typst can only
    include files beside the one it compiles, so both are copied to a
    temporary directory first.

    Raises:
        ReportError: If the report isn't valid Typst, saying where
    """
    output = path.with_suffix(".pdf")
    templates = resources.files(TEMPLATE_PACKAGE) / TEMPLATE_DIR
    with tempfile.TemporaryDirectory(prefix="render-report-") as tmp:
        build = Path(tmp)
        for name in (REPORT_TEMPLATE, STYLE_TEMPLATE):
            (build / name).write_text((templates / name).read_text())
        # In a directory of its own, so it can't clash with the templates
        copy = build / "report" / path.name
        copy.parent.mkdir()
        copy.write_text(path.read_text())
        try:
            typst.compile(build / REPORT_TEMPLATE, output=output,
                          sys_inputs={"report": f"report/{path.name}"})
        except typst.TypstError as e:
            # Point to the report rather than its copy, and leave out
            # Typst's note that it was included from the template
            message = e.diagnostic.split("\nhelp: while including")[0].rstrip()
            # (as Typst shows it: relative, with symlinks such as macOS's
            # /var -> /private/var resolved)
            message = message.replace(os.path.relpath(copy.resolve()), str(path))
            raise ReportError(message) from None
    logger.info(f"Rendered {output}")
    return output


def count_todos(path: Path) -> int:
    """How many lines of a report still have a "TODO", other than
    comments. (Not by cutting lines at "//", which links contain.)"""
    return sum(
        "TODO" in line and not line.lstrip().startswith("//")
        for line in path.read_text().splitlines()
    )

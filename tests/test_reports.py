"""
Tests for src/invoice_generator/reports.py writing lesson reports.

Drive and lesson file preparation are replaced by fakes, and summaries
come from `FakeModel` rather than Apple's model. Reports are compiled with Typst and read back
where it matters how Typst reads them.
"""

import logging
import re
import pytest
import typst
from datetime import UTC, date, datetime
from unittest.mock import MagicMock
from googleapiclient.errors import HttpError
from pypdf import PdfReader

from invoice_generator.drive_api import LessonFolder
from invoice_generator.event_processing import Lesson
from invoice_generator.models import StudentInfo
from invoice_generator.reports import (
    Entry,
    escape_markup,
    format_report,
    report_filename,
    write_reports,
)
from invoice_generator.summariser import ModelUnavailable, SummaryFailed

OCTOBER = (datetime(2026, 10, 1), datetime(2026, 10, 31, 23, 59, 59))
MATHS = "https://drive.google.com/drive/folders/maths"
PHYSICS = "https://drive.google.com/drive/folders/physics"


def text_of(markup, tmp_path):
    """The text Typst shows for `markup`, as a single line."""
    source = tmp_path / "test.typ"
    source.write_text(markup)
    typst.compile(source, output=tmp_path / "test.pdf")
    text = "".join(page.extract_text() for page in PdfReader(tmp_path / "test.pdf").pages)
    return " ".join(text.split())


class FakeModel:
    """Stands in for `summarise`: summarises a lesson as "<subject> on
    <date>", or as `replies` says: a string to reply with, or an exception
    to raise, by date."""

    def __init__(self):
        self.replies = {}
        self.lessons = []

    def __call__(self, lesson):
        self.lessons.append(lesson)
        reply = self.replies.get(lesson.date, f"{lesson.subject} on {lesson.date:%d}")
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def model(monkeypatch):
    """Install `FakeModel`; set `model.replies` to choose replies."""
    fake = FakeModel()
    monkeypatch.setattr("invoice_generator.reports.summarise", fake)
    return fake


def lesson_on(day):
    """A calendar lesson in October 2026."""
    start = datetime(2026, 10, day, 16, tzinfo=UTC)
    return Lesson(start, start.replace(hour=17))


def lesson_folder(day, subject="Maths", shared=True):
    return LessonFolder(date(2026, 10, day), f"{subject}-{day}",
                        f"https://drive.google.com/drive/folders/{subject}-{day}",
                        subject, shared)


@pytest.fixture
def drive(monkeypatch):
    """Fake Drive. `drive.folders` maps each folder's ID to its lessons,
    or to an exception to raise; `drive.failing_downloads` holds IDs of
    lesson folders that fail to download."""
    fake = MagicMock()
    fake.folders = {}
    fake.failing_downloads = set()

    def find(service, folder_id, start, end):
        assert (start, end) == (date(2026, 10, 1), date(2026, 10, 31))
        result = fake.folders[folder_id]
        if isinstance(result, Exception):
            raise result
        return result

    def download(service, folder_id, destination):
        if folder_id in fake.failing_downloads:
            raise HttpError(MagicMock(status=500, reason="Backend Error"), b"{}")
        return []

    monkeypatch.setattr("invoice_generator.reports.find_lesson_folders", find)
    monkeypatch.setattr("invoice_generator.reports.download_folder", download)
    monkeypatch.setattr("invoice_generator.reports.prepare", lambda files, workdir: [])
    return fake


def student(*folders, reports=True):
    return StudentInfo(client_type="private", rate=50, reports=reports,
                       folders=list(folders))


class TestEscapeMarkup:
    """Tests for escape_markup function."""

    @pytest.mark.parametrize("text", [
        "integrated $x^2$ and used #hashtags",
        "a*b*c and snake_case_names",
        "[brackets] <label> @reference ~tilde",
        r"a back\slash",
        "`code` here",
        "speed // velocity, a /* not a comment */ b",
        "ratios like 3/4 and 1/2",
    ])
    def test_text_is_shown_as_it_is(self, text, tmp_path):
        """Characters Typst would read as markup are shown as typed."""
        assert text_of(escape_markup(text), tmp_path) == text

    def test_plain_text_is_unchanged(self):
        assert escape_markup("integration by parts (x e^x)") == "integration by parts (x e^x)"


class TestReportFilename:
    """Tests for report_filename function."""

    def test_named_like_the_invoices(self):
        assert report_filename("Jane Doe") == "jane-doe-report.typ"


class TestFormatReport:
    """Tests for format_report function."""

    ENTRIES = [
        Entry(date(2026, 10, 2), MATHS, "worked through practice questions"),
        Entry(date(2026, 10, 7), None, "TODO: no lesson folder found"),
    ]

    def test_month_report(self):
        """A dated, linked list of lessons under a title like the
        invoices', with room for a note at the end."""
        report = format_report("Sam Smith", self.ENTRIES, *OCTOBER)

        assert report == (
            "// Lesson report for Sam Smith. Edit it as you like, then run\n"
            "// `uv run render-reports` to make it into a PDF.\n"
            "\n"
            "= Sam Smith lesson report for October 2026\n"
            "\n"
            "This month Sam and I have covered:\n"
            "\n"
            f'- #link("{MATHS}")[2026-10-02]: worked through practice questions\n'
            "- 2026-10-07: TODO: no lesson folder found\n"
            "\n"
            "// Add a paragraph or two here, or delete this line.\n"
        )

    def test_other_periods(self):
        """Periods other than a month are given as dates."""
        report = format_report("Sam Smith", self.ENTRIES,
                               datetime(2026, 10, 5), datetime(2026, 10, 20))

        assert "= Sam Smith lesson report for 05/10/2026 to 20/10/2026\n" in report
        assert "Over this period Sam and I have covered:" in report

    def test_reads_as_intended(self, tmp_path):
        """Typst shows the comments as nothing and the rest as text."""
        text = text_of(format_report("Sam Smith", self.ENTRIES, *OCTOBER), tmp_path)

        assert text == (
            "Sam Smith lesson report for October 2026 "
            "This month Sam and I have covered: "
            "• 2026-10-02: worked through practice questions "
            "• 2026-10-07: TODO: no lesson folder found"
        )

    def test_names_are_not_read_as_markup(self, tmp_path):
        text = text_of(format_report("Sam_ #Smith", [], *OCTOBER), tmp_path)

        assert text.startswith("Sam_ #Smith lesson report")
        assert "This month Sam_ and I" in text


class TestWriteReports:
    """Tests for write_reports function."""

    @pytest.fixture(autouse=True)
    def fake_model(self, model):
        self.model = model

    def write(self, tmp_path, lessons, student_data):
        return write_reports(lessons, student_data, *OCTOBER, MagicMock(),
                             tmp_path / "reports")

    def test_writes_a_report_per_student_with_reports(self, tmp_path, drive):
        """Lessons from every folder are summarised and listed in date
        order; students without `reports` get none."""
        drive.folders = {
            "maths": [lesson_folder(2), lesson_folder(13)],
            "physics": [lesson_folder(5, "Physics")],
        }
        self.model.replies = {date(2026, 10, 13): "integrated $x^2$"}

        outcome = self.write(
            tmp_path,
            {"Sam Smith": [lesson_on(2), lesson_on(5), lesson_on(13)],
             "Jo Bloggs": [lesson_on(3)]},
            {"Sam Smith": student(MATHS, PHYSICS),
             "Jo Bloggs": student(reports=False)},
        )

        report = tmp_path / "reports" / "sam-smith-report.typ"
        assert outcome.written == [report]
        assert outcome.warnings == []
        lines = [line for line in report.read_text().splitlines() if line.startswith("- ")]
        assert lines == [
            '- #link("https://drive.google.com/drive/folders/Maths-2")[2026-10-02]: Maths on 02',
            '- #link("https://drive.google.com/drive/folders/Physics-5")[2026-10-05]: Physics on 05',
            '- #link("https://drive.google.com/drive/folders/Maths-13")[2026-10-13]: integrated \\$x^2\\$',
        ]
        assert [lesson.subject for lesson in self.model.lessons] == ["Maths", "Maths", "Physics"]

    def test_checks_lessons_against_the_calendar(self, tmp_path, drive):
        """Lessons without a folder get a TODO; folders without a lesson
        are kept. Both are worth checking."""
        drive.folders = {"maths": [lesson_folder(2), lesson_folder(9)]}

        outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(2), lesson_on(5)]},
                             {"Sam Smith": student(MATHS)})

        report = outcome.written[0].read_text()
        assert "- 2026-10-05: TODO: no lesson folder found\n" in report
        assert "[2026-10-09]: Maths on 09\n" in report
        assert outcome.warnings == [
            ("Sam Smith", "no lesson folder for 2026-10-05"),
            ("Sam Smith", "a lesson folder for 2026-10-09, but no lesson in the calendar"),
        ]

    def test_existing_reports_are_kept(self, tmp_path, drive):
        """A report may have been edited, so is never overwritten."""
        (tmp_path / "reports").mkdir()
        existing = tmp_path / "reports" / "sam-smith-report.typ"
        existing.write_text("edited")
        outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(2)]},
                             {"Sam Smith": student(MATHS)})

        assert outcome.kept == [existing]
        assert outcome.written == []
        assert existing.read_text() == "edited"
        assert self.model.lessons == []

    def test_failed_summaries_become_todos(self, tmp_path, drive, caplog):
        """One lesson failing shouldn't stop the rest."""
        drive.folders = {"maths": [lesson_folder(2), lesson_folder(9)]}
        self.model.replies = {date(2026, 10, 2): SummaryFailed("guardrail [violation]")}

        with caplog.at_level(logging.WARNING):
            outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(2), lesson_on(9)]},
                                 {"Sam Smith": student(MATHS)})

        report = outcome.written[0].read_text()
        assert "[2026-10-02]: TODO: summary failed (guardrail \\[violation\\])\n" in report
        assert "[2026-10-09]: Maths on 09\n" in report
        assert outcome.warnings == [
            ("Sam Smith", "Maths/2026-10-02: summary failed (guardrail [violation])")
        ]
        assert "No summary of Maths/2026-10-02" in caplog.text

    def test_failed_downloads_become_todos(self, tmp_path, drive):
        drive.folders = {"maths": [lesson_folder(2)]}
        drive.failing_downloads = {"Maths-2"}

        outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(2)]},
                             {"Sam Smith": student(MATHS)})

        assert "[2026-10-02]: TODO: download failed (Backend Error)\n" in (
            outcome.written[0].read_text()
        )
        assert outcome.warnings == [
            ("Sam Smith", "Maths/2026-10-02: download failed (Backend Error)")
        ]

    def test_folders_that_cannot_be_opened_are_reported(self, tmp_path, drive):
        """A wrong link or lost access skips that folder, not the report."""
        drive.folders = {
            "maths": HttpError(MagicMock(status=404, reason="File not found"), b"{}"),
            "physics": [lesson_folder(5, "Physics")],
        }

        outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(5)]},
                             {"Sam Smith": student(MATHS, PHYSICS)})

        assert outcome.warnings == [
            ("Sam Smith", f"could not open {MATHS} (File not found)")
        ]
        assert "[2026-10-05]: Physics on 05" in outcome.written[0].read_text()

    def test_unshared_folders_are_reported(self, tmp_path, drive):
        """Links to folders only you can open won't work for parents."""
        drive.folders = {"maths": [lesson_folder(2, shared=False),
                                   lesson_folder(9, shared=None)]}

        outcome = self.write(tmp_path, {"Sam Smith": [lesson_on(2), lesson_on(9)]},
                             {"Sam Smith": student(MATHS)})

        assert outcome.warnings == [(
            "Sam Smith", "Maths/2026-10-02 isn't shared with anyone with the "
            "link, so its link won't open for others",
        )]

    def test_model_failing_altogether_stops_the_reports(self, tmp_path, drive):
        drive.folders = {"maths": [lesson_folder(2), lesson_folder(9)]}
        self.model.replies = {date(2026, 10, 2): ModelUnavailable("terms")}

        with pytest.raises(ModelUnavailable, match="terms"):
            self.write(tmp_path, {"Sam Smith": [lesson_on(2), lesson_on(9)]},
                       {"Sam Smith": student(MATHS)})

    def test_lessons_are_summarised_in_order(self, tmp_path, drive):
        """Lessons download while earlier ones are summarised, and each
        ends up on its own line."""
        drive.folders = {"maths": [lesson_folder(day) for day in range(1, 7)]}

        outcome = self.write(
            tmp_path, {"Sam Smith": [lesson_on(day) for day in range(1, 7)]},
            {"Sam Smith": student(MATHS)},
        )

        dates = re.findall(r"\[(2026-10-\d\d)\]", outcome.written[0].read_text())
        assert dates == [f"2026-10-0{day}" for day in range(1, 7)]
        assert [lesson.date.day for lesson in self.model.lessons] == list(range(1, 7))

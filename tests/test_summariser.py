"""
Tests for src/invoice_generator/summariser.py summarising lessons with
Apple's on-device model.

`fm` is replaced by `FakeFm`, which records each command and replies as the
model might, so the model is never run.
"""

import subprocess
import pytest
import typst
from datetime import date
from PIL import Image

from invoice_generator.lesson_files import Kind, Material
from invoice_generator.summariser import (
    DOCUMENT_QUESTION,
    MAX_IMAGES,
    MAX_PAGES_PER_PDF,
    PAGE_QUESTION,
    CommandFailed,
    LessonMaterials,
    ModelUnavailable,
    SummaryFailed,
    check_model,
    clean_reply,
    file_names,
    first_topics,
    fm,
    plain_name,
    prompt,
    summarise,
)


class FakeFm:
    """Stands in for `subprocess.run`. `reply(command)` gives what `fm`
    prints, or a `(returncode, output)` pair for a failure."""

    def __init__(self):
        self.reply = lambda command: ""
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        reply = self.reply(command)
        if isinstance(reply, tuple):
            returncode, output = reply
            return subprocess.CompletedProcess(command, returncode, "", output)
        return subprocess.CompletedProcess(command, 0, reply, "")

    def option(self, command, name):
        """The value of `--name=...` in a command, or None."""
        prefix = f"--{name}="
        return next((arg.removeprefix(prefix) for arg in command
                     if arg.startswith(prefix)), None)


@pytest.fixture
def model(monkeypatch):
    """Install `FakeFm`; set `model.reply` to choose replies."""
    fake = FakeFm()
    monkeypatch.setattr("invoice_generator.summariser.subprocess.run", fake)
    return fake


def lesson(directory, *materials):
    return LessonMaterials(date(2026, 10, 14), "Sam Maths", list(materials), directory)


def image(directory, name="Photo.png"):
    path = directory / name
    Image.new("RGB", (100, 100), "white").save(path)
    return path


def pdf(directory, pages, name="Notes.pdf"):
    source = directory / "notes.typ"
    source.write_text("#pagebreak()\n".join(["Vectors\n"] * pages))
    typst.compile(source, output=directory / name)
    return directory / name


class TestPrompt:
    """Tests for prompt function."""

    def test_prompts_ship_with_the_package(self):
        assert "Ignore headers, footers" in prompt("page-notes.md")
        assert prompt("lesson-topics.md").startswith("You are given notes")

    def test_trailing_newlines_are_left_out(self):
        assert not prompt("page-notes.md").endswith("\n")


class TestCleanReply:
    """Tests for clean_reply function."""

    @pytest.mark.parametrize("reply, cleaned", [
        ("integration by substitution", "integration by substitution"),
        ("integration by substitution.\n", "integration by substitution"),
        ("\n\n- integration by substitution\nmore", "integration by substitution"),
        ('"integration by substitution."', "integration by substitution"),
        ("“integration by substitution”", "integration by substitution"),
        ("* vectors", "vectors"),
        ("Sam's \"error log\"", "Sam's \"error log\""),
    ])
    def test_takes_the_first_line_without_decoration(self, reply, cleaned):
        assert clean_reply(reply) == cleaned

    @pytest.mark.parametrize("reply", ["", "\n  \n", '""', "."])
    def test_empty_replies_fail(self, reply):
        with pytest.raises(SummaryFailed, match="empty"):
            clean_reply(reply)


class TestFm:
    """Tests for fm function and the commands it runs."""

    def test_values_are_attached_and_the_question_follows_dashes(self, model, tmp_path):
        """Values starting with "-", like a bulleted list, would otherwise
        be read as options."""
        model.reply = lambda command: "apples\n"

        reply = fm("- one word", "- what is first?", text="- apples\n- pears",
                   image=tmp_path / "a.png")

        assert reply == "apples\n"
        assert model.commands == [[
            "fm", "respond", "--no-stream", "--greedy",
            "--guardrails", "permissive-content-transformations",
            "--instructions=- one word",
            f"--image={tmp_path / 'a.png'}",
            "--text=- apples\n- pears",
            "--", "- what is first?",
        ]]

    def test_failures_raise_with_the_end_of_the_output(self, model):
        model.reply = lambda command: (1, "x" * 1000 + "context window exceeded")

        with pytest.raises(CommandFailed, match="context window exceeded$") as exc_info:
            fm("instructions", "question")
        assert exc_info.value.returncode == 1
        assert len(str(exc_info.value)) < 600

    def test_terms_not_agreed_means_the_model_is_unavailable(self, model):
        """`fm` refuses to run, with status 69, until its terms are agreed."""
        model.reply = lambda command: (69, "YOU HAVE NOT AGREED")

        with pytest.raises(ModelUnavailable, match="sudo fm license"):
            fm("instructions", "question")

    def test_missing_fm_means_the_model_is_unavailable(self, monkeypatch):
        def missing(command, **kwargs):
            raise FileNotFoundError(command[0])
        monkeypatch.setattr("invoice_generator.summariser.subprocess.run", missing)

        with pytest.raises(ModelUnavailable, match="`fm` is not installed"):
            fm("instructions", "question")

    def test_slow_replies_fail_the_lesson(self, monkeypatch):
        def slow(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        monkeypatch.setattr("invoice_generator.summariser.subprocess.run", slow)

        with pytest.raises(SummaryFailed, match="took more than 120s"):
            fm("instructions", "question")


class TestCheckModel:
    """Tests for check_model function."""

    @pytest.fixture
    def installed(self, monkeypatch):
        monkeypatch.setattr("invoice_generator.summariser.shutil.which",
                            lambda name: f"/usr/bin/{name}")

    def test_passes_when_the_model_is_available(self, model, installed):
        check_model()

        assert model.commands == [["fm", "available"]]

    def test_needs_fm(self, monkeypatch):
        monkeypatch.setattr("invoice_generator.summariser.shutil.which", lambda name: None)

        with pytest.raises(ModelUnavailable, match="need macOS 27"):
            check_model()

    def test_says_to_agree_to_the_terms(self, model, installed):
        model.reply = lambda command: (69, "YOU HAVE NOT AGREED")

        with pytest.raises(ModelUnavailable, match="sudo fm license"):
            check_model()

    def test_passes_on_why_the_model_is_unavailable(self, model, installed):
        model.reply = lambda command: (1, "Apple Intelligence is turned off")

        with pytest.raises(ModelUnavailable, match="Apple Intelligence is turned off"):
            check_model()


class TestFileNames:
    """Tests for plain_name and file_names functions."""

    @pytest.mark.parametrize("name, plain", [
        ("maths-questions-from-error-log.pdf", "maths questions from error log"),
        ("Physics IA_", "Physics IA"),
        ("Print _ RevisionHub.pdf", "Print RevisionHub"),
        ("L5 Energy Levels and Spectra.pptx", "L5 Energy Levels and Spectra"),
        ("Extra/Notes.pdf", "Extra/Notes"),
    ])
    def test_plain_names(self, name, plain):
        assert plain_name(name) == plain

    def test_names_another_name_starts_with_are_left_out(self):
        """No need for "questions" beside "questions worked solutions"."""
        materials = [
            Material("mock-exam-questions-worked-solutions.pdf", Kind.PDF, None),
            Material("mock-exam-questions.pdf", Kind.PDF, None),
            Material("README", Kind.OTHER, None),
        ]

        assert file_names(materials) == "mock exam questions worked solutions, README"


class TestFirstTopics:
    """Tests for first_topics function."""

    @pytest.mark.parametrize("topics, first", [
        ("a, b, c, d", "a, b, c"),
        ("a, b", "a, b"),
        ("a mix of topics, including a, b, c, d", "a mix of topics, including a, b, c"),
        ("a, , b", "a, b"),
    ])
    def test_keeps_at_most_three(self, topics, first):
        assert first_topics(topics) == first


class TestSummarise:
    """Tests for summarise function."""

    def test_notes_each_page_then_names_the_topics(self, tmp_path, model):
        """Pages, images and documents are noted on their own, without
        their names; the summary is the file names, then the topics the
        notes add up to."""
        (tmp_path / "README.txt").write_text("- Practise these: " + "x" * 5000)
        materials = [
            Material("vectors-homework.pdf", Kind.PDF, pdf(tmp_path, pages=2)),
            Material("Photo.png", Kind.IMAGE, image(tmp_path)),
            Material("README", Kind.TEXT, tmp_path / "README.txt"),
            Material("Quiz", Kind.OTHER, None),
        ]
        questions = []

        def reply(command):
            question = command[-1]
            questions.append(question)
            if question.startswith("- "):
                return "dot product, cross product, lines, planes.\n"
            return "unclear" if len(questions) == 2 else "dot product"
        model.reply = reply

        summary = summarise(lesson(tmp_path, *materials))

        assert summary == "vectors homework, Photo, README, Quiz: dot product, cross product, lines"
        *notes, topics = model.commands
        assert [model.option(c, "instructions") for c in notes] == [prompt("page-notes.md")] * 4
        assert questions[:4] == [PAGE_QUESTION] * 3 + [DOCUMENT_QUESTION]
        # No note mentions a file's name
        assert not any("vectors" in arg for c in notes for arg in c)
        # Documents are cut short to fit the context window
        assert len(model.option(notes[-1], "text")) == 3000
        # The topics come from the notes, less the page that was unclear
        assert model.option(topics, "instructions") == prompt("lesson-topics.md")
        assert topics[-1] == (
            "- vectors-homework.pdf, page 1: dot product\n"
            "- Photo.png: dot product\n"
            "- README: dot product"
        )

    def test_reads_a_limited_number_of_pages(self, tmp_path, model):
        """Long PDFs and many photos are cut down, keeping each prompt
        within the context window."""
        model.reply = lambda command: "vectors"
        materials = [
            Material("Long.pdf", Kind.PDF, pdf(tmp_path, pages=6, name="Long.pdf")),
            *(Material(f"Photo {n}.png", Kind.IMAGE, image(tmp_path, f"{n}.png"))
              for n in range(6)),
        ]

        summarise(lesson(tmp_path, *materials))

        images = [model.option(c, "image") for c in model.commands
                  if model.option(c, "image")]
        assert len(images) == MAX_IMAGES
        assert sum("Long page" in image for image in images) == MAX_PAGES_PER_PDF

    def test_lessons_with_nothing_to_read_go_by_their_names(self, tmp_path, model):
        summary = summarise(lesson(tmp_path, Material("Quiz on vectors", Kind.OTHER, None)))

        assert summary == "Quiz on vectors"
        assert model.commands == []

    def test_failed_notes_are_skipped(self, tmp_path, model):
        """An image too big for the context window, say, shouldn't stop
        the summary."""
        model.reply = lambda command: (1, "Exceeded model context window size")

        summary = summarise(lesson(tmp_path, Material("Photo.png", Kind.IMAGE, image(tmp_path))))

        assert summary == "Photo"

    def test_failed_topics_leave_the_names(self, tmp_path, model):
        def reply(command):
            if model.option(command, "instructions") == prompt("lesson-topics.md"):
                return (1, "guardrail violation")
            return "vectors"
        model.reply = reply

        summary = summarise(lesson(tmp_path, Material("Photo.png", Kind.IMAGE, image(tmp_path))))

        assert summary == "Photo"

    def test_empty_folders_fail(self, tmp_path, model):
        with pytest.raises(SummaryFailed, match="empty"):
            summarise(lesson(tmp_path))

    def test_terms_not_agreed_stops_everything(self, tmp_path, model):
        model.reply = lambda command: (69, "YOU HAVE NOT AGREED")

        with pytest.raises(ModelUnavailable, match="sudo fm license"):
            summarise(lesson(tmp_path, Material("Photo.png", Kind.IMAGE, image(tmp_path))))

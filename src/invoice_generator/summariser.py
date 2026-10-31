"""
Summarising what a lesson covered, with Apple's on-device model.

Summaries are written by the language model built into macOS, through the
`fm` command that comes with macOS 27. It runs entirely on the Mac: lesson
files, which are students' work, are never sent anywhere.

The model is small, with a context window of 4,096 tokens shared by the
prompt and the reply, and follows short prompts far better than long
ones. So a lesson is summarised in steps, each a prompt of its own:

1. Each page image and document is noted on its own, following
   `prompts/page-notes.md`. The prompt leaves out the file's name, which
   the model would otherwise just repeat.
2. The notes are boiled down to at most `MAX_TOPICS` topics, following
   `prompts/lesson-topics.md`.
3. The summary is the lesson's file names, tidied, then those topics. File
   names are chosen by the tutor and are the best guide to what a lesson
   was for; asked to reword them, the model loses the words that matter.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

from invoice_generator.constants import (
    LESSON_TOPICS_PROMPT,
    PAGE_NOTES_PROMPT,
    PROMPTS_DIR,
    TEMPLATE_PACKAGE,
)
from invoice_generator.lesson_files import Kind, Material, pdf_pages
from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)

# Limits on what's read, to keep each prompt within the context window and
# a lesson's summary to a few seconds
MAX_PAGES_PER_PDF = 4
MAX_IMAGES = 8
IMAGE_EDGE = 1024
TEXT_CHARACTERS = 3000
MAX_TOPICS = 3
TIMEOUT = 120

PAGE_QUESTION = "What maths or physics does this page teach or practise?"
DOCUMENT_QUESTION = (
    "What kind of document is this (e.g. notes, questions, a report), and "
    "what maths or physics is it about?"
)
MIX = "a mix of topics, including "

# `fm` exits with this until its terms have been agreed to
TERMS_NOT_AGREED = 69
AGREE_TO_TERMS = ("agree to the Apple Foundation Models terms first, by "
                  "running `sudo fm license`")


class ModelUnavailable(Exception):
    """Raised when Apple's model can't be used at all, e.g. `fm` isn't
    installed or its terms haven't been agreed to."""


class SummaryFailed(Exception):
    """Raised when one lesson couldn't be summarised."""


class CommandFailed(SummaryFailed):
    """Raised when `fm` exits with an error."""

    def __init__(self, returncode: int, output: str) -> None:
        super().__init__(f"`fm` failed ({returncode}): {output}")
        self.returncode = returncode


@dataclass(frozen=True)
class LessonMaterials:
    """Everything there is to summarise about one lesson."""

    date: date
    # The name of the folder the lesson's folder is in, e.g. "Sam Maths"
    subject: str
    materials: list[Material]
    # A directory holding every file in `materials`, which may also be
    # written to
    directory: Path


def prompt(name: str) -> str:
    """One of the prompts in `prompts/`."""
    return (resources.files(TEMPLATE_PACKAGE) / PROMPTS_DIR / name).read_text().strip()


def clean_reply(text: str) -> str:
    """The model's reply without list markers, quotation marks or a full
    stop that slipped in, from its first line.

    Raises:
        SummaryFailed: If the reply is empty
    """
    for line in text.splitlines():
        line = line.strip().removeprefix("- ").removeprefix("* ").strip()
        if len(line) > 1 and line[0] == line[-1] and line[0] in "\"'“”":
            line = line[1:-1]
        line = line.strip("“”").rstrip(".").strip()
        if line:
            return line
    raise SummaryFailed("the model's reply was empty")


def fm(instructions: str, question: str, *, image: Path | None = None,
       text: str | None = None) -> str:
    """Prompt Apple's model with `fm respond`, returning its reply.

    Values are attached to their options (`--text=...`), and the question
    follows `--`, as `fm` would otherwise read any value starting with "-",
    like a bulleted list, as an option.

    Raises:
        ModelUnavailable: If `fm` isn't installed or its terms haven't
            been agreed to
        CommandFailed: If `fm` fails, e.g. the prompt is too long
        SummaryFailed: If it takes longer than `TIMEOUT` seconds
    """
    command = [
        "fm", "respond", "--no-stream", "--greedy",
        # For transforming content the user supplies, as here, rather than
        # generating it
        "--guardrails", "permissive-content-transformations",
        f"--instructions={instructions}",
    ]
    if image is not None:
        command.append(f"--image={image}")
    if text is not None:
        command.append(f"--text={text}")
    command += ["--", question]
    return run(command)


def run(command: list[str]) -> str:
    """Run an `fm` command and return what it printed.

    Raises:
        ModelUnavailable: If `fm` isn't installed or its terms haven't
            been agreed to
        CommandFailed: If it exits with an error
        SummaryFailed: If it takes longer than `TIMEOUT` seconds
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=TIMEOUT)
    except FileNotFoundError:
        raise ModelUnavailable("`fm` is not installed") from None
    except subprocess.TimeoutExpired:
        raise SummaryFailed(f"`fm` took more than {TIMEOUT}s") from None
    if result.returncode == TERMS_NOT_AGREED:
        raise ModelUnavailable(AGREE_TO_TERMS)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise CommandFailed(result.returncode, output[-500:])
    return result.stdout


def check_model() -> None:
    """Check Apple's model can be used, before any lesson is downloaded.

    Raises:
        ModelUnavailable: Saying what to do about it
    """
    if shutil.which("fm") is None:
        raise ModelUnavailable(
            "`fm` was not found: lesson reports need macOS 27 or later, on "
            "a Mac with Apple Intelligence"
        )
    try:
        run(["fm", "available"])
    except CommandFailed as e:
        raise ModelUnavailable(f"Apple's model is unavailable: {e}") from None


def note(label: str, question: str, *, image: Path | None = None,
         text: str | None = None) -> str | None:
    """The model's note on one page image or document, or None if it
    couldn't tell or failed (e.g. the image didn't fit)."""
    try:
        reply = clean_reply(fm(prompt(PAGE_NOTES_PROMPT), question,
                               image=image, text=text))
    except SummaryFailed as e:
        logger.info(f"No note on '{label}': {e}")
        return None
    return None if reply.casefold() == "unclear" else reply


def take_notes(lesson: LessonMaterials) -> list[str]:
    """Notes on what each page image and document of a lesson shows, as
    "- <file>, page <n>: <note>" lines."""
    notes = []
    images = 0
    for number, material in enumerate(lesson.materials):
        if material.path is None:
            continue
        if material.kind is Kind.TEXT:
            text = material.path.read_text(errors="replace")[:TEXT_CHARACTERS]
            reply = note(material.name, DOCUMENT_QUESTION, text=text)
            if reply:
                notes.append(f"- {material.name}: {reply}")
            continue

        room = MAX_IMAGES - images
        if room == 0:
            continue
        if material.kind is Kind.PDF:
            pages_dir = lesson.directory / "pages" / str(number)
            pages_dir.mkdir(parents=True, exist_ok=True)
            pages = pdf_pages(material.path, pages_dir,
                              min(MAX_PAGES_PER_PDF, room), IMAGE_EDGE)
            labels = [f"{material.name}, page {n}" for n in range(1, len(pages) + 1)]
        else:
            pages, labels = [material.path], [material.name]
        for image, label in zip(pages, labels, strict=True):
            images += 1
            reply = note(label, PAGE_QUESTION, image=image)
            if reply:
                notes.append(f"- {label}: {reply}")
    return notes


def plain_name(name: str) -> str:
    """A file name without its extension, dashes or underscores, e.g.
    "maths questions from error log" for "maths-questions-from-error-log.pdf"."""
    name = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    return " ".join(re.sub(r"[-_]+", " ", name).split())


def file_names(materials: list[Material]) -> str:
    """The lesson's file names, tidied, leaving out any that the start of
    another repeats (e.g. "questions" beside "questions worked solutions")."""
    names = [plain_name(material.name) for material in materials]
    return ", ".join(
        name for name in names
        if not any(other != name and other.casefold().startswith(name.casefold())
                   for other in names)
    )


def first_topics(text: str) -> str:
    """The first `MAX_TOPICS` of a comma-separated list of topics, which
    the model doesn't reliably stop at itself."""
    mix = text.startswith(MIX)
    topics = [topic.strip() for topic in text.removeprefix(MIX).split(",")
              if topic.strip()]
    return (MIX if mix else "") + ", ".join(topics[:MAX_TOPICS])


def summarise(lesson: LessonMaterials) -> str:
    """Summarise what a lesson covered in one line, e.g. "calculus1
    revision homework: related rates, integration, solving differential
    equations".

    Raises:
        SummaryFailed: If this lesson couldn't be summarised
        ModelUnavailable: If Apple's model stops working altogether, so
            there's no point trying other lessons
    """
    names = file_names(lesson.materials)
    if not names:
        raise SummaryFailed("the lesson's folder is empty")

    notes = take_notes(lesson)
    if not notes:
        return names
    try:
        topics = clean_reply(fm(prompt(LESSON_TOPICS_PROMPT), "\n".join(notes)))
    except SummaryFailed as e:
        # The file names alone still say something
        logger.info(f"No topics for {lesson.subject}/{lesson.date}: {e}")
        return names
    return f"{names}: {first_topics(topics)}"

# Invoice Generator

Generates PDF invoices from Google Calendar events by matching attendee email addresses with details specified in `students.json`.

## Requirements
- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip` for dependency management
- Google Calendar API credentials (instructions below)
- A consistent naming scheme for your Google Calendar events (e.g. "Tutoring Joe Bloggs")

### Setting up Google Calendar API credentials
1. Visit the [Google Developers Console](https://console.developers.google.com/) and create a new project.
2. Enable the Google Calendar API for your project.
3. In the "Credentials" section, create a new OAuth client ID. If prompted, configure the OAuth consent screen with the necessary details.
4. Set the application type to "Desktop app" and name your client.
5. Download the JSON file containing your credentials, rename it `credentials.json`.

For detailed steps, refer to the [official Google Calendar API documentation](https://developers.google.com/calendar/quickstart/python).

### Installation

#### Using uv (Recommended)

**1. Install uv:**
```shell
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

**2. Clone the project:**
```shell
git clone https://github.com/baiway/invoice-generator.git
cd invoice-generator
```

**3. (macOS only) Install WeasyPrint system libraries via Homebrew:**

WeasyPrint requires several system libraries (Cairo, Pango, etc.) that are not bundled with the Python package.

```shell
brew install weasyprint
```

No further setup is needed: `src/invoice_generator/weasyprint_libs.py` adds the Homebrew lib directory to `DYLD_FALLBACK_LIBRARY_PATH` in-process before WeasyPrint is imported, so there is nothing to export in your shell profile.

**4. Install dependencies:**
```shell
uv sync
```

This creates a virtual environment and installs all dependencies including dev dependencies (pytest, mypy, etc.).

#### Using pip

If you prefer pip:

```shell
python -m venv .venv
source .venv/bin/activate
pip install -e . --group dev
```

The `--group` flag needs pip 25.1 or newer; development dependencies are
declared in `[dependency-groups]` (PEP 735) rather than as an extra. For
runtime dependencies only, `pip install -e .` is enough.

### Setup
**1. Configure student data:** Create a directory called `data` in the root directory of the project
```shell
mkdir data
```

**2. Move `credentials.json` into the `data` directory**
```shell
mv ~/Downloads/credentials.json ./data
```

**3. Create three files in the `data` directory:** `students.json`, `bank_details.json`, and `contact_details.json`. Examples of each are shown below.

`students.json`:
```json
{
  "Alice": {
    "client_type": "private",
    "rate": 50,
    "emails": [
      "alice3240@hotmail.co.uk",
      "04alice@school.com"
    ]
  },
  "Bob": {
    "client_type": "tutors4u",
    "rate": 40,
    "emails": [
      "bob9001@icloud.com"
    ]
  }
}
```

`bank_details.json`: Both the sort code and account number accept flexible input formats:
- Sort code: `"12-34-56"` or `"123456"` (dashes optional)
- Account number: `"1234 5678"` or `"12345678"` (spaces optional)

```json
{
  "name": "Joe Bloggs",
  "sort_code": "12-34-56",
  "account_number": "1234 5678",
  "bank": "Monzo Bank"
}
```

`contact_details.json`: Replace the country code, phone number and email address with your details. The phone number can include spaces or other formatting characters (they'll be normalised automatically).
```json
{
  "country_code": "+44",
  "phone_number": "1234 567890",
  "email": "joethetutor@gmail.com"
}
```

## Usage

Installing the project puts a `generate-invoices` command inside the project's
virtual environment — not on your PATH. There are two ways to reach it.

Run it through uv, which needs no activation and works from anywhere in the
repository:

```shell
uv run generate-invoices
```

Or activate the environment once per shell, after which the bare command works:

```shell
source .venv/bin/activate       # Windows: .venv\Scripts\activate
generate-invoices
```

The examples below assume an activated environment; prefix them with `uv run`
otherwise. Running `python generate-invoices.py` from the repository root is
equivalent to `generate-invoices`, and needs the same environment — it imports
the installed package, so it fails with `ModuleNotFoundError` from a shell where
the environment is neither activated nor supplied by `uv run`.

### Basic Usage

Generate invoices for the last full month:
```shell
generate-invoices
```

### Advanced Options

```shell
# Generate for specific students only
generate-invoices --only "Alice" "Bob"

# Custom date range
generate-invoices --from 2024-01-01 --to 2024-01-31

# Custom start date (end defaults to today)
generate-invoices --from 2024-01-01

# Read configuration from somewhere else, write invoices somewhere else
generate-invoices --data-dir ~/tutoring/data --output-dir ~/tutoring/invoices
```

Paths are resolved against the directory you run the command from, so
`generate-invoices` run in `~/tutoring` reads `~/tutoring/data/students.json`
and writes to `~/tutoring/invoices/` unless told otherwise. The detailed log
(`invoice-generator.log`) is likewise written to the current directory.

For all options:
```shell
generate-invoices --help
```

### Output

Invoices are saved as PDFs in the `invoices/` directory:
- Private clients: `alice-invoice.pdf`
- Agency clients: Combined into `agency-name-invoice.pdf`

## Development

### Running Tests

The project has a comprehensive test suite with **195 tests** achieving **100% code coverage**.

The tests import the installed `invoice_generator` package rather than the
source directory, so the project itself must be installed first — `uv sync`
and `pip install -e . --group dev` both do this.

As with `generate-invoices`, the development tools below live in the project's
virtual environment: activate it first, or prefix each command with `uv run`
(`uv run pytest`, `uv run mypy src/ generate-invoices.py`, `uv run ruff check`).

Coverage is not collected by default; pass `--cov` when you want it.

```shell
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# With coverage report (terminal)
pytest --cov --cov-report=term-missing

# With coverage report (HTML)
pytest --cov --cov-report=html
# Then open htmlcov/index.html in your browser

# Run specific test file
pytest tests/test_models.py

# Run specific test class
pytest tests/test_models.py::TestStudentInfo

# Run specific test
pytest tests/test_models.py::TestStudentInfo::test_valid_student_info
```

### Linting

```shell
ruff check
```

Ruff is configured for linting only — there is no formatter and no
import-order rule, so it reports likely mistakes rather than style
preferences. See `[tool.ruff.lint]` in `pyproject.toml` for the rule set.

### Type Checking

```shell
mypy src/ generate-invoices.py
```

### Continuous Integration

`.github/workflows/ci.yml` runs the lint, type check and test suite on
every push to `main` and every pull request, against the oldest and
newest supported Python versions.

### Project Structure

```
invoice-generator/
├── pyproject.toml            # Project configuration with uv support
├── uv.lock                   # Exact versions of every dependency
├── generate-invoices.py      # Wrapper for the installed CLI
├── .github/workflows/ci.yml  # Lint, type check and tests on 3.11 and 3.14
├── src/
│   └── invoice_generator/    # The package itself
│       ├── cli.py                # Command line interface and entry point
│       ├── calendar_api.py       # Google Calendar API integration
│       ├── event_processing.py   # Event classification and processing
│       ├── invoice_generator.py  # PDF generation with WeasyPrint
│       ├── data_loader.py        # JSON loading with Pydantic validation
│       ├── models.py             # Pydantic models with validators and properties
│       ├── constants.py          # Configuration constants
│       ├── logging_config.py     # Logging setup (file + console handlers)
│       ├── utils.py              # Date utilities
│       ├── formatting.py         # Display formatting (dates, times, currency)
│       ├── weasyprint_libs.py    # macOS library path setup for WeasyPrint
│       ├── py.typed              # PEP 561 marker: the package ships types
│       └── templates/            # Invoice template, shipped with the package
│           ├── invoice-template.html
│           └── styles.css
├── tests/                    # Test suite
│   ├── conftest.py           # Pytest fixtures and test data
│   ├── test_calendar_api.py  # Google Calendar API tests (mocked)
│   ├── test_cli.py           # CLI parsing and validation tests
│   ├── test_data_loader.py   # JSON loading and validation tests
│   ├── test_event_processing.py  # Event classification tests
│   ├── test_formatting.py    # Formatting function tests
│   ├── test_invoice_generator.py # PDF generation tests
│   ├── test_logging_config.py    # Logging configuration tests
│   ├── test_models.py        # Pydantic model validation tests
│   ├── test_utils.py         # Date utility tests
│   └── test_weasyprint_libs.py  # Library path configuration tests
├── data/                     # Configuration files (git-ignored)
│   ├── students.json
│   ├── bank_details.json
│   ├── contact_details.json
│   ├── credentials.json
│   └── token.json
└── invoices/                 # Generated PDFs (git-ignored)
```

## Troubleshooting

### WeasyPrint installation issues (macOS)

If you see `cannot load library 'libgobject-2.0-0'`, the Homebrew libraries are missing or are installed somewhere `src/invoice_generator/weasyprint_libs.py` does not look (it checks `/opt/homebrew/lib` and `/usr/local/lib`). Run `brew install weasyprint`, then check where it put them:

```shell
ls "$(brew --prefix)/lib/libgobject-2.0.dylib"
```

If that path is outside both directories, point Python at it yourself before running the generator:

```shell
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib:$DYLD_FALLBACK_LIBRARY_PATH"
```

If you still see library errors, refer to the official WeasyPrint docs:
- [Installation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
- [Troubleshooting](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting)

### Pydantic Validation Errors

If you see "Validation failed" errors, check that your JSON files match the expected format:
- `students.json`: Each student needs `client_type`, `rate`, and `emails` (array of email addresses, can be empty)
- `bank_details.json`: Sort code must be 6 digits (dashes optional). Account number must be 8 digits (spaces optional).
- `contact_details.json`: Must have valid `country_code` (e.g., "+44"), `phone_number` (10+ digits, formatting optional), and `email` fields
- Email addresses must be in valid format

### Google Calendar Authentication

On first run, a browser window will open for Google OAuth. After authentication, a `token.json` file is created for future runs.

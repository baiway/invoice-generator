# Invoice Generator

Generates PDF invoices from Google Calendar events by matching attendee email addresses with details specified in `students.json`.

## Requirements
- Python >= 3.11
- [uv](https://github.com/astral-sh/uv)
- [Homebrew](https://brew.sh) and WeasyPrint's system libraries (`brew install weasyprint`); see [WeasyPrint's installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) for other platforms
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
```shell
git clone https://github.com/baiway/invoice-generator.git
cd invoice-generator
brew install weasyprint
uv sync
```

### Setup
**1. Create a `data` directory** in the root directory of the project and move `credentials.json` into it:
```shell
mkdir data
mv ~/Downloads/credentials.json ./data
```

**2. Create three files in the `data` directory:** `students.json`, `bank_details.json`, and `contact_details.json`. Examples of each are shown below.

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

Generate invoices for the last full month:
```shell
uv run generate-invoices
```

Some other options:
```shell
# Generate for specific students only
uv run generate-invoices --only "Alice" "Bob"

# Custom date range
uv run generate-invoices --from 2024-01-01 --to 2024-01-31

# All options
uv run generate-invoices --help
```

### Output

Invoices are saved as PDFs in the `invoices/` directory:
- Private clients: `alice-invoice.pdf`
- Agency clients: Combined into `agency-name-invoice.pdf`

## Development

```shell
uv run pytest      # tests; add `--cov` for a coverage report
uv run ruff check  # lint
uv run mypy src/   # type check
```

`.github/workflows/ci.yml` runs all three on every push to `main` and every pull request, against the oldest and newest supported Python versions.

### Project Structure

```
invoice-generator/
├── pyproject.toml            # Project configuration
├── uv.lock                   # Exact versions of every dependency
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
├── tests/                    # Test suite, one `test_<module>.py` per module
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

If you still see library errors, refer to [WeasyPrint's troubleshooting docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting).

### Pydantic Validation Errors

If you see a `ValidationError`, check that your JSON files match the expected format:
- `students.json`: Each student needs `client_type`, `rate`, and `emails` (array of email addresses, can be empty)
- `bank_details.json`: Sort code must be 6 digits (dashes optional). Account number must be 8 digits (spaces optional).
- `contact_details.json`: Must have valid `country_code` (e.g., "+44"), `phone_number` (10+ digits, formatting optional), and `email` fields
- Email addresses must be in valid format

### Google Calendar Authentication

On first run, a browser window will open for Google OAuth. After authentication, a `token.json` file is created for future runs.

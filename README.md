# Invoice Generator

Generates PDF invoices from Google Calendar events by matching attendee email addresses with details specified in `students.json`.

## Features

- Automated invoice generation from Google Calendar
- Support for multiple client types (private clients, agencies)
- Pydantic validation for configuration files
- Type-safe Python codebase with mypy compliance
- Comprehensive test suite
- Structured logging and error handling

## Requirements

- Python 3.9 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip for dependency management
- Google Calendar API credentials (instructions below)
- A consistent naming scheme for your Google Calendar events (e.g., "Tutoring Joe Bloggs")

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

**3. Install dependencies:**
```shell
uv sync
```

This creates a virtual environment and installs all dependencies including dev dependencies (pytest, mypy, etc.).

#### Using pip

If you prefer pip:

```shell
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

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
          "emails:" [
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
      },
  }
```

`bank_details.json`: You can get a payment link from the Monzo app. For the QR code link, just replace `joebloggs` with your Monzo username.
```json
{
  "name": "Joe Bloggs",
  "sort_code": "04-00-04",
  "account_number": "8093 4419",
  "bank": "Monzo Bank",
  "link": "https://monzo.me/joebloggs/amt?h=psiAKU",
  "QR_code": "https://internal-api.monzo.com/inbound-p2p/qr-code/joebloggs?currency=GBP&amount=amt"
}
```

`contact_details.json`: Replace the mobile number and email address with your details.
```json
{
  "mobile": "07803 293571",
  "email": "joethetutor@gmail.com"
}
```

## Usage

### Basic Usage

Generate invoices for the last full month:
```shell
python generate-invoices.py
```

### Advanced Options

```shell
# Generate for specific students only
python generate-invoices.py --only "Alice" "Bob"

# Custom date range
python generate-invoices.py --from 2024-01-01 --to 2024-01-31

# Custom start date (end defaults to today)
python generate-invoices.py --from 2024-01-01
```

For all options:
```shell
python generate-invoices.py --help
```

### Output

Invoices are saved as PDFs in the `invoices/` directory:
- Private clients: `alice-invoice.pdf`
- Agency clients: Combined into `agency-name-invoice.pdf`

## Development

### Running Tests

```shell
# Run all tests
pytest

# With coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_schema.py
```

### Type Checking

```shell
mypy src/ generate-invoices.py
```

### Project Structure

```
invoice-generator/
├── pyproject.toml           # Project configuration (replaces requirements.txt)
├── generate-invoices.py     # Main entry point
├── src/
│   ├── api.py              # Google Calendar integration
│   ├── schema.py           # Event classification logic
│   ├── models.py           # Pydantic models for validation
│   ├── validation.py       # JSON loading with validation
│   ├── constants.py        # Configuration constants
│   ├── logging_config.py   # Logging setup
│   ├── outputs.py          # PDF generation
│   ├── utils.py            # Date utilities
│   └── formatting.py       # Display formatting
├── tests/                  # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_schema.py
│   ├── test_utils.py
│   └── test_formatting.py
├── data/                   # Configuration files (git-ignored)
│   ├── students.json
│   ├── bank_details.json
│   ├── contact_details.json
│   ├── credentials.json
│   └── token.json
├── template/               # Invoice template
│   ├── invoice-template.html
│   └── styles.css
└── invoices/               # Generated PDFs
```

## Troubleshooting

### weasyprint Installation Issues

If you experience issues with `weasyprint` on macOS, see: [gobject-2.0-0 not able to load on macbook](https://stackoverflow.com/questions/69097224/gobject-2-0-0-not-able-to-load-on-macbook/69295303#69295303) on Stack Overflow.

### Pydantic Validation Errors

If you see "Validation failed" errors, check that your JSON files match the expected format:
- `students.json`: Each student needs `client_type`, `rate`, and `emails` (array of email addresses)
- `bank_details.json`: Must include `amt` placeholder in both `link` and `QR_code` fields
- `contact_details.json`: Must have valid `mobile` and `email` fields
- Email addresses must be in valid format

### Google Calendar Authentication

On first run, a browser window will open for Google OAuth. After authentication, a `token.json` file is created for future runs.

# Invoice Generator

Generates PDF invoices from Google Calendar events by matching attendee email addresses with details specified in `students.json`.

## Requirements
- Python >= 3.9
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

`bank_details.json`: You can get a payment link from the Monzo app. For the QR code link, just replace `joebloggs` with your Monzo username. Both the sort code and account number accept flexible input formats:
- Sort code: `"12-34-56"` or `"123456"` (dashes optional)
- Account number: `"1234 5678"` or `"12345678"` (spaces optional)

```json
{
  "name": "Joe Bloggs",
  "sort_code": "12-34-56",
  "account_number": "1234 5678",
  "bank": "Monzo Bank",
  "link": "https://monzo.me/joebloggs/{amount}?h=psiAKU",
  "QR_code": "https://internal-api.monzo.com/inbound-p2p/qr-code/joebloggs?currency=GBP&amount={amount}"
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

The project has a comprehensive test suite with **144 tests** achieving **99% code coverage**.

```shell
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# With coverage report (terminal)
pytest --cov=src --cov-report=term-missing

# With coverage report (HTML)
pytest --cov=src --cov-report=html
# Then open htmlcov/index.html in your browser

# Run specific test file
pytest tests/test_models.py

# Run specific test class
pytest tests/test_models.py::TestStudentInfo

# Run specific test
pytest tests/test_models.py::TestStudentInfo::test_valid_student_info
```

### Type Checking

```shell
mypy src/ generate-invoices.py
```

### Project Structure

```
invoice-generator/
├── pyproject.toml            # Project configuration with uv support
├── generate-invoices.py      # Main entry point
├── src/
│   ├── calendar_api.py       # Google Calendar API integration
│   ├── event_processing.py   # Event classification and processing
│   ├── invoice_generator.py  # PDF generation with WeasyPrint
│   ├── data_loader.py        # JSON loading with Pydantic validation
│   ├── models.py             # Pydantic models with validators and properties
│   ├── constants.py          # Configuration constants
│   ├── logging_config.py     # Logging setup (file + console handlers)
│   ├── utils.py              # Date utilities
│   └── formatting.py         # Display formatting (dates, times, currency)
├── tests/                    # Test suite
│   ├── conftest.py           # Pytest fixtures and test data
│   ├── test_calendar_api.py  # Google Calendar API tests (mocked)
│   ├── test_data_loader.py   # JSON loading and validation tests
│   ├── test_event_processing.py  # Event classification tests
│   ├── test_formatting.py    # Formatting function tests
│   ├── test_invoice_generator.py # PDF generation tests
│   ├── test_logging_config.py    # Logging configuration tests
│   ├── test_models.py        # Pydantic model validation tests
│   └── test_utils.py         # Date utility tests
├── data/                     # Configuration files (git-ignored)
│   ├── students.json
│   ├── bank_details.json
│   ├── contact_details.json
│   ├── credentials.json
│   └── token.json
├── template/                 # Invoice template
│   ├── invoice-template.html
│   └── styles.css
└── invoices/                 # Generated PDFs (git-ignored)
```

## Troubleshooting

### weasyprint Installation Issues

If you experience issues with `weasyprint` on macOS, see: [gobject-2.0-0 not able to load on macbook](https://stackoverflow.com/questions/69097224/gobject-2-0-0-not-able-to-load-on-macbook/69295303#69295303) on Stack Overflow.

### Pydantic Validation Errors

If you see "Validation failed" errors, check that your JSON files match the expected format:
- `students.json`: Each student needs `client_type`, `rate`, and `emails` (array of email addresses, can be empty)
- `bank_details.json`: Must include `{amount}` placeholder in both `link` and `QR_code` fields. Sort code must be 6 digits (dashes optional). Account number must be 8 digits (spaces optional).
- `contact_details.json`: Must have valid `country_code` (e.g., "+44"), `phone_number` (10+ digits, formatting optional), and `email` fields
- Email addresses must be in valid format

### Google Calendar Authentication

On first run, a browser window will open for Google OAuth. After authentication, a `token.json` file is created for future runs.

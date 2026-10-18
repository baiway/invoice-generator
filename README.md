# Invoice generator

[![Tests](https://img.shields.io/github/actions/workflow/status/baiway/invoice-generator/ci.yml?branch=main&label=Tests)](https://github.com/baiway/invoice-generator/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fbaiway%2Finvoice-generator%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.requires-python&label=python&logo=python)](pyproject.toml)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Generates PDF invoices for a tutoring business from Google Calendar events. Each lesson is matched to a student in `students.json`, either by the email address of someone invited to the event or, when no one else is invited, by the event's title (e.g. "Tutoring Jane"). Private clients get an invoice each; agencies gets a combined invoice with a page per student.

![An example invoice: a table of sessions and the amount owed, alongside bank and contact details for payment](docs/images/invoice-example.png)

## Quick start

You need [`uv`](https://docs.astral.sh/uv/), which installs Python 3.11 or newer if you don't already have it.

```shell
git clone https://github.com/baiway/invoice-generator.git
cd invoice-generator
uv sync
```

Then follow the [setup guide](docs/SETUP.md) to connect Google Calendar and add your students, bank details and contact details.

## Usage

Generate invoices for the last full month:
```shell
uv run generate-invoices
```

Some other options:
```shell
# Generate for specific students only
uv run generate-invoices --only "Jane Doe" "John Smith"

# Custom date range
uv run generate-invoices --from 2026-09-01 --to 2026-09-30

# All options
uv run generate-invoices --help
```

### Output

Invoices are saved as PDFs in the `invoices/` directory:
- Private clients: `jane-doe-invoice.pdf`
- Agency clients: combined into `agency-name-invoice.pdf`

A detailed log of each run is saved in `logs/`.

## Documentation

- [Setup](docs/SETUP.md): Google Calendar API credentials, the files in `data/`, naming calendar events, and troubleshooting
- [Development](docs/DEVELOPMENT.md): how it works, running the tests, linting and type checking

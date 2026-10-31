# Setup

This guide covers everything `generate-invoices` needs before its first run: access to your Google Calendar, a `data/` directory describing your students and how you get paid, and calendar events it can recognise as lessons.

## 1. Google Calendar API credentials

1. Visit the [Google Developers Console](https://console.developers.google.com/) and create a new project.
2. Enable the Google Calendar API for your project.
3. In the "Credentials" section, create a new OAuth client ID. If prompted, configure the OAuth consent screen, and add your own Google account as a test user.
4. Set the application type to "Desktop app" and name your client.
5. Download the JSON file containing your credentials, and rename it `credentials.json`.

For detailed steps, refer to the [official Google Calendar API documentation](https://developers.google.com/calendar/quickstart/python).

The generator only asks for read-only access to your calendar.

## 2. The `data/` directory

Create a `data` directory in the root of the project and move `credentials.json` into it:
```shell
mkdir data
mv ~/Downloads/credentials.json ./data
```

Then create three more files in `data/`: `students.json`, `bank_details.json` and `contact_details.json`. The directory is git-ignored, so none of this is committed. To keep it somewhere else, pass `--data-dir` to `generate-invoices`.

### `students.json`

Each student's full name maps to their details:
```json
{
  "Jane Doe": {
    "client_type": "private",
    "rate": 50,
    "emails": [
      "jane.doe@example.com",
      "parent@example.com"
    ]
  },
  "John Smith": {
    "client_type": "Example Agency",
    "rate": 40,
    "emails": []
  }
}
```

- The **name** appears on the invoice (and in its filename, for a private client), and is what `--only` expects.
- **`client_type`** is `"private"` for a client you invoice directly, who gets an invoice of their own. Anything else is the name of an agency: all of its students share one invoice, named after the agency.
- **`rate`** is the hourly rate in pounds.
- **`emails`** are the addresses that may be invited to the student's lessons, such as the student's and their parents'. It can be empty for students whose lessons are recognised by title instead (see [Naming calendar events](#3-naming-calendar-events)).
- **`reports`** and **`folders`** are optional, and only needed for [lesson reports](#5-lesson-reports-optional). Set `reports` to `true` to write reports for the student, and list in `folders` the link to each Google Drive folder their lessons are kept in, e.g. one for maths and one for physics:
  ```json
  "reports": true,
  "folders": [
    "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz?usp=sharing",
    "https://drive.google.com/drive/folders/1ZyXwVuTsRqPoNmLkJiHgFeDcBa?usp=sharing"
  ]
  ```

### `bank_details.json`

The account invoices ask to be paid into:
```json
{
  "name": "Joe Bloggs",
  "sort_code": "12-34-56",
  "account_number": "1234 5678",
  "bank": "Example Bank"
}
```

The sort code may be written with or without dashes (`"12-34-56"` or `"123456"`), and the account number with or without a space (`"1234 5678"` or `"12345678"`).

### `contact_details.json`

How clients can reach you, shown under the bank details:
```json
{
  "country_code": "+44",
  "phone_number": "7700 900123",
  "email": "joe.bloggs@example.com"
}
```

The phone number can include spaces or other formatting characters; only the digits are kept.

## 3. Naming calendar events

The generator decides which events are lessons, and who they were with, like this:

- **If anyone else is invited**, the event is matched by their email addresses against the `emails` in `students.json`, whatever its title.
- **If no one else is invited**, the title has to name the student in one of these forms:
  - `Tutoring <name>`, e.g. "Tutoring Jane" or "Tutoring Jane Doe"
  - `<name> BAC <anything>`, as in Blue Education's bookings, e.g. "Jane Doe BAC Physics" or "Jane Doe+BAC Physics"

  `<name>` can be a student's full name or the start of it, such as their first name, as long as only one student matches. Case doesn't matter. Titles containing "PMT" are lessons paid through an agency, so are never invoiced.
- **Cancelled events** are ignored, including those whose titles start "Cancelled:" or "Canceled:".

All-day events are never invoiced. To recognise other title formats, see the tip on adapting the project in the [README](../README.md).

## 4. First run

```shell
uv run generate-invoices
```

The first time, a browser window opens for you to sign in to Google and allow read-only access to your calendar. The result is saved as `data/token.json`, so later runs don't ask again.

## 5. Lesson reports (optional)

With `--reports`, `generate-invoices` also drafts a report for each student with `reports` set in `students.json`: a dated list of what each lesson covered, with links to the lesson's materials, for you to edit and then turn into a PDF.

### Lesson folders

Each folder in a student's `folders` holds a folder per lesson, named by its date:
```
Sam Maths/
├── 2026-10-02/
├── 2026-10-05/
└── 2026-10-13/
```

A lesson's folder can hold anything: GoodNotes exports and other PDFs, photos and screenshots, Google Docs, Slides and Sheets, and PowerPoint files. Name files after what's in them (e.g. "Integration by substitution.pdf" rather than "Note 14 Oct 2026.pdf"): names are read first, and are often more reliable than handwriting.

## Troubleshooting

### Validation errors

A `ValidationError` names the file and field that are wrong. The rules are:
- `students.json`: each student needs `client_type`, a `rate` above zero, and `emails` (a list, which can be empty)
- `students.json`: each of `folders` must be a link to a Google Drive folder, and a student with `reports` set needs at least one
- `bank_details.json`: the sort code must be 6 digits and the account number 8 digits, ignoring dashes and spaces
- `contact_details.json`: `country_code` must look like `"+44"`, and `phone_number` must have at least 10 digits
- Email addresses must be valid

### Google sign-in

If Google says access is blocked, check that your account is listed as a test user on the OAuth consent screen.

When a saved sign-in expires or is revoked, the browser opens to sign in again. While the consent screen's publishing status is "Testing", Google expires sign-ins after 7 days, so expect to sign in about once a week. Moving the app to "In production" avoids this; for an app only you use, Google shows an "unverified app" warning that you can click through.

### Skipped events

At the end of each run, the generator lists events it couldn't invoice, grouped by why:

- **With an unexpected format**: no one else was invited, and the title isn't one of the forms in [Naming calendar events](#3-naming-calendar-events). This list includes events that aren't lessons at all, so check it for lessons with mistyped titles.
- **Whose attendees aren't in `students.json`**: add the email addresses shown to the right student's `emails`.
- **Naming a student not in `students.json`**: add the student, or correct the name in the title.
- **That could be for more than one student**: two students share the name used in the title, so use their full name.
- **Lasting all day**: change the event to the lesson's actual times.

Unless you used `--only`, students with no lessons in the period are listed last, as a prompt to get in touch.

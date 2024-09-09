# Invoice generator
Generates invoices from Google Calendar events by matching attendee email addresses with details specified a `students.json` file.

## Getting started
### Requirements
- [Python 3](https://python.org/): to check whether you have Python 3 installed, type `python --version` into your terminal (or PowerShell on Windows). If Python is not installed, you can download it from [python.org/downloads](https://python.org/downloads/). You can find some concise guidance for installing Python [here](https://github.com/baiway/MScFE_python_refresher/blob/72b13a0eec7e3b9e2987c6c17a0fd6c839758c7b/docs/installing-python.md).
- Google Calendar API credentials (instructions below)

### Recommendations
- A very simple naming scheme for your Google Calendar events. All of mine are called something like "Tutoring Joe Bloggs", which makes this sort of automation possible. If you do not have a consistent naming convention for your Google Calendar, you're going to run into problems.

### Setting up Google Calendar API credentials
1. Visit the [Google Developers Console](https://console.developers.google.com/) and create a new project.
2. Enable the Google Calendar API for your project.
3. In the "Credentials" section, create a new OAuth client ID. If prompted, configure the OAuth consent screen with the necessary details.
4. Set the application type to "Desktop app" and name your client.
5. Download the JSON file containing your credentials, rename it to `credentials.json`.

For detailed steps, refer to the [official Google Calendar API documentation](https://developers.google.com/calendar/quickstart/python).

### Installation
**1. Clone the project**
```shell
git clone https://github.com/baiway/invoice-generator.git
```

**2. Change into the project directory**
```shell
cd invoice-generator
```

**3. Create a virtual environment**
```shell
python -m venv .venv
```

**4. Activate the environment**
```shell
source .venv/bin/activate
```

**5. Install dependencies**
```shell
pip install -r requirements.txt
```

### Setup
**1. Configure student data:** Create a directory called `data` in the root directory of the project
```shell
mkdir data
```

**2. Create three files in the `data` directory:** `students.json`, `bank_details.json`, and `contact_details.json`. Examples of each are shown below.

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

`contact_details.json`:
```json
{
  "mobile": "07803 293571",
  "email": "joethetutor@gmail.com"
}
```

## Running the script
To run the script, enter the following command:
```shell
python generate-invoices.py
```

By default, the script will generate invoices for all students seen within the last full month. For example, if the script is run on 3rd September 2024, the start of the invoice period will default to 1st August 2024 and the end will default to 31st August 2024. This behaviour can be changed with the `--only`, `--from` and `--to` options. For details, enter:
```shell
python generate-invoices.py --help
```

If the script runs successfully, invoices will be generated in the `invoices` folder.

## To-do:
- Add ChatGPT support for the above so a report can be generated based on some minimal prompts (e.g. "worked through exam questios on quadratic inequalities", "introduced quadratic simultaneous equations", "more practice is needed if they are to achieve their target grade", etc.)

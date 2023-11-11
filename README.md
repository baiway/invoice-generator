# Automatic invoices from Google Calendar
This is a simple Python program that generates invoices from Google Calendar events. 

## Getting started
### Prerequisites
- Python3.x: if you don't hve Python installed, download it from [python.org](https://python.org).
- A very simple naming scheme for your Google Calendar events. All of mine are called something like "Tutoring Joe Bloggs", which makes this sort of automation possible. If you do not have a consistent naming convention for your Google Calendar, you're going to run into problems.
- Your own Google Calendar API credentials (instructions below)

### Setting up Google Calendar API credentials
1. Visit the [Google Developers Console](https://console.developers.google.com/) and create a new project.
2. Enable the Google Calendar API for your project.
3. In the "Credentials" section, create a new OAuth client ID. If prompted, configure the OAuth consent screen with the necessary details.
4. Set the application type to "Desktop app" and name your client.
5. Download the JSON file containing your credentials, rename it to `credentials.json`.

For detailed steps, refer to the [official Google Calendar API documentation](https://developers.google.com/calendar/quickstart/python).

### Cloning the project
To clone the project, run the following command in your terminal:
```
  git clone https://github.com/baiway/invoice-generator.git
  cd invoice-generator
```

### Setting up
1. **Install dependencies:** Inside the project directory, run:
```
  pip install -r requirements.txt
```
This will install all the necessary Python packages.
2. **Configure student data:** Navigate to the `data` directory and create a `students.json` file with your student/client data. Here's an example:
```
  {
      "Alice": {
          "client_type": "private",
          "rate": 50,
          "aliases": ["Brad Pitt", "Dizzee Rascal"]
      },
      "Bob": {
          "client_type": "agency-x",
          "rate": 40,
          "aliases": ["Steven Graham"]
      },
  }
   
```

3. Move your `credentials.json` file to the `data` directory as well.


## Running the program
To run the program, execute the following command:
```
  python main.py
```
Follow the prompts in the terminal to either use a custom date range (by entering `y`) or the last full calendar month (by entering `n`) to generate invoices over.

Upon successful execution, the generated invoices will be saved as PDF files in the `invoices` folder within your project directory. 

## To-do:
- Implement unit tests to test `credentials.json` and validate fields in `students.json`
- Implement differential behaviour based on the `client_type`. For example, combine all the invoices from one agency into a single invoice. 
- Add an optional prompt to write a short report for each invoice
- Add ChatGPT support for the above so a report can be generated based on some minimal prompts (e.g. "worked through exam questios on quadratic inequalities", "introduced quadratic simultaneous equations", "more practice is needed if they are to achieve their target grade", etc.)

## Setting Up Google Calendar API Credentials

To run this project, you need to set up your own Google Calendar API credentials:

1. Visit the [Google Developers Console](https://console.developers.google.com/) and create a new project.
2. Enable the Google Calendar API for your project.
3. In the "Credentials" section, create a new OAuth client ID. If prompted, configure the OAuth consent screen with the necessary details.
4. Set the application type to "Desktop app" and name your client.
5. Download the JSON file containing your credentials, rename it to `credentials.json`, and place it in the project's root directory.
6. Remember to add `credentials.json` to your `.gitignore` file.

For detailed steps, refer to the [official Google Calendar API documentation](https://developers.google.com/calendar/quickstart/python).

Install dependencies by cloning the repository then using
```pip install -r requirements.txt```

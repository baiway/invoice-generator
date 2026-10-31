"""
Tests for src/invoice_generator/google_auth.py signing in to Google.

Google's OAuth flow and token refresh are mocked, so nothing here touches
the network or opens a browser.
"""

import pytest
from unittest.mock import MagicMock, patch
from google.auth.exceptions import RefreshError

from invoice_generator.google_auth import authenticate

CALENDAR = "https://www.googleapis.com/auth/calendar.readonly"
DRIVE = "https://www.googleapis.com/auth/drive.readonly"


def saved_creds(*, valid=True, expired=False, refresh_token="refresh",
                scopes=(CALENDAR,)):
    """Mock credentials as loaded from `token.json`."""
    creds = MagicMock()
    creds.valid = valid
    creds.expired = expired
    creds.refresh_token = refresh_token
    creds.scopes = list(scopes)
    creds.has_scopes.side_effect = lambda wanted: set(wanted) <= set(scopes)
    return creds


@pytest.fixture
def files(tmp_path):
    """`credentials.json`, and a `token.json` from an earlier sign-in."""
    creds_file = tmp_path / "credentials.json"
    token_file = tmp_path / "token.json"
    creds_file.write_text('{"installed": {}}')
    token_file.write_text('{"token": "saved_token"}')
    return creds_file, token_file


@pytest.fixture
def google():
    """Patch the token loader, token refresh and browser sign-in.

    A browser sign-in returns `google["new_creds"]`.
    """
    new_creds = MagicMock()
    new_creds.to_json.return_value = '{"token": "new_token"}'
    with patch("invoice_generator.google_auth.Credentials.from_authorized_user_file") as from_file, \
         patch("invoice_generator.google_auth.Request"), \
         patch("invoice_generator.google_auth.InstalledAppFlow.from_client_secrets_file") as flow:
        flow.return_value.run_local_server.return_value = new_creds
        yield {"from_file": from_file, "flow": flow, "new_creds": new_creds}


class TestAuthenticate:
    """Tests for authenticate function with Google OAuth."""

    def test_missing_credentials_file_raises_error(self, tmp_path):
        """Missing credentials.json should raise FileNotFoundError."""
        nonexistent_creds = tmp_path / "nonexistent" / "credentials.json"

        with pytest.raises(FileNotFoundError, match="not found"):
            authenticate(nonexistent_creds, tmp_path / "token.json", [CALENDAR])

    def test_valid_saved_token_is_used_as_it_is(self, files, google):
        """A valid token with the scopes needed needs no sign-in."""
        creds = saved_creds()
        google["from_file"].return_value = creds

        assert authenticate(*files, [CALENDAR]) is creds
        google["flow"].assert_not_called()
        creds.refresh.assert_not_called()

    def test_token_is_loaded_with_the_scopes_it_was_granted(self, files, google):
        """The token's own scopes are what get checked, so it must not be
        loaded as if it had the ones asked for."""
        google["from_file"].return_value = saved_creds()

        authenticate(*files, [CALENDAR])

        google["from_file"].assert_called_once_with(files[1])

    def test_expired_token_is_refreshed_and_saved(self, files, google):
        """An expired token with a refresh token should be refreshed."""
        creds = saved_creds(valid=False, expired=True)
        creds.to_json.return_value = '{"token": "refreshed_token"}'
        # A successful refresh makes the credentials valid again
        creds.refresh.side_effect = lambda request: setattr(creds, "valid", True)
        google["from_file"].return_value = creds

        assert authenticate(*files, [CALENDAR]) is creds
        creds.refresh.assert_called_once()
        google["flow"].assert_not_called()
        assert files[1].read_text() == '{"token": "refreshed_token"}'

    def test_failed_refresh_falls_back_to_signing_in(self, files, google, caplog):
        """A revoked or lapsed refresh token should mean signing in again,
        not a crash."""
        creds = saved_creds(valid=False, expired=True)
        creds.refresh.side_effect = RefreshError("invalid_grant")
        google["from_file"].return_value = creds

        assert authenticate(*files, [CALENDAR]) is google["new_creds"]
        google["flow"].return_value.run_local_server.assert_called_once_with(port=0)
        assert files[1].read_text() == '{"token": "new_token"}'
        assert "signing in again" in caplog.text

    def test_invalid_token_without_refresh_token_means_signing_in(self, files, google):
        """An invalid token that can't be refreshed needs a new sign-in."""
        google["from_file"].return_value = saved_creds(
            valid=False, expired=True, refresh_token=None
        )

        assert authenticate(*files, [CALENDAR]) is google["new_creds"]
        assert files[1].read_text() == '{"token": "new_token"}'

    def test_no_token_file_means_signing_in(self, tmp_path, google):
        """The first run signs in through the browser and saves the token."""
        creds_file = tmp_path / "credentials.json"
        token_file = tmp_path / "token.json"
        creds_file.write_text('{"installed": {}}')

        assert authenticate(creds_file, token_file, [CALENDAR]) is google["new_creds"]
        google["flow"].assert_called_once_with(creds_file, [CALENDAR])
        google["from_file"].assert_not_called()
        assert token_file.read_text() == '{"token": "new_token"}'

    def test_missing_scope_means_signing_in_for_old_and_new(
        self, files, google, caplog
    ):
        """A token without Drive access, the first time reports are
        written, should mean signing in again for both, so the next
        invoices-only run doesn't lose Drive access."""
        creds = saved_creds(scopes=(CALENDAR,))
        google["from_file"].return_value = creds

        assert authenticate(*files, [CALENDAR, DRIVE]) is google["new_creds"]
        google["flow"].assert_called_once_with(files[0], [CALENDAR, DRIVE])
        creds.refresh.assert_not_called()
        assert "lacks access" in caplog.text

    def test_extra_scopes_are_not_a_reason_to_sign_in(self, files, google):
        """A token with Drive access does for an invoices-only run."""
        creds = saved_creds(scopes=(CALENDAR, DRIVE))
        google["from_file"].return_value = creds

        assert authenticate(*files, [CALENDAR]) is creds
        google["flow"].assert_not_called()

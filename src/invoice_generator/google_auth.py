"""
Signing in to Google.

The calendar is always needed, Drive only when writing lesson reports, so
each run asks for the scopes it needs. One saved sign-in serves both.
"""

from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request

from invoice_generator.logging_config import get_logger

logger = get_logger(__name__)


def authenticate(
    credentials_path: Path,
    token_path: Path,
    scopes: list[str],
) -> Credentials:
    """Sign in to Google.

    Signs in through the browser the first time, then caches the result
    in `token_path` for subsequent runs. A cached sign-in that lacks one
    of `scopes` (e.g. Drive, the first time reports are written) means
    signing in again, keeping the access it already had.

    Args:
        credentials_path: Path to the OAuth client's `credentials.json`
        token_path: Path to the cached `token.json`, created if missing
        scopes: The access this run needs

    Returns:
        Credentials with at least `scopes`

    Raises:
        FileNotFoundError: If credentials.json is not found
    """
    if not credentials_path.is_file():
        raise FileNotFoundError(f"`{credentials_path.resolve()}` not found")

    # Reuse the cached token, refreshing it if it has expired. Refreshing
    # fails if the token was revoked or has lapsed (Google expires them
    # after 7 days for apps still in "Testing"), so sign in again then.
    # The token is loaded with the scopes it was granted, not `scopes`, so
    # that missing access can be noticed now rather than as a 403 later.
    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(token_path)
        if not creds.has_scopes(scopes):
            logger.warning("Saved Google sign-in lacks access this run needs; "
                           "signing in again")
            scopes = sorted(set(scopes) | set(creds.scopes or []))
            creds = None
        elif creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                logger.warning("Could not refresh Google token; signing in again")
                creds = None
            else:
                token_path.write_text(creds.to_json())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings

settings = get_settings()


class GoogleTokenError(Exception):
    pass


def verify_google_id_token(token: str) -> dict:
    """Verifies a Google-issued ID token and returns its claims (sub, email,
    name, picture). Raises GoogleTokenError on any verification failure.
    """
    if not settings.google_client_id:
        raise GoogleTokenError("GOOGLE_CLIENT_ID is not configured on the server")

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.google_client_id
        )
    except ValueError as exc:
        raise GoogleTokenError(str(exc)) from exc

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleTokenError("Invalid token issuer")

    return claims

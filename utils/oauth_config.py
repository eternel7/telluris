import os
import base64
import time
import jwt
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="facebook",
    api_base_url="https://graph.facebook.com/v19.0/",
    access_token_url="https://graph.facebook.com/v19.0/oauth/access_token",
    authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
    client_id=os.getenv("FACEBOOK_CLIENT_ID"),
    client_secret=os.getenv("FACEBOOK_CLIENT_SECRET"),
    client_kwargs={"scope": "email public_profile"},
)


def generate_apple_client_secret() -> str | None:
    key_b64 = os.getenv("APPLE_PRIVATE_KEY_B64", "")
    if not key_b64:
        return None
    private_key = base64.b64decode(key_b64).decode()
    now = int(time.time())
    return jwt.encode(
        {
            "iss": os.getenv("APPLE_TEAM_ID"),
            "iat": now,
            "exp": now + 86400 * 180,
            "aud": "https://appleid.apple.com",
            "sub": os.getenv("APPLE_CLIENT_ID"),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": os.getenv("APPLE_KEY_ID"), "alg": "ES256"},
    )


_apple_id = os.getenv("APPLE_CLIENT_ID")
_apple_secret = generate_apple_client_secret()

if _apple_id and _apple_secret:
    oauth.register(
        name="apple",
        server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
        client_id=_apple_id,
        client_secret=_apple_secret,
        client_kwargs={"scope": "openid email name"},
    )

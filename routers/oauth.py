import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from db.config import get_doc, save_doc
from utils.auth import create_access_token
from utils.oauth_config import oauth, ENABLED_PROVIDERS, generate_apple_client_secret

router = APIRouter()


def upsert_user(provider: str, sub: str, email: str | None, email_verified: bool, name: str | None) -> str:
    # 1. Fast lookup by dedicated identity document (keyed by provider:sub)
    identity_id = f"identity:{provider}:{sub}"
    identity_doc = get_doc(identity_id)
    if identity_doc:
        return identity_doc["user_id"]

    # 2. Link to existing account if email is verified
    user_id = None
    if email and email_verified:
        user_doc = get_doc(f"user:{email}")
        if user_doc:
            user_id = user_doc["_id"]
            identities = user_doc.get("identities", [])
            identities.append({"provider": provider, "sub": sub})
            user_doc["identities"] = identities
            save_doc(user_doc)

    # 3. Create new user
    if not user_id:
        user_id = f"user:{email}" if email else f"user:apple_{sub}"
        save_doc({
            "_id": user_id,
            "type": "user",
            "email": email or "",
            "username": name or "",
            "identities": [{"provider": provider, "sub": sub}],
        })

    # Create the identity lookup document for future logins
    save_doc({"_id": identity_id, "type": "identity", "user_id": user_id})
    return user_id


def _auth_redirect(user_id: str) -> RedirectResponse:
    token = create_access_token({"user_id": user_id})
    response = RedirectResponse(url="/embleme")
    response.set_cookie(key="auth_token", value=token, httponly=True, samesite="lax")
    return response


# ── Google ───────────────────────────────────────────────────────────────────

@router.get("/login/google")
async def login_google(request: Request):
    if "google" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    redirect_uri = request.url_for("auth_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google", name="auth_google")
async def auth_google(request: Request):
    if "google" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    token = await oauth.google.authorize_access_token(request)
    userinfo = token["userinfo"]
    user_id = upsert_user(
        provider="google",
        sub=userinfo["sub"],
        email=userinfo.get("email"),
        email_verified=userinfo.get("email_verified", False),
        name=userinfo.get("name"),
    )
    return _auth_redirect(user_id)


# ── Facebook ─────────────────────────────────────────────────────────────────

@router.get("/login/facebook")
async def login_facebook(request: Request):
    if "facebook" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    redirect_uri = request.url_for("auth_facebook")
    return await oauth.facebook.authorize_redirect(request, redirect_uri)


@router.get("/auth/facebook", name="auth_facebook")
async def auth_facebook(request: Request):
    if "facebook" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    token = await oauth.facebook.authorize_access_token(request)
    resp = await oauth.facebook.get("me?fields=id,name,email", token=token)
    profile = resp.json()
    user_id = upsert_user(
        provider="facebook",
        sub=profile["id"],
        email=profile.get("email"),
        email_verified=bool(profile.get("email")),
        name=profile.get("name"),
    )
    return _auth_redirect(user_id)


# ── Apple ────────────────────────────────────────────────────────────────────

@router.get("/login/apple")
async def login_apple(request: Request):
    if "apple" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    redirect_uri = str(request.url_for("auth_apple"))
    return await oauth.apple.authorize_redirect(request, redirect_uri, response_mode="form_post")


@router.post("/auth/apple", name="auth_apple")
async def auth_apple(request: Request):
    if "apple" not in ENABLED_PROVIDERS:
        return RedirectResponse(url="/auth")
    # Apple regenerates the client_secret JWT per-request (ES256, valid 6 months max)
    client_secret = generate_apple_client_secret()
    token = await oauth.apple.authorize_access_token(request, client_secret=client_secret)
    userinfo = token.get("userinfo", {})

    # Name only sent by Apple on first authorisation, inside the form body
    name = None
    form = await request.form()
    user_blob = form.get("user")
    if user_blob:
        try:
            user_data = json.loads(user_blob)
            fn = user_data.get("name", {})
            name = f"{fn.get('firstName', '')} {fn.get('lastName', '')}".strip() or None
        except Exception:
            pass

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    user_id = upsert_user(
        provider="apple",
        sub=sub,
        email=email,
        email_verified=not userinfo.get("is_private_email", False),
        name=name,
    )
    return _auth_redirect(user_id)

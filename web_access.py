"""Single-team HTTP Basic authentication, used behind HTTPS for online hosting."""
import base64
import hmac
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("THREAD_REQUIRE_AUTH") == "1" and len(os.environ.get("THREAD_APP_PASSWORD", "")) < 12:
        raise RuntimeError("Set THREAD_APP_PASSWORD to at least 12 characters before starting online mode.")
    yield


async def protect_app(request, call_next):
    if request.url.path != "/health" and os.environ.get("THREAD_REQUIRE_AUTH") == "1":
        header = request.headers.get("authorization", "")
        valid = False
        try:
            scheme, token = header.split(" ", 1)
            username, password = base64.b64decode(token, validate=True).decode("utf-8").split(":", 1)
            valid = (scheme.lower() == "basic"
                     and hmac.compare_digest(username.encode(), os.environ.get("THREAD_APP_USERNAME", "admin").encode())
                     and hmac.compare_digest(password.encode(), os.environ.get("THREAD_APP_PASSWORD", "").encode())
                     and len(os.environ.get("THREAD_APP_PASSWORD", "")) >= 12)
        except (ValueError, UnicodeError):
            pass
        if not valid:
            return JSONResponse({"detail": "Vui lòng đăng nhập để sử dụng ứng dụng."}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="Thread Studio", charset="UTF-8"',
                                         "Cache-Control": "no-store"})
    # HTTP Basic is cached by browsers. Prevent another website from causing
    # authenticated uploads or paid analysis requests through the user's browser.
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("origin"):
        try:
            origin = urlsplit(request.headers["origin"])
            same_origin = (origin.scheme in ("http", "https") and origin.username is None
                           and origin.netloc.casefold() == request.headers.get("host", "").casefold())
        except ValueError:
            same_origin = False
        if not same_origin:
            return JSONResponse({"detail": "Chỉ chấp nhận yêu cầu từ trang ứng dụng."}, status_code=403)
    size = request.headers.get("content-length")
    if size and (not size.isdigit() or len(size) > 10 or int(size) > 12_000_000):
        return JSONResponse({"detail": "Yêu cầu tối đa 12 MB."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response

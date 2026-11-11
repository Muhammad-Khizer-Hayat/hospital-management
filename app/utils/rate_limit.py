"""Small in-memory rate limiter + login lockout (no extra packages needed)."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict = defaultdict(deque)       # key -> timestamps of recent requests
_login_fails: dict = defaultdict(deque)  # "email|ip" -> timestamps of failed logins

LOGIN_MAX_FAILS = 5
LOGIN_WINDOW = 15 * 60   # 5 failures within 15 minutes => locked for the rest of that window


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(limit: int, window_seconds: int, scope: str):
    """FastAPI dependency: allow `limit` requests per `window_seconds` per IP."""
    def dependency(request: Request):
        key = f"{scope}:{client_ip(request)}"
        now = time.time()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise HTTPException(status_code=429,
                                    detail="Too many requests. Please slow down and try again shortly.",
                                    headers={"Retry-After": str(retry)})
            q.append(now)
    return dependency


def _fail_key(email: str, ip: str) -> str:
    return f"{(email or '').strip().lower()}|{ip}"


def login_locked_for(email: str, ip: str) -> int:
    """Seconds the caller must still wait (0 = not locked)."""
    now = time.time()
    with _lock:
        q = _login_fails[_fail_key(email, ip)]
        while q and now - q[0] > LOGIN_WINDOW:
            q.popleft()
        if len(q) >= LOGIN_MAX_FAILS:
            return int(LOGIN_WINDOW - (now - q[0])) + 1
    return 0


def record_login_failure(email: str, ip: str):
    with _lock:
        _login_fails[_fail_key(email, ip)].append(time.time())


def clear_login_failures(email: str, ip: str):
    with _lock:
        _login_fails.pop(_fail_key(email, ip), None)
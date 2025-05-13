from fastapi import APIRouter, HTTPException, Request
import redis
import uuid
import hashlib
import os

from datetime import datetime

router = APIRouter()
r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, decode_responses=True)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
def register_user(username: str, password: str):
    if r.exists(f"user:{username}"):
        raise HTTPException(status_code=400, detail="User already exists.")
    r.hset(f"user:{username}", mapping={"password": hash_password(password)})
    return {"msg": "User registered successfully"}

@router.post("/login")
def login_user(username: str, password: str):
    # Rate limit check
    attempts_key = f"login_attempts:{username}"
    attempts = r.incr(attempts_key)
    if attempts == 1:
        r.expire(attempts_key, 300)  # 5-minute window

    if attempts > 5:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    stored_hash = r.hget(f"user:{username}", "password")
    if not stored_hash or stored_hash != hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_token = str(uuid.uuid4())
    r.setex(f"session:{session_token}", 3600, username)  # expires in 1 hour

    # Publish login event
    r.publish("login-events", f"{username} logged in at {datetime.utcnow().isoformat()}")

    # Log audit stream
    r.xadd("audit:logins", {"user": username, "ts": datetime.utcnow().isoformat()})

    return {"token": session_token}


@router.get("/dashboard")
def dashboard(request: Request, token: str):
    user = r.get(f"session:{token}")
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired session.")
    return {"msg": f"Welcome {user}"}

@router.post("/logout")
def logout(token: str):
    r.delete(f"session:{token}")
    return {"msg": "Logged out successfully"}


@router.get("/audit-log")
def get_recent_logins(limit: int = 10):
    entries = r.xrevrange("audit:logins", "+", "-", count=limit)
    return [{"id": eid, "user": data["user"], "timestamp": data["ts"]} for eid, data in entries]

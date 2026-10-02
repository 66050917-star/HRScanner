import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FIREBASE_API_KEY", "").strip()
BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

ERROR_MESSAGES = {
    "EMAIL_EXISTS": "อีเมลนี้ถูกสมัครไว้แล้ว",
    "OPERATION_NOT_ALLOWED": "Firebase ยังไม่ได้เปิด Email/Password sign-in",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "มีการลองหลายครั้งเกินไป กรุณารอสักครู่แล้วลองใหม่",
    "EMAIL_NOT_FOUND": "ไม่พบบัญชีผู้ใช้นี้",
    "INVALID_PASSWORD": "รหัสผ่านไม่ถูกต้อง",
    "INVALID_LOGIN_CREDENTIALS": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
    "USER_DISABLED": "บัญชีนี้ถูกระงับการใช้งาน",
    "WEAK_PASSWORD": "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร",
    "INVALID_EMAIL": "รูปแบบอีเมลไม่ถูกต้อง",
}


def _ensure_key():
    if not API_KEY:
        raise RuntimeError("ไม่พบ FIREBASE_API_KEY ใน Environment/Streamlit Secrets")


def _post(action, email, password):
    _ensure_key()
    url = f"{BASE_URL}:{action}?key={API_KEY}"
    response = requests.post(
        url,
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=20,
    )
    data = response.json()
    if response.ok:
        return data

    code = data.get("error", {}).get("message", "FIREBASE_AUTH_ERROR")
    # Firebase can append details after a colon.
    short_code = code.split(" : ", 1)[0]
    raise RuntimeError(ERROR_MESSAGES.get(short_code, code))


def register_user(email, password):
    return _post("signUp", email.strip(), password)


def login_user(email, password):
    return _post("signInWithPassword", email.strip(), password)

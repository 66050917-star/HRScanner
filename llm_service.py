"""ชั้นเรียก AI ที่สลับ provider/โมเดลได้ (OpenRouter หรือ Gemini) — Knowledge/คะแนนไม่ขึ้นกับไฟล์นี้"""
import os, re, json, base64
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"), override=True)
OR_URL = "https://openrouter.ai/api/v1"

def _e(name, default=""): return (os.getenv(name) or default).strip().strip("\"'")
def provider(): return _e("LLM_PROVIDER", "openrouter").lower()
def get_key(): return _e("OPENROUTER_API_KEY") if provider() == "openrouter" else _e("GEMINI_API_KEY")
def get_model():
    return _e("OPENROUTER_MODEL", "google/gemini-2.5-flash") if provider() == "openrouter" else _e("GEMINI_MODEL", "gemini-2.5-flash")
def get_vision_model():
    return _e("OPENROUTER_VISION_MODEL") or get_model() if provider() == "openrouter" else get_model()

def parse_json(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try: return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", t, re.S)
        if not m: raise ValueError("AI ตอบกลับไม่ใช่ JSON")
        return json.loads(m.group())

def _or_chat(messages, model, json_mode):
    body = {"model": model, "messages": messages, "temperature": 0}
    if json_mode: body["response_format"] = {"type": "json_object"}
    r = requests.post(f"{OR_URL}/chat/completions", json=body, timeout=180,
                      headers={"Authorization": f"Bearer {get_key()}", "X-Title": "TalentAI Screener"})
    if r.status_code == 400 and json_mode:      # บางโมเดลไม่รองรับ JSON mode -> ลองใหม่โดยไม่ใช้
        return _or_chat(messages, model, False)
    data = r.json()
    if r.status_code != 200 or "error" in data:
        raise RuntimeError(f"OpenRouter ({model}): {data.get('error', r.text)}"[:400])
    return data["choices"][0]["message"]["content"] or ""

def chat_json(system, prompt):
    if provider() == "openrouter":
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        return parse_json(_or_chat(msgs, get_model(), True))
    from google import genai
    from google.genai import types
    res = genai.Client(api_key=get_key()).models.generate_content(model=get_model(), contents=prompt,
        config=types.GenerateContentConfig(temperature=0, system_instruction=system, response_mime_type="application/json"))
    return parse_json(res.text)

OCR_PROMPT = ("ถอดข้อความทั้งหมดในภาพนี้ตามที่ปรากฏจริง (ไทย/อังกฤษ/ตัวเลข) ห้ามแก้ ห้ามสรุป ห้ามเดาส่วนที่อ่านไม่ออก "
              "รักษาลำดับบรรทัดและตารางเกรดให้อ่านง่าย ตอบเฉพาะข้อความที่ถอดได้")

def vision_text(data: bytes, mime: str) -> str:
    if provider() == "openrouter":
        url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        msgs = [{"role": "user", "content": [{"type": "text", "text": OCR_PROMPT}, {"type": "image_url", "image_url": {"url": url}}]}]
        return _or_chat(msgs, get_vision_model(), False).strip()
    from google import genai
    from google.genai import types
    res = genai.Client(api_key=get_key()).models.generate_content(model=get_model(),
        contents=[types.Part.from_bytes(data=data, mime_type=mime), OCR_PROMPT])
    return (res.text or "").strip()

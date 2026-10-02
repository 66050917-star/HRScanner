"""สกัดข้อมูลจาก Resume/Transcript ด้วย AI (ผ่าน llm_service) — ไม่มี key = rule-based"""
import os, re, json, copy
from knowledge import SYSTEM_PROMPT, ROLE_HINTS
from llm_service import get_key, chat_json  # สลับ provider/โมเดลที่ llm_service

SKILL_BANK = ["React", "Node.js", "TypeScript", "JavaScript", "Python", "Java", "PostgreSQL", "MySQL", "AWS", "Docker",
              "Git", "SQL", "Excel", "Power BI", "SEO", "Google Ads", "Google Analytics", "Facebook Ads",
              "Content Marketing", "Figma", "Photoshop", "SAP", "Payroll", "Recruitment"]
SOFT_BANK = ["Communication", "Teamwork", "Leadership", "Problem Solving", "การสื่อสาร", "ทำงานเป็นทีม", "ภาวะผู้นำ"]
EMPTY = {"name": "", "email": "", "phone": "", "summary": "", "education": [], "experience": [], "hard_skills": [],
         "soft_skills": [], "projects": [], "certificates": [], "relevant_years": None, "major_match": "unknown",
         "other_found": {}, "recommended_positions": [], "mode": "rules"}
SCHEMA = """{"name":"","email":"","phone":"","summary":"สรุปสั้น 1-2 ประโยคจากข้อมูลจริงใน Resume",
"education":[{"level":"","degree":"","major":"","institution":"","year":"","gpa":null,"evidence":""}],
"experience":[{"title":"","company":"","period":"","relevance":"direct|partial|minor|none|unknown"}],
"hard_skills":[],"soft_skills":[],
"projects":[{"name":"","description":"","relevance":"direct|partial|none|unknown"}],
"certificates":[{"name":"","relevance":"direct|partial|none|unknown"}],
"relevant_years":null,"major_match":"match|partial|none|unknown","other_found":{},
"recommended_positions":[{"position":"","reason":""}]}"""

def _lines(t): return [l.strip() for l in t.splitlines() if l.strip()]
def _rel(line, terms):
    h = sum(t.lower() in line.lower() for t in terms)
    return "direct" if h >= 2 else "partial" if h == 1 else "none"
def _lvl(s):
    s = s.lower()
    return next(v for k, v in [("เอก", "ปริญญาเอก"), ("ph", "ปริญญาเอก"), ("โท", "ปริญญาโท"), ("master", "ปริญญาโท"),
                               ("ตรี", "ปริญญาตรี"), ("bachelor", "ปริญญาตรี"), ("ปวส", "ปวส"), ("ปวช", "ปวช")] if k in s)

def roles_from_skills(skills):
    low = {s.lower() for s in skills}
    r = sorted(((sum(s.lower() in low for s in sk), n, sk) for n, sk in ROLE_HINTS.items()), reverse=True)
    return [{"position": n, "reason": "พบทักษะ: " + ", ".join(s for s in sk if s.lower() in low)} for c, n, sk in r if c >= 2][:3]

def extract_rules(resume, transcript, jd):
    d = copy.deepcopy(EMPTY); text = resume + "\n" + transcript; L = _lines(resume)
    terms = jd["skills"] + [w[:6] for w in re.split(r"\W+", jd["title"]) if len(w) >= 4]  # ตัดคำให้ market ตรงกับ marketing
    d["name"] = L[0] if L else ""
    if m := re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", resume): d["email"] = m.group()
    if m := re.search(r"0\d[\d\- ]{7,11}\d", resume): d["phone"] = m.group()
    for l in _lines(text):
        lv = re.search(r"ปริญญาเอก|ปริญญาโท|ปริญญาตรี|ปวส|ปวช|ph\.?d|master|bachelor", l, re.I)
        mj = re.search(r"สาขา(?:วิชา)?\s*:?\s*(.+?)(?=\s+(?:มหาวิทยาลัย|GPAX|GPA)|$)", l)
        gp = re.search(r"(?:GPAX|GPA|เกรดเฉลี่ย\S*)\D{0,10}([0-4]\.\d{1,2})", l, re.I)
        un = re.search(r"มหาวิทยาลัย\S+", l)
        if lv or mj or gp:
            d["education"].append({"level": _lvl(lv.group()) if lv else "", "major": mj.group(1).strip() if mj else "",
                                   "institution": un.group() if un else "", "gpa": float(gp.group(1)) if gp else None, "evidence": l})
    majors = [m.lower() for m in jd.get("majors", [])]; cm = " ".join(e["major"] for e in d["education"]).lower()
    d["major_match"] = "unknown" if (not majors or not cm) else "match" if any(m in cm for m in majors) else "none"
    for l in L:
        if "@" in l and not re.search(r"@\S+\.\S+", l):
            head, _, rest = l.lstrip("-• ").partition("@")
            per = re.search(r"\(([^)]*)\)", rest)
            d["experience"].append({"title": head.strip(), "company": re.split(r"[(:]", rest)[0].strip(),
                                    "period": per.group(1) if per else "", "relevance": _rel(l, terms)})
    if m := re.search(r"ประสบการณ์[^\d\n]{0,15}(\d+(?:\.\d+)?)\s*(?:ปี|years?)", resume, re.I):
        d["relevant_years"] = float(m.group(1)) if any(e["relevance"] != "none" for e in d["experience"]) else 0.0
    low = resume.lower()
    d["hard_skills"] = [s for s in dict.fromkeys(SKILL_BANK + jd["skills"]) if s.lower() in low]
    d["soft_skills"] = [s for s in SOFT_BANK if s.lower() in low]
    d["projects"] = [{"name": l.lstrip("-• ")[:70], "description": l, "relevance": _rel(l, terms)}
                     for l in L if len(l) > 12 and re.search(r"โปรเจกต์|โครงงาน|project", l, re.I)]
    d["certificates"] = [{"name": l.lstrip("-• "), "relevance": _rel(l, terms)} for l in L
                         if len(l) > 10 and re.search(r"certified|certificate|ใบรับรอง|อบรม|training|award|รางวัล", l, re.I)]
    d["other_found"] = {r: next(l for l in L if r.lower() in l.lower()) for r in jd.get("others", []) if any(r.lower() in l.lower() for l in L)}
    d["recommended_positions"] = roles_from_skills(d["hard_skills"])
    if d["experience"]:
        d["summary"] = f"{d['experience'][0]['title']}" + (f" ประสบการณ์ {d['relevant_years']:g} ปี" if d["relevant_years"] else "")
    return d

def extract_ai(resume, transcript, jd):
    if not get_key(): return extract_rules(resume, transcript, jd)
    try:
        prompt = f"""วิเคราะห์ Resume เทียบกับ JD (ถ้ามี) แล้วตอบเป็น JSON object เท่านั้นตามโครงสร้าง:
{SCHEMA}
- level ใช้ได้เฉพาะ: ปวช, ปวส, ปริญญาตรี, ปริญญาโท, ปริญญาเอก (ไม่พบ = "")
- relevant_years = ปีประสบการณ์ที่เกี่ยวข้องกับ JD ที่คำนวณได้จากช่วงเวลาที่ระบุจริงใน Resume (ไม่ระบุ = null)
- other_found = {{ข้อกำหนดอื่นใน JD: ข้อความคัดลอกตรงตัวจาก Resume}} เฉพาะข้อที่มีหลักฐานจริง
- gpa ใส่เฉพาะเมื่อระบุไว้จริง มิฉะนั้น null
- ไม่มี JD: relevance="unknown", relevant_years=null, major_match="unknown", other_found={{}}
=== JD ===\n{json.dumps(jd, ensure_ascii=False)}
=== RESUME ===\n{resume}
=== TRANSCRIPT (เสริมข้อมูลการศึกษาเท่านั้น) ===\n{transcript}"""
        out = chat_json(SYSTEM_PROMPT, prompt)
        if not isinstance(out, dict): raise ValueError("รูปแบบผลลัพธ์ไม่ถูกต้อง")
        return {**EMPTY, **out, "mode": "ai"}
    except Exception as e:
        print("AI failed, fallback to rules:", e)
        d = extract_rules(resume, transcript, jd); d["ai_error"] = str(e)[:300]; return d

def skills_from_jd(jd_text):
    if get_key():
        try:
            out = chat_json("ตอบเป็น JSON เท่านั้น", 'ดึงเฉพาะทักษะ/เครื่องมือที่ JD ระบุไว้ชัดเจน (ห้ามเดา) ตอบเป็น {"skills": ["..."]}\n' + jd_text)
            out = out.get("skills", []) if isinstance(out, dict) else out
            out = [str(s).strip() for s in out if str(s).strip()]
            if out: return out
        except Exception as e:
            print("AI JD failed, fallback to rules:", e)
    return [s for s in SKILL_BANK if s.lower() in jd_text.lower()]

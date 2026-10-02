import os
import datetime
from types import SimpleNamespace
import requests
import streamlit as st
import db_service as db
from export_service import to_csv, to_xlsx
from parser_service import read_upload
from ai_service import extract_ai, skills_from_jd, get_key
from scoring_service import score_candidate
from knowledge import EDU_OPTIONS, NOT_FOUND, CANT_CALC, DISCLAIMER
from firebase_auth import register_user, login_user

st.set_page_config(page_title="TalentAI Screener", page_icon="🧑‍💼", layout="wide")
db.init()
STATUSES = ["Pending", "Shortlisted", "Interview Scheduled", "Rejected"]
LABELS = {"skills": "Skills", "experience": "Experience", "education": "Education",
          "projects_certs": "Projects / Certificates", "other": "คุณสมบัติอื่น ๆ"}
ICON = {"High": "🟢", "Moderate": "🟡", "Low": "🔴", "N/A": "⚪"}
FIELDS = ["jd_title", "jd_exp", "jd_skills", "jd_edu", "jd_majors", "jd_gpa", "jd_others", "jd_text", "cand_name", "resume_text", "transcript_text"]
DEMOS = {
    "Full Stack Dev": dict(jd_title="Senior Full Stack Developer", jd_exp=3.0, jd_skills="React, Node.js, TypeScript, PostgreSQL, AWS, Docker",
        jd_edu="ปริญญาตรี", jd_majors="วิทยาการคอมพิวเตอร์, Computer Science, วิศวกรรมคอมพิวเตอร์", jd_gpa=0.0, jd_others="English, AWS Certified",
        jd_text="ต้องการ Full Stack Engineer ประสบการณ์ 3+ ปี เชี่ยวชาญ React, Node.js, TypeScript, PostgreSQL, Deploy บน AWS และใช้ Docker", cand_name="",
        resume_text="สมชาย ใจดี\nsomchai@example.com 081-234-5678\nประสบการณ์ทำงาน\n- Senior Software Developer @ Tech Solutions (2022 - ปัจจุบัน): ประสบการณ์ 4 ปี\nทักษะ: React, Node.js, TypeScript, PostgreSQL, AWS, Git, Communication\nโปรเจกต์\n- โปรเจกต์ ระบบ E-commerce ด้วย React และ Node.js บน AWS\nใบรับรอง\n- AWS Certified Developer\nภาษา: English (TOEIC 800)",
        transcript_text="มหาวิทยาลัยเทคโนโลยีแห่งชาติ\nปริญญาตรี สาขา วิทยาการคอมพิวเตอร์\nGPAX: 3.85"),
    "Digital Marketer": dict(jd_title="Digital Marketer", jd_exp=2.0, jd_skills="Google Ads, SEO, Content Marketing, Google Analytics, Facebook Ads",
        jd_edu="ปริญญาตรี", jd_majors="การตลาด, Marketing", jd_gpa=2.5, jd_others="English",
        jd_text="ต้องการ Digital Marketer ดูแล Google Ads, Facebook Ads, SEO, Content Marketing และวิเคราะห์ผลด้วย Google Analytics", cand_name="",
        resume_text="วิภาดา รักเรียน\nประสบการณ์ทำงาน\n- Marketing Associate @ Growth Agency (2024 - ปัจจุบัน): ประสบการณ์ 2 ปี\nทักษะ: Google Ads, SEO, Facebook Ads\n- บริหารงบโฆษณาเดือนละ 200,000 บาท",
        transcript_text="มหาวิทยาลัยธรรมศาสตร์\nปริญญาตรี สาขา การตลาด\nGPAX: 3.20"),
}
for k, v in DEMOS["Full Stack Dev"].items(): st.session_state.setdefault(k, v)
st.session_state.setdefault("upl", 0)

def load_demo(name): st.session_state.update(DEMOS[name])
def clear_all():
    ss = st.session_state
    for k in FIELDS: ss[k] = ""
    ss.jd_exp = 0.0; ss.jd_gpa = 0.0; ss.jd_edu = "ไม่ระบุ"; ss.upl += 1
    ss.pop("current", None); ss.pop("view_id", None)
def as_upload(f): return SimpleNamespace(filename=f.name, read=f.getvalue)
def split(s): return [x.strip() for x in s.split(",") if x.strip()]

PRESET_TEXT = ["google/gemini-2.5-flash", "openai/gpt-4o-mini", "anthropic/claude-sonnet-4.5", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]
PRESET_VISION = ["google/gemini-2.5-flash", "openai/gpt-4o", "anthropic/claude-sonnet-4.5", "qwen/qwen2.5-vl-72b-instruct"]

@st.cache_data(ttl=3600)
def or_models():  # ดึงรายชื่อโมเดลล่าสุดจาก OpenRouter (ไม่ต้องใช้ key)
    try:
        d = requests.get("https://openrouter.ai/api/v1/models", timeout=15).json()["data"]
        return sorted(m["id"] for m in d), sorted(m["id"] for m in d if "image" in (m.get("architecture") or {}).get("input_modalities", []))
    except Exception:
        return PRESET_TEXT, PRESET_VISION

def pick(label, options, env, default):
    cur = os.getenv(env) or default
    return st.selectbox(label, options, index=options.index(cur) if cur in options else 0)

with st.sidebar:
    st.subheader("🤖 AI")
    prov = st.radio("ผู้ให้บริการ", ["openrouter", "gemini"], format_func=lambda x: "OpenRouter (เลือกโมเดลได้)" if x == "openrouter" else "Google Gemini")
    os.environ["LLM_PROVIDER"] = prov
    k = st.text_input("API key (ใช้เฉพาะรอบนี้)", type="password")
    if prov == "openrouter":
        if k.strip(): os.environ["OPENROUTER_API_KEY"] = k.strip()
        texts, visions = or_models()
        os.environ["OPENROUTER_MODEL"] = st.text_input("พิมพ์ชื่อโมเดลเอง (ไม่บังคับ)", key="m_txt").strip() or pick("โมเดลวิเคราะห์ Resume", texts, "OPENROUTER_MODEL", PRESET_TEXT[0])
        os.environ["OPENROUTER_VISION_MODEL"] = pick("โมเดลอ่านภาพ/PDF สแกน (รองรับรูป)", visions, "OPENROUTER_VISION_MODEL", PRESET_VISION[0])
    elif k.strip(): os.environ["GEMINI_API_KEY"] = k.strip()
    if get_key(): st.success(f"พบ API key — ใช้ {prov} ได้")
    else: st.warning("ไม่พบ API key — ใช้โหมด rule-based (ความเกี่ยวข้องประเมินจากคำสำคัญ ควรตรวจซ้ำ)")

def fmt(x): return f"{x:.2f}".rstrip("0").rstrip(".")
def mark(w): return "✅" if w["score"] >= w["max"] else "❌" if w["score"] <= 0 else "🟡"

def report_md(p):
    x, r, jd = p["extracted"], p["result"], p["jd"]
    sc = f"{fmt(r['score'])}/100" if r["score"] is not None else CANT_CALC
    score_md = []
    for k, v in r["parts"].items():
        score_md.append(f"### {LABELS[k]}: {fmt(v['score'])}/{v['max']}")
        if "rows" not in v: score_md += [f"- {n}" for n in v.get("notes", [])]; continue
        score_md.append(f"วิธีคิด: {v['formula']}")
        for w in v["rows"]:
            score_md.append(f"- {mark(w)} {w['label']} ({fmt(w['score'])}/{fmt(w['max'])}): {w['why']}" + (f" — หลักฐาน: “{w['evidence']}”" if w.get("evidence") else ""))
    return "\n".join([f"# {x['name']} — {jd['title'] or 'ไม่ระบุตำแหน่ง'}", f"## 1. Candidate Summary\n{x['summary'] or NOT_FOUND}",
        "## 2. Education\n" + ("\n".join(f"- {e.get('level','')} {e.get('major','')} {e.get('institution','')}" for e in x["education"]) or NOT_FOUND),
        "## 3. Work Experience\n" + ("\n".join(f"- {e['title']} @ {e['company']} {e['period']}" for e in x["experience"]) or NOT_FOUND),
        "## 4. Skills\nHard: " + (", ".join(x["hard_skills"]) or NOT_FOUND) + "\nSoft: " + (", ".join(x["soft_skills"]) or NOT_FOUND),
        f"## 5. Matching Score: {sc}", *score_md,
        "## 6. Recommended Positions\n" + ("\n".join(f"- {s['position']} ({s['reason']})" for s in r["recommended"]) or NOT_FOUND), f"\n_{DISCLAIMER}_"])

def show_result(p, key):
    x, r, jd = p["extracted"], p["result"], p["jd"]
    st.markdown("### 1. Candidate Summary")
    st.write(f"**{x['name'] or 'ไม่ระบุชื่อ'}** · {x['email'] or ''} {x['phone'] or ''}")
    st.write(x["summary"] or NOT_FOUND)
    if x.get("ai_error"): st.error("AI เรียกไม่สำเร็จ จึงใช้โหมด rule-based แทน: " + x["ai_error"])
    if x.get("mode") == "rules": st.caption("⚠️ โหมด rule-based: ความเกี่ยวข้องของประสบการณ์/โปรเจกต์ประเมินจากคำสำคัญ ควรตรวจสอบกับ Resume")
    st.markdown("### 2. Education")
    if x["education"]: st.dataframe([{k: e.get(k) for k in ("level", "major", "institution", "gpa")} for e in x["education"]], hide_index=True, width="stretch")
    else: st.write(NOT_FOUND)
    st.markdown("### 3. Work Experience")
    for e in x["experience"]: st.write(f"- **{e['title']}** @ {e['company']} {('(' + e['period'] + ')') if e['period'] else ''}")
    if not x["experience"]: st.write(NOT_FOUND)
    st.markdown("### 4. Skills")
    st.write("**Hard skills:** " + (", ".join(x["hard_skills"]) or NOT_FOUND)); st.write("**Soft skills:** " + (", ".join(x["soft_skills"]) or NOT_FOUND))
    if x["projects"]: st.write("**Projects:** " + "; ".join(pj["name"] for pj in x["projects"]))
    if x["certificates"]: st.write("**Certificates / Training / Awards:** " + "; ".join(c["name"] for c in x["certificates"]))

    st.markdown("### 5. Matching Score")
    if r["score"] is None: st.warning(f"{CANT_CALC} (ไม่พบ Required Skills ใน JD) — แสดงตำแหน่งที่แนะนำแทน")
    else:
        c1, c2 = st.columns(2); c1.metric("Total", f"{fmt(r['score'])}/100"); c2.metric("ระดับ", f"{ICON[r['level']]} {r['level']}")
        st.caption("รวม = " + " + ".join(fmt(v["score"]) for v in r["parts"].values()) + f" = {fmt(r['score'])}  (คะแนนทุกช่องมาจากข้อมูลใน Resume และ JD เท่านั้น)")
    for k, v in r["parts"].items():
        with st.expander(f"{LABELS[k]} — {fmt(v['score'])}/{v['max']}", expanded=True):
            st.progress(min(v["score"] / v["max"], 1.0))
            if "rows" not in v:  # ข้อมูลที่บันทึกด้วยเวอร์ชันเก่า
                for n in v.get("notes", []): st.write("• " + n)
                continue
            st.caption("วิธีคิด: " + v["formula"])
            for w in v["rows"]:
                st.markdown(f"{mark(w)} **{w['label']}** · {fmt(w['score'])}/{fmt(w['max'])} — {w['why']}")
                if w.get("evidence"): st.caption(f"หลักฐานใน Resume: “{w['evidence']}”")
    st.caption("หัวข้อที่ JD ไม่ระบุเกณฑ์จะได้ 0 คะแนนตามเกณฑ์")

    st.markdown("### 6. Recommended Positions")
    for i in r["recommended"]: st.write(f"- **{i['position']}** — {i['reason']}")
    if not r["recommended"]: st.write(NOT_FOUND)
    st.info(DISCLAIMER)
    st.download_button("⬇️ ดาวน์โหลดรายงาน (.md)", report_md(p), f"report_{x['name']}.md", key=f"dl{key}")

st.title("🧑‍💼 TalentAI Screener")
st.caption("ช่วย HR คัดกรอง Resume เบื้องต้น — ไม่ใช่ผู้ตัดสินใจรับเข้าทำงาน")
t_an, t_db = st.tabs(["🔍 วิเคราะห์ผู้สมัคร", f"🗄️ ฐานข้อมูล ({len(db.list_all())})"])

with t_an:
    st.write("ตัวอย่างทดสอบ:")
    for col, name in zip(st.columns(6), DEMOS): col.button(name, on_click=load_demo, args=(name,))
    jc, dc = st.columns([1, 2])
    with jc:
        st.subheader("1. Job Description")
        st.text_input("ชื่อตำแหน่ง", key="jd_title")
        a, b = st.columns(2)
        a.number_input("ประสบการณ์ที่ต้องการ (ปี, 0 = ไม่ระบุ)", 0.0, step=1.0, key="jd_exp")
        b.number_input("GPA ขั้นต่ำ (0 = ไม่ระบุ)", 0.0, 4.0, step=0.1, key="jd_gpa")
        st.text_input("Required Skills (คั่นด้วย , — เว้นว่าง = ดึงจาก JD)", key="jd_skills")
        st.selectbox("ระดับการศึกษาที่ต้องการ", EDU_OPTIONS, key="jd_edu")
        st.text_input("สาขาวิชาที่ต้องการ (คั่นด้วย ,)", key="jd_majors")
        st.text_input("คุณสมบัติอื่น ๆ (ภาษา/ใบรับรอง/เครื่องมือ คั่นด้วย ,)", key="jd_others")
        jdf = st.file_uploader("ไฟล์ JD (PDF/DOCX/TXT/รูป)", ["pdf", "docx", "txt", "png", "jpg", "jpeg"], key=f"jdf{st.session_state.upl}")
        st.text_area("รายละเอียด JD ฉบับเต็ม", height=120, key="jd_text")
    with dc:
        st.subheader("2. เอกสารผู้สมัคร")
        st.text_input("ชื่อผู้สมัคร (เว้นว่าง = ให้ AI อ่านจากเอกสาร)", key="cand_name")
        rc, tc = st.columns(2)
        rf = rc.file_uploader("Resume (PDF/DOCX/TXT/รูป)", ["pdf", "docx", "txt", "png", "jpg", "jpeg"], key=f"rf{st.session_state.upl}")
        rc.text_area("หรือวางข้อความ Resume", height=260, key="resume_text")
        tf = tc.file_uploader("Transcript (ไม่บังคับ — เสริมข้อมูลการศึกษา)", ["pdf", "docx", "txt", "png", "jpg", "jpeg"], key=f"tf{st.session_state.upl}")
        tc.text_area("หรือวางข้อความ Transcript", height=260, key="transcript_text")

    b1, b2 = st.columns([4, 1])
    b2.button("🧹 ล้างข้อมูล", on_click=clear_all, width="stretch")
    if b1.button("✨ วิเคราะห์ Resume", type="primary", width="stretch"):
        try:
            with st.spinner("AI กำลังอ่านเอกสาร..."):
                ss = st.session_state
                resume = read_upload(as_upload(rf)) if rf else ss.resume_text
                transcript = read_upload(as_upload(tf)) if tf else ss.transcript_text
                if not resume.strip(): raise ValueError("กรุณาใส่ Resume")
                jd_text = read_upload(as_upload(jdf)) if jdf else ss.jd_text
                skills = split(ss.jd_skills) or (skills_from_jd(jd_text) if jd_text.strip() else [])
                jd = {"title": ss.jd_title, "min_exp": ss.jd_exp, "skills": skills, "edu_level": ss.jd_edu, "majors": split(ss.jd_majors),
                      "min_gpa": ss.jd_gpa, "others": split(ss.jd_others), "text": jd_text}
                ex = extract_ai(resume, transcript, jd)
                if ss.cand_name: ex["name"] = ss.cand_name
                ss.current = {"extracted": ex, "result": score_candidate(ex, jd, resume + "\n" + transcript), "jd": jd}
        except Exception as e:
            st.error(str(e) if isinstance(e, ValueError) else f"เกิดข้อผิดพลาด: {e}")

    if "current" in st.session_state:
        st.divider(); p = st.session_state.current; show_result(p, "cur")
        if st.button("💾 บันทึกลงฐานข้อมูล"):
            db.add(p["extracted"]["name"] or "ไม่ระบุชื่อ", p["jd"]["title"], p["extracted"], p["result"], p["jd"])
            st.toast("บันทึกแล้ว"); st.rerun()

with t_db:
    f1, f2 = st.columns([2, 1])
    q = f1.text_input("ค้นหาชื่อ / ตำแหน่ง"); sf = f2.selectbox("สถานะ", ["ทั้งหมด"] + STATUSES)
    rows = db.list_all(q, "" if sf == "ทั้งหมด" else sf)
    top = st.container()
    if not rows: st.info("ยังไม่มีข้อมูลผู้สมัคร")
    for c in rows:
        a, b, d, e, s, v, x = st.columns([1.2, 2, 2, 1.4, 2, 1, 1])
        a.write(c["created"]); b.write(f"**{c['name']}**"); d.write(c["role"])
        e.write(f"{ICON.get(c['level'], '⚪')} {c['score']:g}%" if c["score"] is not None else "⚪ -")
        new = s.selectbox("สถานะ", STATUSES, STATUSES.index(c["status"]), key=f"s{c['id']}", label_visibility="collapsed")
        if new != c["status"]: db.set_status(c["id"], new); st.toast("อัปเดตสถานะแล้ว")
        if v.button("ดู", key=f"v{c['id']}"): st.session_state.view_id = c["id"]
        if x.button("ลบ", key=f"x{c['id']}"): db.delete(c["id"]); st.session_state.pop("view_id", None); st.rerun()
    ex_rows = db.export_rows(q, "" if sf == "ทั้งหมด" else sf)
    if ex_rows:
        with top:
            today = datetime.date.today().isoformat(); d1, d2, d3 = st.columns([1, 1, 4])
            d1.download_button("⬇️ CSV", to_csv(ex_rows), f"candidates_{today}.csv", "text/csv", width="stretch")
            d2.download_button("⬇️ Excel", to_xlsx(ex_rows), f"candidates_{today}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
            d3.caption(f"ส่งออก {len(ex_rows)} รายการตามตัวกรองที่เลือก (รวมคะแนนรายช่อง ทักษะที่พบ/ไม่พบ และสถานะ)")
    if vid := st.session_state.get("view_id"):
        rec = db.get(vid)
        if rec: st.divider(); show_result(rec["payload"], f"db{vid}")

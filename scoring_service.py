"""คำนวณ Matching Score ตามเกณฑ์ใน knowledge.py — ทุกคะแนนมี "แถวเหตุผล" (rows) ที่รวมกันได้คะแนนของช่องนั้นพอดี"""
from knowledge import WEIGHTS as W, EDU_RANK, NOT_FOUND, CANT_CALC, SKILL_MISSING
ORDER = {"direct": 3, "partial": 2, "minor": 1}
LV = {v: k for k, v in EDU_RANK.items()}
TH = {"direct": "ตรงโดยตรง", "partial": "เกี่ยวข้องบางส่วน", "minor": "เกี่ยวข้องเล็กน้อย", "none": "ไม่เกี่ยวข้อง", "unknown": "ไม่สามารถประเมินได้"}

def norm(s): return " ".join(str(s).lower().split())
def has(text, s): return bool(s) and norm(s) in norm(text)
def best(items): return max(items, key=lambda i: ORDER.get(i.get("relevance", "unknown"), 0), default=None)
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None
def R(label, score, mx, why, evidence=None):
    return {"label": label, "score": round(score, 4), "max": round(mx, 4), "why": why, "evidence": (evidence or "")[:140]}
def P(rows, mx, formula): return {"score": round(sum(r["score"] for r in rows), 2), "max": mx, "formula": formula, "rows": rows}

def score_candidate(ex, jd, text):
    req = jd["skills"]; parts = {}; matched, missing = [], []

    # 1) Skills 40 — ทักษะละเท่าๆ กัน ต้องระบุชัดเจนใน Resume (ห้ามอนุมาน)
    per = 40 / len(req) if req else 0; rows = []
    for s in req:
        ev = next((l.strip() for l in text.splitlines() if has(l, s)), None)
        if ev: matched.append({"skill": s, "evidence": ev}); rows.append(R(s, per, per, "พบทักษะนี้ระบุชัดเจนใน Resume", ev))
        else: missing.append(s); rows.append(R(s, 0, per, SKILL_MISSING))
    parts["skills"] = P(rows or [R("Required Skills", 0, 40, CANT_CALC + " (JD ไม่มี Required Skills)")], 40,
        f"(พบ {len(matched)} ÷ ทั้งหมด {len(req)}) × 40 = {40 * len(matched) / len(req):.2f}" if req else CANT_CALC)

    # 2) Experience 25
    exps = ex["experience"]; b = best(exps)
    ev = f"{b.get('title', '')} @ {b.get('company', '')} {b.get('period', '')}".strip() if b and b.get("relevance") in ORDER else None
    if jd["min_exp"] > 0:
        ry = num(ex.get("relevant_years")); f = "min(ปีที่เกี่ยวข้อง ÷ ปีที่ JD ต้องการ, 1) × 25"
        if ry is None: row = R("ปีประสบการณ์ที่เกี่ยวข้อง", 0, 25, f"{NOT_FOUND}: ไม่พบปีประสบการณ์ที่เกี่ยวข้องใน Resume (JD ต้องการ {jd['min_exp']:g} ปี) → 0")
        else:
            ratio = min(ry / jd["min_exp"], 1)
            row = R("ปีประสบการณ์ที่เกี่ยวข้อง", ratio * 25, 25, f"พบประสบการณ์ที่เกี่ยวข้อง {ry:g} ปี เทียบกับที่ JD ต้องการ {jd['min_exp']:g} ปี → min({ry:g} ÷ {jd['min_exp']:g}, 1) = {ratio:.2f} → {ratio:.2f} × 25", ev)
    else:
        f = "JD ไม่ระบุจำนวนปี ใช้ความเกี่ยวข้อง: ตรง=25 / บางส่วน=15 / เล็กน้อย=5 / ไม่เกี่ยว=0"
        r = b.get("relevance", "unknown") if b else None
        row = R("ความเกี่ยวข้องของประสบการณ์", {"direct": 25, "partial": 15, "minor": 5}.get(r, 0), 25,
                f"{NOT_FOUND}: ไม่พบประสบการณ์ทำงานใน Resume → 0" if not b else f"ประสบการณ์ที่เกี่ยวข้องที่สุดอยู่ระดับ “{TH.get(r, r)}”", ev)
    parts["experience"] = P([row], 25, f)

    # 3) Education 15 = ระดับ 7 + สาขา 5 + อื่นๆ(GPA) 3
    edu = ex["education"]; cand = max((EDU_RANK.get(e.get("level", ""), 0) for e in edu), default=0); rq = EDU_RANK.get(jd["edu_level"], 0)
    lv_ev = next((e.get("evidence", "") for e in edu if EDU_RANK.get(e.get("level", ""), 0) == cand), "") if cand else ""
    if not rq: r1 = R("ระดับการศึกษา", 0, 7, "JD ไม่ระบุระดับการศึกษา จึงไม่มีเกณฑ์เทียบ → 0")
    elif not cand: r1 = R("ระดับการศึกษา", 0, 7, f"{NOT_FOUND}: ไม่พบระดับการศึกษาใน Resume (JD ต้องการ {jd['edu_level']}) → 0")
    elif cand >= rq: r1 = R("ระดับการศึกษา", 7, 7, f"ผู้สมัครจบ{LV[cand]} ตรงหรือสูงกว่าที่ JD ต้องการ ({jd['edu_level']}) → เต็ม", lv_ev)
    elif cand == rq - 1: r1 = R("ระดับการศึกษา", 3.5, 7, f"ผู้สมัครจบ{LV[cand]} ต่ำกว่าที่ JD ต้องการ ({jd['edu_level']}) หนึ่งระดับ → ตรงบางส่วน ได้ครึ่งหนึ่ง", lv_ev)
    else: r1 = R("ระดับการศึกษา", 0, 7, f"ผู้สมัครจบ{LV[cand]} ต่ำกว่าที่ JD ต้องการ ({jd['edu_level']}) เกินหนึ่งระดับ → 0", lv_ev)
    mm = ex.get("major_match", "unknown"); majors = ", ".join(jd["majors"]); cm = ", ".join(e["major"] for e in edu if e.get("major"))
    if not jd["majors"]: r2 = R("สาขาวิชา", 0, 5, "JD ไม่ระบุสาขาวิชา จึงไม่มีเกณฑ์เทียบ → 0")
    else:
        sc, why = {"match": (5, f"สาขาของผู้สมัครตรงกับที่ JD ต้องการ ({majors}) → เต็ม"), "partial": (2.5, f"สาขาของผู้สมัครตรงบางส่วนกับที่ JD ต้องการ ({majors}) → ครึ่งหนึ่ง"),
                   "none": (0, f"สาขาของผู้สมัครไม่ตรงกับที่ JD ต้องการ ({majors}) → 0")}.get(mm, (0, f"{NOT_FOUND}: ไม่พบสาขาวิชาใน Resume → 0"))
        r2 = R("สาขาวิชา", sc, 5, why, cm)
    gpas = [e["gpa"] for e in edu if e.get("gpa") is not None]
    if jd["min_gpa"] <= 0: r3 = R("คุณสมบัติการศึกษาอื่น ๆ (GPA)", 0, 3, "JD ไม่ระบุ GPA ขั้นต่ำ จึงไม่มีเกณฑ์เทียบ → 0")
    elif not gpas: r3 = R("คุณสมบัติการศึกษาอื่น ๆ (GPA)", 0, 3, f"{NOT_FOUND}: ไม่พบ GPA ใน Resume (ไม่อนุมานเอง) → 0")
    else:
        ok = max(gpas) >= jd["min_gpa"]
        r3 = R("คุณสมบัติการศึกษาอื่น ๆ (GPA)", 3 if ok else 0, 3, f"GPA {max(gpas):.2f} {'ผ่าน' if ok else 'ต่ำกว่า'}เกณฑ์ขั้นต่ำ {jd['min_gpa']:g} → {'เต็ม' if ok else '0'}")
    parts["education"] = P([r1, r2, r3], 15, "ระดับการศึกษา 7 + สาขาวิชา 5 + คุณสมบัติด้านการศึกษาอื่น ๆ 3")

    # 4) Projects 6 + Certificates 4
    def rel_row(label, items, full, key):
        b = best(items)
        if not b: return R(label, 0, full, f"{NOT_FOUND}: ไม่พบ{label}ใน Resume → 0")
        r = b.get("relevance", "unknown")
        sc = {"direct": full, "partial": full / 2, "minor": 1}.get(r, 0)
        return R(label, sc, full, f"รายการที่เกี่ยวข้องที่สุดอยู่ระดับ “{TH.get(r, r)}” (ตรง={full:g} / บางส่วน={full / 2:g} / เล็กน้อย=1 / ไม่เกี่ยว=0)", b.get(key, ""))
    parts["projects_certs"] = P([rel_row("Projects", ex["projects"], 6, "name"), rel_row("Certificates / Training / Awards", ex["certificates"], 4, "name")], 10,
                                "Projects 6 + Certificates/Training/Awards 4")

    # 5) Other 10 — ต้องมีหลักฐานที่คัดลอกจาก Resume จริง
    oth = jd["others"]; per = 10 / len(oth) if oth else 0; rows = []
    for r in oth:
        e = (ex.get("other_found") or {}).get(r, "")
        rows.append(R(r, per, per, "พบหลักฐานใน Resume", e) if has(text, e) else R(r, 0, per, "ไม่พบหลักฐานที่ตรวจย้อนกลับได้ใน Resume"))
    nf = sum(1 for x in rows if x["score"] > 0)
    parts["other"] = P(rows or [R("คุณสมบัติอื่น ๆ", 0, 10, f"{NOT_FOUND}: JD ไม่ระบุคุณสมบัติอื่น ๆ → 0")], 10,
                       f"(พบ {nf} ÷ ทั้งหมด {len(oth)}) × 10 = {10 * nf / len(oth):.2f}" if oth else f"{NOT_FOUND} (JD ไม่ระบุ)")

    total = round(sum(v["score"] for v in parts.values()), 2) if req else None  # ไม่มี Required Skills = คำนวณไม่ได้
    level = "N/A" if total is None else "High" if total >= 75 else "Moderate" if total >= 55 else "Low"
    return {"score": total, "level": level, "parts": parts, "matched": matched, "missing": missing, "recommended": ex.get("recommended_positions", [])}

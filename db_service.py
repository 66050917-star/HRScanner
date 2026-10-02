"""ฐานข้อมูลผู้สมัคร (SQLite)"""
import sqlite3, json, datetime
DB = "candidates_v2.db"

def _c():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    with _c() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT, name TEXT, role TEXT, gpax REAL, score INTEGER, level TEXT,
            status TEXT DEFAULT 'Pending', payload TEXT)""")

def add(name, role, extracted, result, jd):
    with _c() as c:
        cur = c.execute("INSERT INTO candidates(created,name,role,gpax,score,level,payload) VALUES(?,?,?,?,?,?,?)",
            (datetime.date.today().isoformat(), name, role, extracted.get("gpax"), result["score"], result["level"],
             json.dumps({"extracted": extracted, "result": result, "jd": jd}, ensure_ascii=False)))
        return cur.lastrowid

def list_all(q="", status=""):
    sql, args = "SELECT id,created,name,role,gpax,score,level,status FROM candidates WHERE (name LIKE ? OR role LIKE ?)", [f"%{q}%"] * 2
    if status: sql += " AND status=?"; args.append(status)
    with _c() as c: return [dict(r) for r in c.execute(sql + " ORDER BY id DESC", args)]

def get(i):
    with _c() as c:
        r = c.execute("SELECT * FROM candidates WHERE id=?", (i,)).fetchone()
    if not r: return None
    d = dict(r); d["payload"] = json.loads(d["payload"]); return d

def set_status(i, s):
    with _c() as c: c.execute("UPDATE candidates SET status=? WHERE id=?", (s, i))

def delete(i):
    with _c() as c: c.execute("DELETE FROM candidates WHERE id=?", (i,))

HEADERS = ["วันที่สมัคร", "ชื่อผู้สมัคร", "ตำแหน่งที่สมัคร", "คะแนนรวม (100)", "ระดับ", "Skills (40)", "Experience (25)",
           "Education (15)", "Projects/Certificates (10)", "คุณสมบัติอื่น ๆ (10)", "ทักษะที่พบ", "ทักษะที่ไม่พบ", "สถานะ"]

def export_rows(q="", status=""):
    """แถวสำหรับส่งออก CSV/Excel (ตามตัวกรองที่เลือก) — ดึงคะแนนรายช่องจากผลวิเคราะห์ที่บันทึกไว้"""
    out = []
    for c in list_all(q, status):
        r = ((get(c["id"]) or {}).get("payload") or {}).get("result") or {}
        part = lambda k: (r.get("parts", {}).get(k) or {}).get("score")
        out.append(dict(zip(HEADERS, [c["created"], c["name"], c["role"], c["score"], c["level"], part("skills"), part("experience"),
            part("education"), part("projects_certs"), part("other"), ", ".join(m.get("skill", "") for m in r.get("matched", [])),
            ", ".join(r.get("missing", [])), c["status"]])))
    return out

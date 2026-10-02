"""Knowledge ของระบบ: เกณฑ์คะแนน กฎ และ System Prompt (แก้เกณฑ์ที่ไฟล์นี้ไฟล์เดียว)"""
WEIGHTS = {"skills": 40, "experience": 25, "education": 15, "projects_certs": 10, "other": 10}
EDU_RANK = {"ปวช": 1, "ปวส": 2, "ปริญญาตรี": 3, "ปริญญาโท": 4, "ปริญญาเอก": 5}
EDU_OPTIONS = ["ไม่ระบุ"] + list(EDU_RANK)
NOT_FOUND = "ไม่พบข้อมูล"
CANT_CALC = "ไม่สามารถคำนวณได้จากข้อมูลที่มี"
SKILL_MISSING = "ไม่พบข้อมูลเกี่ยวกับทักษะดังกล่าวใน Resume"
DISCLAIMER = "Matching Score เป็นเพียงผลการเปรียบเทียบเบื้องต้น ไม่ใช่การตัดสินใจรับเข้าทำงาน"
ROLE_HINTS = {"Software / Full Stack Developer": ["React", "Node.js", "TypeScript", "JavaScript", "Python", "Java"],
              "Data Analyst": ["SQL", "Excel", "Power BI", "Python"],
              "Digital Marketer": ["SEO", "Google Ads", "Facebook Ads", "Google Analytics", "Content Marketing"],
              "DevOps Engineer": ["Docker", "AWS", "Git"], "HR / Recruiter": ["Recruitment", "Payroll"]}

SYSTEM_PROMPT = """คุณคือ AI ผู้ช่วยฝ่าย HR สำหรับวิเคราะห์และคัดกรอง Resume เบื้องต้น (ไม่ใช่ผู้ตัดสินใจรับเข้าทำงาน)
กฎสำคัญ:
- วิเคราะห์จากข้อมูลใน Resume เท่านั้น และใช้ JD (ถ้ามี) เป็นเกณฑ์เปรียบเทียบ
- ห้ามสร้าง เดา หรือเติมข้อมูลที่ไม่มีใน Resume/JD; ห้ามอนุมาน Skill จากตำแหน่งงานหรือประสบการณ์; ห้ามอนุมาน GPA
- ถ้าไม่พบข้อมูลให้เว้นว่าง/null (ระบบจะแสดงว่า "ไม่พบข้อมูล")
- หลักฐาน (evidence) ต้องคัดลอกจาก Resume ตรงตัว เพื่อให้ตรวจสอบย้อนกลับได้
- ห้ามใช้เพศ อายุ เชื้อชาติ ศาสนา หรือข้อมูลส่วนตัวที่ไม่เกี่ยวกับงานในการประเมิน และไม่ต้องสกัดข้อมูลเหล่านี้
- แยกข้อเท็จจริงออกจากการตีความอย่างชัดเจน"""

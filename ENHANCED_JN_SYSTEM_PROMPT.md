# 🚀 AI-Powered JN Resolution System (Enhanced Build Prompt)

from the existing project we have right now please do some mapping and re-align with the new infrastructure was propose below

---

## 🧠 PROJECT BACKGROUND

The AI-Powered JN Resolution System is designed for Malaysia’s Ministry of Education (MOE) to support Jemaah Nazir (JN) in detecting discrepancies between school-reported data and actual inspection findings.

### Problem:
- Schools submit self-reported data
- Actual inspection differs
- No automated detection
- Manual review slow and inconsistent

### Objective:
Build a smart governance system that:
1. Extracts data
2. Compares discrepancies
3. Calculates index
4. Triggers actions
5. Supports multi-device access

---

## ⚙️ SYSTEM DESIGN

### 3-Agent Architecture
INPUT → Extract → Compare → Decide → OUTPUT

---

## 🧱 CORE REQUIREMENTS

### ✅ Cross-Device Support (PWA Concept)
- Accessible via Laptop, Tablet, Mobile
- Responsive Streamlit layout
- App behaves like web app (installable optional via browser)

---

### ✅ Authentication & Authorization

#### Domain Restriction:
Only allow login from:
- @moe.gov.my
- @moe-dl.edu.my

#### Role-Based Access Control (RBAC):

| Role | Description | Access |
|------|------------|--------|
| Admin | Full system control | All data + manage users |
| Peneraju Sektor | Sector leader | View + high-level decision |
| Penyelaras JN | Inspector coordinator | Input + review inspection data |

---

## 🔹 Agent A – Extract
- Input: CSV (initial)
- Future: API + PDF

---

## 🔹 Agent B – Compare
index = weighted gap calculation

---

## 🔹 Agent C – Decide
- Auto action based on index

---

## 🖥️ SYSTEM (STREAMLIT FULLSTACK)

### UI Pages:
1. Login Page
2. Dashboard Page
3. Upload Page
4. Results Page

---

## 📊 FEATURES

- Secure login (email validation)
- Role-based UI display
- CSV upload
- Data processing
- Discrepancy index
- Risk classification
- Dashboard (charts + tables)

---

## 🧱 PROJECT STRUCTURE

jn-ai-system/
├── app.py
├── auth/
│   └── auth.py
├── agents/
│   ├── extract.py
│   ├── compare.py
│   ├── decide.py
├── pages/
│   ├── login.py
│   ├── dashboard.py
│   ├── upload.py
├── utils/
│   └── helpers.py
├── .env
├── .gitignore
├── requirements.txt
└── README.md

---

## ⚙️ ENV SETUP

python -m venv venv

Activate:
venv\Scripts\activate

---

## ✅ .env
OPENAI_API_KEY=your_key
AUTH_DOMAIN_1=@moe.gov.my
AUTH_DOMAIN_2=@moe-dl.edu.my

---

## ✅ .gitignore
venv/
.env
__pycache__/

---

## ✅ requirements.txt
streamlit
pandas
python-dotenv

---

## 📈 SAMPLE CSV

school,cleanliness_reported,cleanliness_actual,ict_reported,ict_actual,discipline_reported,discipline_actual
SMK A,90,28,85,30,80,55

---

## 🚀 RUN
pip install -r requirements.txt
streamlit run app.py

---

## ✅ SUMMARY

- Cross-device ready
- Secured with RBAC
- 3-agent AI system
- Ready for scaling

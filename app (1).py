# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION, RBAC Login
Format: Lessons Learned Register (Cyberpunk UI Edition)
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime
import os
import io
import re

# ==============================================================================
# 1. OPTIONAL IMPORTS (DOCUMENT PARSING, GDRIVE, & GEMINI)
# ==============================================================================
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

try:
    import google.generativeai as genai
    import json
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==============================================================================
# 2. CORE CONFIGURATION
# ==============================================================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_enterprise.db")

USER_CREDENTIALS = {
    "pm_user": {"password": "password123", "role": "Uploader"},
    "pmo_reviewer": {"password": "password123", "role": "Reviewer"},
    "guest": {"password": "password123", "role": "Viewer"}
}

PMO_SATKER_OPTIONS = [
    "Project Management Office",
    "Mine Development",
    "Logistic & Infrastructure Development",
    "Energy Business Development",
    "Downstream Business Development"
]

ALL_DEPARTMENTS_OPTIONS = [
    "Corporate Secretary", "Internal Audit", "Corporate Management System & Performance",
    "Project Management Office", "Mine Development", "Logistic & Infrastructure Development", "Energy Business Development", "Downstream Business Development",
    "Budgeting & Accounting", "Corporate Finance", "Portfolio Management", "Information Technology", "Risk Management",
    "Strategic Human Capital", "Human Capital Operations", "Asset management & Supporting Civil Infrastructure", "Legal & Regulatory Affairs", "Sustainability", "Procurement",
    "Production & Operation Optimization", "Corporate SHE", "Planning", "Mine Planning", "Exploration",
    "Tanjung Enim Mining Site", "Mining", "Coal Handling & Transportation", "Environmental Management & Mining Support", "Operational Services", "Coal Handling Facility & Main Mining Equipment Maintenance", "Production & Mining Support Equipment Maintenance",
    "Maintenance", "Ombilin Mining Site",
    "Commercial", "Marketing", "Distribution", "Tarahan Port", "Kertapati Port",
    "Lainnya"
]

DIVISION_FOLDERS = {
    "Human Resources (HR)": "14Q949Rt_UNyEKYenuneBZXlgzznUMOnY",
    "Information Technology (IT)": "1-bPwqpCeY4yRtdGpzfZ4UmjmQKSTk7AV",
    "Finance": "1Pdkc9LD7XFkFhioznFWIZozp8lyqb_q-",
    "Operations": "1kVAq06Jep0dLL-dTOpDLqtxR3iugcB4F",
    "Lainnya": "1Pdkc9LD7XFkFhioznFWIZozp8lyqb_q-" 
}

TIPE_DIVISI_OPTIONS = list(DIVISION_FOLDERS.keys())
KATEGORI_OPTIONS = ["Area perbaikan", "Apa yang berhasil", "Apa yang tidak berhasil"]

KEYWORDS_DESKRIPSI = ["isu", "masalah", "kendala", "terhambat", "deskripsi"]
KEYWORDS_DAMPAK = ["dampak", "akibat", "menyebabkan", "tertunda"]
KEYWORDS_PENCEGAHAN = ["pencegahan", "solusi", "rekomendasi", "memilih"]
KEYWORDS_TANTANGAN = ["tantangan", "risiko", "kemungkinan", "hambatan"]

# --- PLOTLY CYBERPUNK THEME ---
def create_cyberpunk_theme():
    font_family = "'Rajdhani', sans-serif"
    template = pio.templates["plotly_dark"]
    template.layout.font = dict(family=font_family, color="#e0e0e0", size=14)
    template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    template.layout.colorway = ["#00f3ff", "#bc13fe", "#ff003c", "#fcee0a", "#00ff66"]
    template.layout.xaxis.showgrid = False
    template.layout.yaxis.showgrid = True
    template.layout.yaxis.gridcolor = "rgba(0, 243, 255, 0.1)"
    template.layout.xaxis.gridcolor = "rgba(0, 243, 255, 0.1)"
    pio.templates["cyberpunk"] = template
    pio.templates.default = "cyberpunk"

# ==============================================================================
# 3. GOOGLE DRIVE UPLOADER 
# ==============================================================================
def upload_to_gdrive(file_bytes_io, filename, target_folder_id):
    if not GDRIVE_AVAILABLE: return None
    try:
        scopes = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else: return None

        service = build('drive', 'v3', credentials=creds)
        file_bytes_io.seek(0)
        media = MediaIoBaseUpload(file_bytes_io, mimetype='application/octet-stream', resumable=True)
        file_metadata = {'name': filename, 'parents': [target_folder_id]}

        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink', supportsAllDrives=True).execute()
        file_id = uploaded_file.get('id')
        file_link = uploaded_file.get('webViewLink')
        
        try:
            service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}, supportsAllDrives=True).execute()
        except Exception: pass
        return file_link
    except Exception as e:
        st.error(f"Gagal mengunggah ke GDrive: {e}")
        return None

# ==============================================================================
# 4. DATA REPOSITORY
# ==============================================================================
class KnowledgeRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lessons_learned (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nama_proyek TEXT NOT NULL, 
                manajer_proyek TEXT, 
                project_owner TEXT,
                related_department TEXT,
                kategori TEXT, 
                tipe TEXT, 
                deskripsi_isu TEXT, 
                dampak_isu TEXT, 
                aktivitas_pencegahan TEXT,
                tantangan TEXT,
                status TEXT DEFAULT 'Pending Review', 
                upload_date TEXT,
                reviewer_notes TEXT DEFAULT '',
                gdrive_link TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def fetch_all(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM lessons_learned ORDER BY id DESC", conn)
        conn.close()
        return df

    def insert(self, data):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO lessons_learned 
                (nama_proyek, manajer_proyek, project_owner, related_department, kategori, tipe, deskripsi_isu, dampak_isu, aktivitas_pencegahan, tantangan, status, upload_date, gdrive_link) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Review', ?, ?)
            """, (
                data['nama_proyek'], data['manajer_proyek'], data['project_owner'], data['related_department'],
                data['kategori'], data['tipe'], data['deskripsi_isu'], data['dampak_isu'], 
                data['aktivitas_pencegahan'], data['tantangan'], datetime.now().strftime("%d %B %Y"), data.get('gdrive_link', '')
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e: 
            st.error(f"DB Insert Error: {e}")
            return False

    def update_status(self, record_id, new_status, notes=""):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE lessons_learned SET status = ?, reviewer_notes = ? WHERE id = ?", (new_status, notes, record_id))
            conn.commit()
            conn.close()
            return True
        except Exception: return False

    def resubmit_record(self, record_id, data):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE lessons_learned 
                SET nama_proyek = ?, manajer_proyek = ?, project_owner = ?, related_department = ?, kategori = ?, tipe = ?, deskripsi_isu = ?, dampak_isu = ?, aktivitas_pencegahan = ?, tantangan = ?, gdrive_link = ?, status = 'Pending Review' 
                WHERE id = ?
            """, (
                data['nama_proyek'], data['manajer_proyek'], data['project_owner'], data['related_department'],
                data['kategori'], data['tipe'], data['deskripsi_isu'], data['dampak_isu'], 
                data['aktivitas_pencegahan'], data['tantangan'], data.get('gdrive_link', ''), record_id
            ))
            conn.commit()
            conn.close()
            return True
        except Exception: return False

    def delete_record(self, record_id):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM lessons_learned WHERE id = ?", (record_id,))
            conn.commit()
            conn.close()
            return True
        except Exception: return False

@st.cache_resource
def get_repository():
    return KnowledgeRepository(DB_PATH)

# ==============================================================================
# 5. AI GENERATIVE ENGINE (GEMINI INTEGRATION)
# ==============================================================================
def parse_document(file_bytes, filename) -> str:
    if not file_bytes: return ""
    try:
        filename = filename.lower()
        if filename.endswith(".pdf") and PDFPLUMBER_AVAILABLE:
            with pdfplumber.open(file_bytes) as pdf: return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif filename.endswith(".pdf") and PYPDF_AVAILABLE:
            reader = PdfReader(file_bytes)
            return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        elif filename.endswith(".docx") and DOCX_AVAILABLE:
            document = docx.Document(file_bytes)
            return "\n".join([p.text for p in document.paragraphs if p.text.strip()])
        elif filename.endswith(".txt"):
            return file_bytes.read().decode("utf-8", errors="ignore")
    except Exception: pass
    return ""

def extract_knowledge(text: str) -> dict:
    res = {"deskripsi_isu": "", "dampak_isu": "", "aktivitas_pencegahan": "", "tantangan": ""}
    if not text: return res

    if GEMINI_AVAILABLE and "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Anda adalah analis Lessons Learned Register profesional di industri pertambangan/enterprise.
            Baca teks laporan di bawah ini dan rangkum menjadi 4 bagian spesifik.
            WAJIB balas HANYA dengan format JSON persis seperti ini:
            {{
                "deskripsi_isu": "Jelaskan masalah utama yang terjadi secara ringkas...",
                "dampak_isu": "Jelaskan apa akibat dari masalah tersebut...",
                "aktivitas_pencegahan": "Jelaskan tindakan korektif atau solusi...",
                "tantangan": "Jelaskan kemungkinan risiko atau hambatan..."
            }}
            TEKS DOKUMEN:
            {text[:15000]} 
            """
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```json"): clean_text = clean_text[7:]
            elif clean_text.startswith("```"): clean_text = clean_text[3:]
            if clean_text.endswith("```"): clean_text = clean_text[:-3]
            ai_data = json.loads(clean_text.strip())
            
            res["deskripsi_isu"] = ai_data.get("deskripsi_isu", "")
            res["dampak_isu"] = ai_data.get("dampak_isu", "")
            res["aktivitas_pencegahan"] = ai_data.get("aktivitas_pencegahan", "")
            res["tantangan"] = ai_data.get("tantangan", "")
            return res
        except Exception as e:
            st.error(f"❌ GEMINI GAGAL: {e}")
            
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s) > 15]
    def extract_by_keywords(kw_list):
        matched = [s for s in sentences if any(kw in s.lower() for kw in kw_list)]
        return " ".join(matched[:3])
    res["deskripsi_isu"] = extract_by_keywords(KEYWORDS_DESKRIPSI) or (" ".join(sentences[:2]) if sentences else "")
    res["dampak_isu"] = extract_by_keywords(KEYWORDS_DAMPAK)
    res["aktivitas_pencegahan"] = extract_by_keywords(KEYWORDS_PENCEGAHAN)
    res["tantangan"] = extract_by_keywords(KEYWORDS_TANTANGAN)
    return res

# ==============================================================================
# 6. UI COMPONENTS & CSS (CYBERPUNK THEME)
# ==============================================================================
def inject_cyberpunk_css():
    st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap](https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap)');
    
    :root {
        --bg-main: #050510;
        --neon-cyan: #00f3ff;
        --neon-cyan-dim: rgba(0, 243, 255, 0.2);
        --neon-purple: #bc13fe;
        --neon-purple-dim: rgba(188, 19, 254, 0.2);
        --neon-pink: #ff003c;
        --text-bright: #ffffff;
        --text-muted: #8892b0;
        --glass-bg: rgba(10, 15, 30, 0.65);
        --glass-border: rgba(0, 243, 255, 0.3);
    }

    /* Animated Grid Background */
    @keyframes moveGrid {
        0% { background-position: 0 0; }
        100% { background-position: 30px 30px; }
    }

    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-main) !important;
        background-image:
            linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px) !important;
        background-size: 30px 30px !important;
        animation: moveGrid 4s linear infinite;
        font-family: 'Rajdhani', sans-serif !important;
        color: var(--text-bright) !important;
    }

    p, label, li, div {
        font-family: 'Rajdhani', sans-serif;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Orbitron', sans-serif !important;
        color: var(--neon-cyan) !important;
        text-shadow: 0 0 10px var(--neon-cyan-dim);
    }

    /* Sticky Navbar / Sidebar Styling */
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="stSidebar"] {
        background-color: rgba(5, 5, 16, 0.9) !important;
        border-right: 1px solid var(--neon-purple-dim);
        box-shadow: 2px 0 15px rgba(188, 19, 254, 0.1);
        backdrop-filter: blur(10px);
    }
    [data-testid="collapsedControl"] {
        display: flex !important; visibility: visible !important;
        background-color: var(--glass-bg) !important;
        color: var(--neon-cyan) !important;
        border: 1px solid var(--neon-cyan) !important;
        border-radius: 8px !important;
        margin: 1rem !important; z-index: 100 !important;
        box-shadow: 0 0 10px var(--neon-cyan-dim) !important;
    }
    
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1200px !important; }
    
    /* Hero Section */
    .hero-text { 
        font-family: 'Orbitron', sans-serif !important; 
        font-size: 80px; 
        font-weight: 900; 
        line-height: 1; 
        color: var(--text-bright); 
        margin-bottom: 16px;
        text-transform: uppercase;
        text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-purple);
        letter-spacing: 2px;
    }
    .hero-sub { 
        font-size: 22px; 
        font-weight: 500; 
        color: var(--neon-cyan); 
        margin-bottom: 60px; 
        max-width: 700px; 
        line-height: 1.5;
        letter-spacing: 1px;
    }
    .section-title { 
        font-family: 'Orbitron', sans-serif !important; 
        font-size: 36px; 
        font-weight: 700; 
        margin-bottom: 32px; 
        color: var(--neon-cyan);
        text-transform: uppercase;
        text-shadow: 0 0 8px var(--neon-cyan-dim);
        border-bottom: 1px solid var(--neon-purple);
        padding-bottom: 10px;
    }

    /* Glassmorphism Cards & Expanders */
    .bento, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid var(--glass-border) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        border-radius: 12px !important;
        transition: all 0.3s ease !important;
        overflow: hidden;
    }
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover, [data-testid="stExpander"]:hover {
        border-color: var(--neon-cyan) !important;
        box-shadow: 0 0 15px var(--neon-cyan-dim), inset 0 0 10px var(--neon-purple-dim) !important;
        transform: translateY(-2px) !important;
    }

    /* Accordion Details */
    [data-testid="stExpander"] summary {
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        color: var(--neon-cyan) !important;
        padding: 16px !important;
        background-color: transparent !important;
        transition: background-color 0.2s ease, text-shadow 0.2s ease !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: rgba(0, 243, 255, 0.1) !important;
        text-shadow: 0 0 8px var(--neon-cyan) !important;
    }
    [data-testid="stExpanderDetails"] {
        padding: 24px !important;
        border-top: 1px dashed var(--neon-purple) !important;
        background: rgba(0, 0, 0, 0.2) !important;
    }

    /* KPI Cards */
    .kpi-big-val { font-family: 'Orbitron', sans-serif; font-size: 72px; font-weight: 900; line-height: 1; color: var(--neon-purple); text-shadow: 0 0 15px var(--neon-purple-dim);}
    .kpi-big-title { font-size: 18px; font-weight: 700; color: var(--neon-cyan); margin-top: 12px; text-transform: uppercase; letter-spacing: 2px;}
    .kpi-small-val { font-family: 'Orbitron', sans-serif; font-size: 48px; font-weight: 700; line-height: 1; color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple-dim);}
    .kpi-small-title { font-size: 16px; font-weight: 700; color: var(--text-muted); margin-top: 8px; text-transform: uppercase; letter-spacing: 1px;}
    
    /* Card Content Typography */
    .card-meta { font-size: 14px; font-weight: 600; color: var(--text-muted); margin-bottom: 24px;}
    .card-section { font-family: 'Orbitron', sans-serif; font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--neon-cyan); margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid var(--neon-cyan-dim); padding-bottom: 4px; letter-spacing: 1px;}
    .card-body { font-size: 16px; font-weight: 500; line-height: 1.6; color: var(--text-bright);}
    
    /* Neon Badges */
    .badge { display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 700; margin-right: 8px; text-transform: uppercase; letter-spacing: 1px; font-family: 'Orbitron', sans-serif;}
    .badge-status-Pending { background: transparent; color: #fcee0a; border: 1px solid #fcee0a; box-shadow: 0 0 5px rgba(252, 238, 10, 0.3);}
    .badge-status-Verified { background: transparent; color: #00ff66; border: 1px solid #00ff66; box-shadow: 0 0 5px rgba(0, 255, 102, 0.3);}
    .badge-status-NeedsRevision { background: transparent; color: #ff8800; border: 1px solid #ff8800; box-shadow: 0 0 5px rgba(255, 136, 0, 0.3);}
    .badge-status-Rejected { background: transparent; color: var(--neon-pink); border: 1px solid var(--neon-pink); box-shadow: 0 0 5px rgba(255, 0, 60, 0.3);}
    .badge-kategori { background: rgba(188, 19, 254, 0.1); color: var(--neon-purple); border: 1px solid var(--neon-purple); box-shadow: 0 0 5px var(--neon-purple-dim);}
    .badge-tipe { background: rgba(0, 243, 255, 0.1); color: var(--neon-cyan); border: 1px solid var(--neon-cyan); box-shadow: 0 0 5px var(--neon-cyan-dim);}
    
    /* GDrive Button */
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 8px; background-color: transparent; color: var(--neon-cyan) !important; padding: 8px 18px; border-radius: 4px; font-weight: 700; font-size: 14px; text-decoration: none !important; margin-top: 16px; transition: all 0.3s ease; border: 1px solid var(--neon-cyan); box-shadow: 0 0 5px var(--neon-cyan-dim); text-transform: uppercase; font-family: 'Orbitron', sans-serif;}
    .gdrive-link-btn:hover { background-color: var(--neon-cyan); color: var(--bg-main) !important; box-shadow: 0 0 15px var(--neon-cyan); transform: scale(1.02); }
    
    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { 
        background-color: rgba(5, 5, 16, 0.8) !important; 
        border: 1px solid var(--glass-border) !important; 
        border-radius: 4px !important; 
        padding: 14px 18px !important; 
        font-size: 16px; font-weight: 500; 
        color: var(--neon-cyan) !important; 
        transition: all 0.3s ease; 
        font-family: 'Rajdhani', sans-serif;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { 
        border-color: var(--neon-cyan) !important; 
        box-shadow: 0 0 10px var(--neon-cyan-dim), inset 0 0 5px var(--neon-cyan-dim) !important; 
    }
    
    /* Action Buttons (Glowing effect) */
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { 
        background-color: transparent !important; 
        color: var(--neon-cyan) !important; 
        border-radius: 4px !important; 
        padding: 12px 24px !important; 
        font-weight: 700 !important; 
        font-size: 16px !important; 
        border: 1px solid var(--neon-cyan) !important; 
        width: 100%; 
        transition: all 0.3s ease !important; 
        text-transform: uppercase;
        font-family: 'Orbitron', sans-serif !important;
        letter-spacing: 2px;
        box-shadow: 0 0 8px var(--neon-cyan-dim) !important;
        position: relative;
        overflow: hidden;
    }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { 
        background-color: var(--neon-cyan) !important; 
        color: var(--bg-main) !important; 
        box-shadow: 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan) !important; 
        transform: translateY(-2px); 
    }
    
    /* Role-based button coloring overrides */
    div[data-testid="stButton"] button:has(p:contains("Reject")) { border-color: var(--neon-pink) !important; color: var(--neon-pink) !important; box-shadow: 0 0 8px rgba(255, 0, 60, 0.3) !important;}
    div[data-testid="stButton"] button:has(p:contains("Reject")):hover { background: var(--neon-pink) !important; color: #fff !important; box-shadow: 0 0 20px var(--neon-pink) !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Verify")) { border-color: #00ff66 !important; color: #00ff66 !important; box-shadow: 0 0 8px rgba(0, 255, 102, 0.3) !important;}
    div[data-testid="stButton"] button:has(p:contains("Verify")):hover { background: #00ff66 !important; color: #000 !important; box-shadow: 0 0 20px #00ff66 !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Revision")) { border-color: #fcee0a !important; color: #fcee0a !important; box-shadow: 0 0 8px rgba(252, 238, 10, 0.3) !important;}
    div[data-testid="stButton"] button:has(p:contains("Revision")):hover { background: #fcee0a !important; color: #000 !important; box-shadow: 0 0 20px #fcee0a !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Delete")) { border-color: var(--text-muted) !important; color: var(--text-muted) !important;}
    div[data-testid="stButton"] button:has(p:contains("Delete")):hover { background: var(--text-muted) !important; color: #fff !important;}

    /* Sidebar Radio */
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 12px 20px; border-radius: 4px; font-size: 16px; font-weight: 700; color: var(--text-muted); transition: 0.3s; font-family: 'Orbitron', sans-serif; text-transform: uppercase;}
    div[role="radiogroup"] > label:hover { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple-dim); }
    div[role="radiogroup"] > label[data-checked="true"] { background-color: rgba(188, 19, 254, 0.1) !important; color: var(--neon-purple) !important; border-left: 4px solid var(--neon-purple); box-shadow: inset 5px 0 10px var(--neon-purple-dim);}
    
    [data-testid="stFileUploadDropzone"] { border-radius: 8px !important; border: 1px dashed var(--neon-purple) !important; background-color: rgba(188, 19, 254, 0.05) !important; }
    
    /* Cyberpunk Divider */
    .cyber-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
        margin: 20px 0;
        box-shadow: 0 0 10px var(--neon-cyan);
    }
    </style>
    """, unsafe_allow_html=True)

def render_big_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-big-val">{value}</div><div class="kpi-big-title">{title}</div></div>""", unsafe_allow_html=True)

def render_small_kpi(title, value):
    st.markdown(f"""<div class="bento" style="padding: 30px;"><div class="kpi-small-val">{value}</div><div class="kpi-small-title">{title}</div></div>""", unsafe_allow_html=True)

def render_knowledge_card_content(row):
    status_str = str(row['status']).replace(" Pending Review", "Pending").replace(" ", "")
    
    deskripsi = str(row['deskripsi_isu']).replace('\n', '<br>')
    dampak = str(row['dampak_isu']).replace('\n', '<br>')
    pencegahan = str(row['aktivitas_pencegahan']).replace('\n', '<br>')
    tantangan = str(row['tantangan']).replace('\n', '<br>')
    
    gdrive_link = row['gdrive_link'] if 'gdrive_link' in row.keys() and row['gdrive_link'] else ""
    gdrive_html = f"""<div style="margin-top: 24px;"><a href="{gdrive_link}" target="_blank" class="gdrive-link-btn">ACCESS SECURE FILE // GDRIVE</a></div>""" if gdrive_link else ""
    
    kat_badge = f"<span class='badge badge-kategori'>CAT: {row.get('kategori', 'Area perbaikan')}</span>"
    tipe_badge = f"<span class='badge badge-tipe'>DIR: {row.get('tipe', '-')}</span>"

    owner_text = row.get('project_owner', '-')
    dept_text = row.get('related_department', '-')

    card_html = f"""
    <div style="padding-bottom: 16px;">
        <div class="card-meta" style="margin-bottom: 16px;">
            <span style="color:var(--neon-cyan);">OP:</span> {row['manajer_proyek']} &nbsp;|&nbsp; 
            <span style="color:var(--neon-cyan);">OWNER:</span> {owner_text} &nbsp;|&nbsp; 
            <span style="color:var(--neon-cyan);">DEPT:</span> {dept_text} &nbsp;|&nbsp; 
            <span style="color:var(--neon-cyan);">TS:</span> {row['upload_date']}
        </div>
        <div style="margin-bottom: 24px;">
            <span class="badge badge-status-{status_str}">SYS_STATUS: {row['status']}</span>
            {kat_badge} {tipe_badge}
        </div>
        <div class="cyber-divider"></div>
        <div class="card-section" style="margin-top:0;">[01] DESKRIPSI ISU</div>
        <div class="card-body">{deskripsi}</div>
        <div class="card-section">[02] DAMPAK ISU</div>
        <div class="card-body">{dampak}</div>
        <div class="card-section">[03] AKTIVITAS PENCEGAHAN</div>
        <div class="card-body" style="font-weight: 600; color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan-dim);">{pencegahan}</div>
        <div class="card-section">[04] TANTANGAN TERUKUR</div>
        <div class="card-body">{tantangan}</div>
        {gdrive_html}
    </div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="SYS_NO_DATA", subtitle="Basis data kosong. Inisialisasi entri pertama untuk memulai indeks pengetahuan."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 80px 40px;"><div class="section-title" style="margin-bottom: 16px; font-size: 32px; border:none;">{title}</div><div class="card-body" style="color: var(--text-muted); font-family:'Orbitron', sans-serif;">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_login():
    st.markdown("""
        <div style="text-align: center; margin-top: 10vh;">
            <div class="hero-text" style="font-size: 64px; margin-bottom: 10px;">NEURAL_ACCESS_PORT</div>
            <div class="hero-sub" style="margin-bottom: 40px; margin-left: auto; margin-right: auto;">AUTHENTICATE TO ACCESS PTBA LESSONS LEARNED MAINFRAME</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; color:var(--neon-cyan); font-family:Orbitron; margin-bottom: 20px; letter-spacing: 2px;'>CREDENTIALS REQUIRED</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="ENTER USER ID...")
            password = st.text_input("Password", type="password", placeholder="ENTER PASSWORD...")
            
            st.write("")
            if st.button("INITIALIZE LOGIN SEQUENCE"):
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user["role"]
                    st.rerun()
                else:
                    st.error("ACCESS DENIED: Invalid Credentials")

def view_dashboard(repo):
    st.markdown("""
        <div class="hero-text">PT BUKIT ASAM<br>KMS_CORE</div>
        <div class="hero-sub">REGISTER AND TRANSFORM OPERATIONAL ANOMALIES INTO ORGANIZATIONAL STRATEGIC ASSETS.</div>
    """, unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
    left, right = st.columns([2.2, 1])
    with left: render_big_kpi("TOTAL DATABANKS", len(df))
    with right:
        verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
        render_small_kpi("VERIFIED INTELLIGENCE", f"{verified_rate}%")
        
    st.write("")
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 20px;'>STATUS DISTRIBUTION</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.8, color="status", color_discrete_map={'Verified': '#00ff66', 'Pending Review': '#bc13fe', 'Needs Revision': '#fcee0a', 'Rejected': '#ff003c'})
            fig1.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 20px;'>DIVISION DISTRIBUTION</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="tipe", color="tipe", color_discrete_sequence=["#00f3ff", "#bc13fe", "#ff003c", "#fcee0a"]) 
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>BROWSE MAINFRAME_DATA</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    
    with st.container(border=True):
        st.markdown("<div style='font-family: Orbitron; font-weight: 700; font-size: 16px; margin-bottom: 12px; color: var(--neon-purple); letter-spacing: 1px;'>[QUERY PARAMETERS]</div>", unsafe_allow_html=True)
        
        search_query = st.text_input("Kata Kunci", placeholder="INPUT SEARCH METRICS...", label_visibility="collapsed")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_kategori = st.selectbox("Kategori Isu", ["ALL CATEGORIES"] + KATEGORI_OPTIONS)
        with f2:
            selected_tipe = st.selectbox("Divisi / Tipe Proyek", ["ALL DIVISIONS"] + TIPE_DIVISI_OPTIONS)
        with f3:
            STATUS_OPTIONS = ["ALL STATUSES", "Verified", "Pending Review", "Needs Revision", "Rejected"]
            selected_status = st.selectbox("Status Verifikasi", STATUS_OPTIONS)

    if selected_kategori != "ALL CATEGORIES":
        df = df[df['kategori'] == selected_kategori]
    if selected_tipe != "ALL DIVISIONS":
        df = df[df['tipe'] == selected_tipe]
    if selected_status != "ALL STATUSES":
        df = df[df['status'] == selected_status]
    if search_query:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]

    st.write("")
    
    if df.empty: 
        render_empty_state("QUERY RETURNED NULL", "Tidak ada dokumen yang sesuai dengan matriks pencarian.")
    else:
        st.markdown(f"<div style='font-size: 14px; font-family: Orbitron; color: var(--neon-cyan); margin-bottom: 16px; text-shadow: 0 0 5px var(--neon-cyan-dim);'>FOUND [<b>{len(df)}</b>] SECURE RECORDS MATCHING CRITERIA.</div>", unsafe_allow_html=True)
        for _, row in df.iterrows(): 
            with st.expander(f"📌 {row['nama_proyek']} | DIR: {row['tipe']} | [{row['status']}]"):
                render_knowledge_card_content(row)

def view_upload(repo):
    st.markdown("<div class='section-title'>INITIALIZE NEW REGISTER</div>", unsafe_allow_html=True)
    
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_deskripsi' not in st.session_state: st.session_state.ai_deskripsi = ""
    if 'ai_dampak' not in st.session_state: st.session_state.ai_dampak = ""
    if 'ai_pencegahan' not in st.session_state: st.session_state.ai_pencegahan = ""
    if 'ai_tantangan' not in st.session_state: st.session_state.ai_tantangan = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("✅ UPLOAD SEQUENCE COMPLETE! Data logged to Mainframe.")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 20px; margin-bottom: 16px; border:none;'>AI_NEURAL_EXTRACTION</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload lampiran atau laporan pendukung (Format: PDF, DOCX, TXT)", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("RUN GEMINI.AI PROTOCOL"):
            with st.spinner("PROCESSING DATA STREAM..."):
                file_bytes = io.BytesIO(uploaded_file.read())
                st.session_state.uploaded_file_bytes = file_bytes
                st.session_state.uploaded_filename = uploaded_file.name
                
                raw_text = parse_document(file_bytes, uploaded_file.name)
                if raw_text:
                    ai_result = extract_knowledge(raw_text)
                    st.session_state.ai_deskripsi = ai_result["deskripsi_isu"]
                    st.session_state.ai_dampak = ai_result["dampak_isu"]
                    st.session_state.ai_pencegahan = ai_result["aktivitas_pencegahan"]
                    st.session_state.ai_tantangan = ai_result["tantangan"]
                    st.rerun() 
                else:
                    st.error("EXTRACTION FAILED. CORRUPTED DATABLOCK.")
    st.write("")
    
    with st.container(border=True):
        with st.form("entry_form", border=False, clear_on_submit=True):
            nama_proyek = st.text_input("Nama Proyek", placeholder="INPUT PROJECT DESIGNATION...")
            manajer_proyek = st.text_input("Manajer Proyek", placeholder="INPUT OPERATOR NAME...")
            
            c_owner, c_dept = st.columns(2)
            with c_owner:
                project_owner = st.selectbox("Project Owner (PMO)", PMO_SATKER_OPTIONS)
            with c_dept:
                related_department = st.selectbox("Related Department", ALL_DEPARTMENTS_OPTIONS)

            c1, c2 = st.columns(2)
            with c1:
                kategori = st.selectbox("Kategori", KATEGORI_OPTIONS)
            with c2:
                tipe = st.selectbox("Tipe / Divisi (Folder Tujuan)", TIPE_DIVISI_OPTIONS)
                
            deskripsi_isu = st.text_area("Deskripsi Isu", value=st.session_state.ai_deskripsi, placeholder="INPUT PRIMARY ANOMALY...", height=100)
            dampak_isu = st.text_area("Dampak Isu", value=st.session_state.ai_dampak, placeholder="INPUT SYSTEM IMPACT...", height=100)
            aktivitas_pencegahan = st.text_area("Aktivitas Pencegahan yang Dapat Dilakukan", value=st.session_state.ai_pencegahan, placeholder="INPUT MITIGATION PROTOCOL...", height=100)
            tantangan = st.text_area("Tantangan yang Mungkin Dihadapi", value=st.session_state.ai_tantangan, placeholder="INPUT RISK PROJECTION...", height=100)
            
            st.write("")
            submitted = st.form_submit_button("TRANSMIT DATA TO MAINFRAME")
            
            if submitted:
                if nama_proyek and deskripsi_isu:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"UPLOADING TO SECURE CLOUD DIR: {tipe}..."):
                                target_folder_id = DIVISION_FOLDERS.get(tipe, DIVISION_FOLDERS["Lainnya"])
                                link = upload_to_gdrive(st.session_state.uploaded_file_bytes, st.session_state.uploaded_filename, target_folder_id)
                                if link: auto_gdrive_link = link

                    data = {
                        "nama_proyek": nama_proyek, 
                        "manajer_proyek": manajer_proyek, 
                        "project_owner": project_owner,
                        "related_department": related_department,
                        "kategori": kategori, 
                        "tipe": tipe, 
                        "deskripsi_isu": deskripsi_isu, 
                        "dampak_isu": dampak_isu, 
                        "aktivitas_pencegahan": aktivitas_pencegahan, 
                        "tantangan": tantangan,
                        "gdrive_link": auto_gdrive_link
                    }
                    
                    if repo.insert(data):
                        st.session_state.ai_deskripsi = ""
                        st.session_state.ai_dampak = ""
                        st.session_state.ai_pencegahan = ""
                        st.session_state.ai_tantangan = ""
                        st.session_state.uploaded_file_bytes = None
                        st.session_state.uploaded_filename = ""
                        
                        st.session_state.save_success = True
                        st.rerun()
                    else:
                        st.error("❌ TRANSMISSION FAILED.")
                else:
                    st.error("MANDATORY FIELDS (Project Name & Anomaly Desc) REQUIRED.")

def view_revision(repo):
    st.markdown("<div class='section-title'>REVISION DESK</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("WORKSPACE CLEAR", "Tidak ada anomali dokumen yang membutuhkan koreksi.")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        if f'rev_desc_{rid}' not in st.session_state: st.session_state[f'rev_desc_{rid}'] = row['deskripsi_isu']
        if f'rev_dampak_{rid}' not in st.session_state: st.session_state[f'rev_dampak_{rid}'] = row['dampak_isu']
        if f'rev_prev_{rid}' not in st.session_state: st.session_state[f'rev_prev_{rid}'] = row['aktivitas_pencegahan']
        if f'rev_tant_{rid}' not in st.session_state: st.session_state[f'rev_tant_{rid}'] = row['tantangan']

        with st.container(border=True):
            st.markdown(f"<div class='section-title' style='font-size: 24px; border:none;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background-color: rgba(252, 238, 10, 0.1); border-left: 4px solid #fcee0a; padding: 16px 20px; border-radius: 4px; margin-bottom: 24px; margin-top: 12px; box-shadow: 0 0 10px rgba(252, 238, 10, 0.2);"><div style="font-family:Orbitron; font-weight: 700; color: #fcee0a; margin-bottom: 4px; font-size: 13px; text-transform: uppercase;">ADMIN_FEEDBACK</div><div style="color: var(--text-bright); font-size: 16px; line-height: 1.5;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                nama_proyek = st.text_input("Nama Proyek", value=row['nama_proyek'])
                manajer_proyek = st.text_input("Manajer Proyek", value=row['manajer_proyek'])

                c_owner, c_dept = st.columns(2)
                with c_owner:
                    owner_val = row.get('project_owner', '')
                    owner_idx = PMO_SATKER_OPTIONS.index(owner_val) if owner_val in PMO_SATKER_OPTIONS else 0
                    project_owner = st.selectbox("Project Owner (PMO)", PMO_SATKER_OPTIONS, index=owner_idx)
                with c_dept:
                    dept_val = row.get('related_department', '')
                    dept_idx = ALL_DEPARTMENTS_OPTIONS.index(dept_val) if dept_val in ALL_DEPARTMENTS_OPTIONS else 0
                    related_department = st.selectbox("Related Department", ALL_DEPARTMENTS_OPTIONS, index=dept_idx)
                
                c1, c2 = st.columns(2)
                with c1:
                    kat_idx = KATEGORI_OPTIONS.index(row['kategori']) if row['kategori'] in KATEGORI_OPTIONS else 0
                    kategori = st.selectbox("Kategori", KATEGORI_OPTIONS, index=kat_idx)
                with c2:
                    tipe_idx = TIPE_DIVISI_OPTIONS.index(row['tipe']) if row['tipe'] in TIPE_DIVISI_OPTIONS else (len(TIPE_DIVISI_OPTIONS)-1)
                    tipe = st.selectbox("Tipe / Divisi", TIPE_DIVISI_OPTIONS, index=tipe_idx)
                    
                deskripsi_isu = st.text_area("Deskripsi Isu", value=st.session_state[f'rev_desc_{rid}'], height=100)
                dampak_isu = st.text_area("Dampak Isu", value=st.session_state[f'rev_dampak_{rid}'], height=100)
                aktivitas_pencegahan = st.text_area("Aktivitas Pencegahan", value=st.session_state[f'rev_prev_{rid}'], height=100)
                tantangan = st.text_area("Tantangan", value=st.session_state[f'rev_tant_{rid}'], height=100)
                
                st.write("")
                if st.form_submit_button("RE-TRANSMIT FOR APPROVAL"):
                    data = {
                        'nama_proyek': nama_proyek, 
                        'manajer_proyek': manajer_proyek, 
                        'project_owner': project_owner,
                        'related_department': related_department,
                        'kategori': kategori, 
                        'tipe': tipe, 
                        'deskripsi_isu': deskripsi_isu, 
                        'dampak_isu': dampak_isu, 
                        'aktivitas_pencegahan': aktivitas_pencegahan, 
                        'tantangan': tantangan, 
                        'gdrive_link': row['gdrive_link']
                    }
                    if repo.resubmit_record(rid, data):
                        st.rerun()

def view_approval(repo):
    st.markdown("<div class='section-title'>APPROVAL TERMINAL</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("INBOX CLEAR", "Semua blok data telah divalidasi.")
        return
        
    for _, row in pending_df.iterrows():
        with st.expander(f"📝 [AWAITING AUTH] {row['nama_proyek']} | OP: {row['manajer_proyek']}"):
            render_knowledge_card_content(row)
            
            st.markdown("<div class='cyber-divider'></div>", unsafe_allow_html=True)
            notes = st.text_area("Admin Feedbacks (Wajib diisi jika revisi/reject)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Delete File", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Reject File", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Flag Revision", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Verify File", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>DATA EXTRACTION / EXPORT</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 24px; margin-bottom: 32px; border:none;'>DOWNLOAD CORE DATABASE</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="EXTRACT AS .CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="EXTRACT AS .XLSX", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 14px; color:var(--text-muted);'>'openpyxl' library required for EXCEL extraction.</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN & ROUTING
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA Cyber KMS", layout="wide", initial_sidebar_state="expanded")
    create_cyberpunk_theme()
    inject_cyberpunk_css()
    repo = get_repository()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None

    if not st.session_state.logged_in:
        view_login()
        return

    role = st.session_state.role
    allowed_pages = ["Dashboard", "Browse"] 
    if role == "Uploader":
        allowed_pages.extend(["New Register", "Revision Desk"])
    elif role == "Reviewer":
        allowed_pages.extend(["Approval", "Export"])

    with st.sidebar:
        st.markdown("<div style='font-family:Orbitron; font-size: 24px; font-weight: 900; letter-spacing: 2px; color: var(--neon-cyan); margin-bottom: 4px; text-shadow: 0 0 10px var(--neon-cyan-dim);'>PTBA.KMS</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-family:Orbitron; font-size: 13px; font-weight: 500; color: var(--neon-purple); margin-bottom: 32px; padding: 12px; background: rgba(188, 19, 254, 0.1); border-radius: 4px; border: 1px solid var(--neon-purple); box-shadow: inset 0 0 10px var(--neon-purple-dim);'>USER: {st.session_state.username} <br>CLEARANCE: <b>{role}</b></div>", unsafe_allow_html=True)
        
        navigation = st.radio("Nav", allowed_pages, label_visibility="collapsed")
        
        st.write("")
        st.write("")
        if st.button("TERMINATE SESSION"):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.username = None
            st.rerun()
            
    if navigation == "Dashboard": view_dashboard(repo)
    elif navigation == "Browse": view_browse(repo)
    elif navigation == "New Register" and role == "Uploader": view_upload(repo)
    elif navigation == "Revision Desk" and role == "Uploader": view_revision(repo)
    elif navigation == "Approval" and role == "Reviewer": view_approval(repo)
    elif navigation == "Export" and role == "Reviewer": view_export(repo)

if __name__ == "__main__":
    main()

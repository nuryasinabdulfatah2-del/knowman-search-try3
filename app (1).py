# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION, RBAC Login
Format: Lessons Learned Register (Holographic Minimalist UI Edition)
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

# --- PLOTLY HOLOGRAPHIC THEME ---
def create_holographic_theme():
    font_family = "'Manrope', sans-serif"
    template = pio.templates["plotly_white"]
    template.layout.font = dict(family=font_family, color="#1A1A24", size=14)
    template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    template.layout.colorway = ["#FFB3E6", "#A3E9FF", "#C9B3FF", "#FFF3B3", "#B3E6FF"]
    template.layout.xaxis.showgrid = False
    template.layout.yaxis.showgrid = True
    template.layout.yaxis.gridcolor = "rgba(0, 0, 0, 0.03)"
    template.layout.xaxis.gridcolor = "rgba(0, 0, 0, 0.03)"
    pio.templates["holographic_minimal"] = template
    pio.templates.default = "holographic_minimal"

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
# 6. UI COMPONENTS & CSS (HOLOGRAPHIC MINIMALIST THEME)
# ==============================================================================
def inject_holographic_css():
    st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600&family=Manrope:wght@300;400;500;600&display=swap](https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600&family=Manrope:wght@300;400;500;600&display=swap)');
    
    :root {
        --bg-main: #FAFAFC;
        --surface: #FFFFFF;
        --text-main: #1A1A24;
        --text-muted: #808090;
        --holo-grad: linear-gradient(135deg, #FFB3E6, #A3E9FF, #C9B3FF, #FFF3B3, #FFB3E6);
        --border-light: rgba(0, 0, 0, 0.04);
        --shadow-soft: 0 4px 30px rgba(0, 0, 0, 0.02);
    }

    /* Animated Gradient for Hover & Accent */
    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Holographic Text Effect */
    .holo-text {
        background: var(--holo-grad);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradient-shift 5s ease infinite;
        display: inline-block;
    }

    /* Background with super subtle dot grid */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-main) !important;
        background-image: radial-gradient(rgba(201, 179, 255, 0.15) 1px, transparent 1px) !important;
        background-size: 40px 40px !important;
        font-family: 'Manrope', sans-serif !important;
        color: var(--text-main) !important;
        background-attachment: fixed !important;
    }
    
    p, label, li, div { font-family: 'Manrope', sans-serif; font-weight: 400; }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text-main) !important;
        letter-spacing: 0.02em;
        font-weight: 500 !important;
    }

    /* Sticky Navbar / Sidebar Styling */
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.8) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid var(--border-light);
        box-shadow: 2px 0 20px rgba(0,0,0,0.01);
    }
    [data-testid="collapsedControl"] {
        display: flex !important; visibility: visible !important;
        background: var(--surface) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 50px !important;
        margin: 1rem !important; z-index: 100 !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03) !important;
        transition: all 0.5s ease;
    }
    [data-testid="collapsedControl"]:hover {
        background: linear-gradient(#FFF, #FFF) padding-box, var(--holo-grad) border-box !important;
        border: 1px solid transparent !important;
        background-size: 200% auto !important;
        animation: gradient-shift 3s ease infinite !important;
    }
    
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1050px !important; }
    
    /* Typography & Layout */
    .hero-text { 
        font-family: 'Space Grotesk', sans-serif !important; 
        font-size: 72px; 
        font-weight: 400; 
        line-height: 1.1; 
        color: var(--text-main); 
        margin-bottom: 24px;
        letter-spacing: -1.5px;
    }
    .hero-sub { 
        font-size: 18px; 
        font-weight: 300; 
        color: var(--text-muted); 
        margin-bottom: 50px; 
        max-width: 650px; 
        line-height: 1.8;
        letter-spacing: 0.2px;
    }
    .section-title { 
        font-family: 'Space Grotesk', sans-serif !important; 
        font-size: 32px; 
        font-weight: 400; 
        margin-bottom: 40px; 
        color: var(--text-main);
        letter-spacing: -0.5px;
    }

    /* Minimalist Cards with Hover Holographic Borders */
    .bento, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid rgba(0,0,0,0.04) !important;
        box-shadow: var(--shadow-soft) !important;
        border-radius: 12px !important; 
        transition: all 0.5s ease !important;
        overflow: hidden;
        padding: 40px !important; /* Wide whitespace */
        position: relative;
    }
    [data-testid="stExpander"] { padding: 0 !important; margin-bottom: 24px !important; background: transparent !important;}
    
    /* Hover effects */
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover, [data-testid="stExpander"]:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 12px 40px rgba(163, 233, 255, 0.15) !important;
        background: linear-gradient(var(--surface), var(--surface)) padding-box, var(--holo-grad) border-box !important;
        border: 1px solid transparent !important;
        background-size: 200% auto !important;
        animation: gradient-shift 4s ease infinite !important;
    }

    /* Accordion Details */
    [data-testid="stExpander"] summary {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 400 !important;
        font-size: 18px !important;
        color: var(--text-main) !important;
        padding: 24px 32px !important;
        background-color: transparent !important;
        transition: all 0.5s ease !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: rgba(0,0,0,0.01) !important;
    }
    [data-testid="stExpanderDetails"] {
        padding: 8px 32px 32px 32px !important;
        border-top: 1px solid var(--border-light) !important;
    }

    /* KPI Cards */
    .kpi-big-val { font-family: 'Space Grotesk', sans-serif; font-size: 80px; font-weight: 300; line-height: 1; color: var(--text-main); letter-spacing: -2px;}
    .kpi-big-title { font-size: 13px; font-weight: 500; color: var(--text-muted); margin-top: 16px; letter-spacing: 2px; text-transform: uppercase;}
    .kpi-small-val { font-family: 'Space Grotesk', sans-serif; font-size: 50px; font-weight: 300; line-height: 1; color: var(--text-main); letter-spacing: -1px;}
    .kpi-small-title { font-size: 12px; font-weight: 500; color: var(--text-muted); margin-top: 12px; letter-spacing: 1px; text-transform: uppercase;}
    
    /* Card Content Typography */
    .card-meta { font-size: 13px; font-weight: 400; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;}
    .card-section { font-family: 'Space Grotesk', sans-serif; font-size: 12px; font-weight: 500; text-transform: uppercase; color: var(--text-main); margin-top: 40px; margin-bottom: 12px; letter-spacing: 1.5px;}
    .card-body { font-size: 15px; font-weight: 300; line-height: 1.8; color: var(--text-main);}
    
    /* Soft Minimal Badges */
    .badge { display: inline-block; padding: 6px 14px; border-radius: 40px; font-size: 11.5px; font-weight: 500; margin-right: 12px; margin-bottom: 8px; letter-spacing: 0.5px;}
    .badge-status-Pending { border: 1px solid rgba(201, 179, 255, 0.4); color: #8A6FD1; background: rgba(201, 179, 255, 0.05);}
    .badge-status-Verified { border: 1px solid rgba(163, 233, 255, 0.4); color: #3CA5C9; background: rgba(163, 233, 255, 0.05);}
    .badge-status-NeedsRevision { border: 1px solid rgba(255, 243, 179, 0.8); color: #B3A04D; background: rgba(255, 243, 179, 0.15);}
    .badge-status-Rejected { border: 1px solid rgba(255, 179, 230, 0.5); color: #C95B9E; background: rgba(255, 179, 230, 0.05);}
    .badge-kategori { border: 1px solid var(--border-light); color: var(--text-muted); background: transparent;}
    .badge-tipe { border: 1px solid var(--border-light); color: var(--text-muted); background: transparent;}
    
    /* GDrive Outline Button with Holographic Hover */
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 10px; background-color: transparent; color: var(--text-muted) !important; padding: 12px 24px; border-radius: 40px; font-weight: 500; font-size: 13px; text-decoration: none !important; margin-top: 32px; transition: all 0.5s ease; border: 1px solid var(--border-light); letter-spacing: 0.5px;}
    .gdrive-link-btn:hover { 
        color: var(--text-main) !important;
        background: linear-gradient(var(--surface), var(--surface)) padding-box, var(--holo-grad) border-box !important;
        border: 1px solid transparent !important;
        background-size: 200% auto !important;
        animation: gradient-shift 3s ease infinite !important;
        box-shadow: 0 4px 20px rgba(163, 233, 255, 0.2);
    }
    
    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { 
        background-color: transparent !important; 
        border: 1px solid var(--border-light) !important; 
        border-radius: 8px !important; 
        padding: 16px 20px !important; 
        font-size: 15px; font-weight: 400; 
        color: var(--text-main) !important; 
        transition: all 0.5s ease; 
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { 
        background: linear-gradient(var(--bg-main), var(--bg-main)) padding-box, var(--holo-grad) border-box !important;
        border-color: transparent !important;
        box-shadow: 0 4px 15px rgba(201, 179, 255, 0.1) !important;
    }
    
    /* Minimal Outline Buttons */
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { 
        background: transparent !important; 
        color: var(--text-main) !important; 
        border-radius: 40px !important; 
        padding: 14px 28px !important; 
        font-weight: 500 !important; 
        font-size: 14px !important; 
        border: 1px solid rgba(0,0,0,0.1) !important; 
        width: 100%; 
        transition: all 0.5s ease !important; 
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: 0.5px;
    }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { 
        background: linear-gradient(var(--surface), var(--surface)) padding-box, var(--holo-grad) border-box !important;
        border: 1px solid transparent !important;
        background-size: 200% auto !important;
        animation: gradient-shift 3s ease infinite !important;
        box-shadow: 0 8px 25px rgba(201, 179, 255, 0.2) !important; 
        transform: translateY(-2px); 
    }
    
    /* Role-based button overrides (Muted natural tones) */
    div[data-testid="stButton"] button:has(p:contains("Reject")):hover { border-color: transparent !important; background: linear-gradient(var(--surface), var(--surface)) padding-box, linear-gradient(45deg, #FFB3E6, #ff8fa3) border-box !important;}
    div[data-testid="stButton"] button:has(p:contains("Verify")):hover { border-color: transparent !important; background: linear-gradient(var(--surface), var(--surface)) padding-box, linear-gradient(45deg, #A3E9FF, #8fe0ff) border-box !important;}
    div[data-testid="stButton"] button:has(p:contains("Revision")):hover { border-color: transparent !important; background: linear-gradient(var(--surface), var(--surface)) padding-box, linear-gradient(45deg, #FFF3B3, #ffe88f) border-box !important;}

    /* Sidebar Radio */
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 14px 20px; border-radius: 8px; font-size: 14px; font-weight: 400; color: var(--text-muted); transition: 0.5s; letter-spacing: 0.5px;}
    div[role="radiogroup"] > label:hover { color: var(--text-main); background: rgba(0,0,0,0.01) !important;}
    div[role="radiogroup"] > label[data-checked="true"] { 
        background: transparent !important; 
        color: var(--text-main) !important; 
        border-bottom: 2px solid transparent;
        border-image: var(--holo-grad) 1;
        border-left: none;
        border-top: none;
        border-right: none;
        border-radius: 0;
    }
    
    [data-testid="stFileUploadDropzone"] { border-radius: 12px !important; border: 1px dashed rgba(0,0,0,0.1) !important; background-color: transparent !important; transition: all 0.5s; }
    [data-testid="stFileUploadDropzone"]:hover { 
        border: 1px solid transparent !important;
        background: linear-gradient(var(--bg-main), var(--bg-main)) padding-box, var(--holo-grad) border-box !important;
    }
    
    /* Holographic Divider */
    .holo-divider {
        height: 1px;
        background: var(--holo-grad);
        opacity: 0.3;
        margin: 40px 0;
    }
    </style>
    """, unsafe_allow_html=True)

def render_big_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-big-val">{value}</div><div class="kpi-big-title">{title}</div></div>""", unsafe_allow_html=True)

def render_small_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-small-val">{value}</div><div class="kpi-small-title">{title}</div></div>""", unsafe_allow_html=True)

def render_knowledge_card_content(row):
    status_str = str(row['status']).replace(" Pending Review", "Pending").replace(" ", "")
    
    deskripsi = str(row['deskripsi_isu']).replace('\n', '<br>')
    dampak = str(row['dampak_isu']).replace('\n', '<br>')
    pencegahan = str(row['aktivitas_pencegahan']).replace('\n', '<br>')
    tantangan = str(row['tantangan']).replace('\n', '<br>')
    
    gdrive_link = row['gdrive_link'] if 'gdrive_link' in row.keys() and row['gdrive_link'] else ""
    gdrive_html = f"""<div><a href="{gdrive_link}" target="_blank" class="gdrive-link-btn">
        <svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;"><line x1="7" y1="17" x2="17" y2="7"></line><polyline points="7 7 17 7 17 17"></polyline></svg>
        Buka File Original
    </a></div>""" if gdrive_link else ""
    
    kat_badge = f"<span class='badge badge-kategori'>○ {row.get('kategori', 'Area perbaikan')}</span>"
    tipe_badge = f"<span class='badge badge-tipe'>○ {row.get('tipe', '-')}</span>"

    owner_text = row.get('project_owner', '-')
    dept_text = row.get('related_department', '-')

    card_html = f"""
    <div>
        <div class="card-meta">
            Operator: {row['manajer_proyek']} &nbsp; • &nbsp; 
            Owner: {owner_text} &nbsp; • &nbsp; 
            Dept: {dept_text} &nbsp; • &nbsp; 
            Update: {row['upload_date']}
        </div>
        <div style="margin-bottom: 32px;">
            <span class="badge badge-status-{status_str}">Status: {row['status']}</span>
            {kat_badge} {tipe_badge}
        </div>
        
        <div class="card-section">Deskripsi Parameter</div>
        <div class="card-body">{deskripsi}</div>
        
        <div class="holo-divider"></div>
        
        <div class="card-section">Dampak / Anomali</div>
        <div class="card-body">{dampak}</div>
        
        <div class="holo-divider"></div>
        
        <div class="card-section">Protokol Pencegahan</div>
        <div class="card-body" style="font-weight: 500; color: #1A1A24;">{pencegahan}</div>
        
        <div class="holo-divider"></div>
        
        <div class="card-section">Tantangan Implementasi</div>
        <div class="card-body">{tantangan}</div>
        {gdrive_html}
    </div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="Belum Ada Rekaman", subtitle="Repositori saat ini bersih dari entri. Mulai catat pengalaman operasional Anda."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 120px 40px;"><div class="section-title" style="margin-bottom: 16px; font-size: 28px; border:none;">{title}</div><div class="card-body" style="color: var(--text-muted); font-weight:300;">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_login():
    st.markdown("""
        <div style="text-align: center; margin-top: 15vh; margin-bottom: 60px;">
            <div class="hero-text"><span class="holo-text">Knowledge</span><br>Management System.</div>
            <div class="hero-sub" style="margin: 0 auto;">Pusat Integrasi Pembelajaran Organisasi PT Bukit Asam Tbk.</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; font-family:\"Space Grotesk\", sans-serif; font-size: 16px; margin-bottom: 32px; font-weight: 400; letter-spacing: 0.5px;'>Otentikasi Kredensial</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="ID Pengguna...")
            password = st.text_input("Password", type="password", placeholder="Kata Sandi...")
            
            st.write("")
            st.write("")
            if st.button("Masuk Area Kerja"):
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user["role"]
                    st.rerun()
                else:
                    st.error("Kredensial tidak valid.")

def view_dashboard(repo):
    st.markdown("""
        <div class="hero-text"><span class="holo-text">Lessons Learned</span><br>Intelligence Core.</div>
        <div class="hero-sub">Platform minimalis untuk mendokumentasikan, menganalisis, dan mentransformasi anomali operasional menjadi strategi aset perusahaan.</div>
    """, unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
    left, right = st.columns([2.2, 1])
    with left: render_big_kpi("Total Basis Pengetahuan", len(df))
    with right:
        verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
        render_small_kpi("Tingkat Verifikasi", f"{verified_rate}%")
        
    st.write("")
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 20px;'>Distribusi Status</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.85, color="status", color_discrete_map={'Verified': '#A3E9FF', 'Pending Review': '#C9B3FF', 'Needs Revision': '#FFF3B3', 'Rejected': '#FFB3E6'})
            fig1.update_layout(showlegend=False, height=320, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 20px;'>Berdasarkan Divisi</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="tipe", color="tipe", color_discrete_sequence=["#FFB3E6", "#A3E9FF", "#C9B3FF", "#FFF3B3", "#B3E6FF"]) 
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=320, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Eksplorasi <span class='holo-text'>Arsip Pengetahuan.</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    
    with st.container(border=True):
        st.markdown("<div style='font-family: \"Space Grotesk\", sans-serif; font-weight: 400; font-size: 16px; margin-bottom: 24px;'>Parameter Pencarian</div>", unsafe_allow_html=True)
        
        search_query = st.text_input("Kata Kunci", placeholder="Ketik metrik pencarian...", label_visibility="collapsed")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_kategori = st.selectbox("Kategori Laporan", ["Semua Kategori"] + KATEGORI_OPTIONS)
        with f2:
            selected_tipe = st.selectbox("Klasifikasi Proyek", ["Semua Divisi"] + TIPE_DIVISI_OPTIONS)
        with f3:
            STATUS_OPTIONS = ["Semua Status", "Verified", "Pending Review", "Needs Revision", "Rejected"]
            selected_status = st.selectbox("Status Verifikasi", STATUS_OPTIONS)

    if selected_kategori != "Semua Kategori":
        df = df[df['kategori'] == selected_kategori]
    if selected_tipe != "Semua Divisi":
        df = df[df['tipe'] == selected_tipe]
    if selected_status != "Semua Status":
        df = df[df['status'] == selected_status]
    if search_query:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]

    st.write("")
    
    if df.empty: 
        render_empty_state("Hasil Pencarian Nihil", "Tidak ditemukan dokumen dengan spesifikasi yang dicari.")
    else:
        st.markdown(f"<div style='font-size: 14px; font-weight:400; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;'>Ditemukan <b>{len(df)}</b> rekaman data.</div>", unsafe_allow_html=True)
        for _, row in df.iterrows(): 
            with st.expander(f"{row['nama_proyek']}  —  {row['tipe']}"):
                render_knowledge_card_content(row)

def view_upload(repo):
    st.markdown("<div class='section-title'>Pencatatan <span class='holo-text'>Register.</span></div>", unsafe_allow_html=True)
    
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_deskripsi' not in st.session_state: st.session_state.ai_deskripsi = ""
    if 'ai_dampak' not in st.session_state: st.session_state.ai_dampak = ""
    if 'ai_pencegahan' not in st.session_state: st.session_state.ai_pencegahan = ""
    if 'ai_tantangan' not in st.session_state: st.session_state.ai_tantangan = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("Tersimpan. Laporan diteruskan ke modul kurasi.")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 20px; margin-bottom: 20px;'>Ekstraksi Gemini AI</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Unggah dokumen pendukung (PDF, DOCX, TXT)", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("Mulai Analisis Artifisial"):
            with st.spinner("Memindai narasi..."):
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
                    st.error("Gagal mengekstraksi teks.")
    st.write("")
    
    with st.container(border=True):
        with st.form("entry_form", border=False, clear_on_submit=True):
            nama_proyek = st.text_input("Identitas Proyek", placeholder="Contoh: Optimasi Logistik Jalur...")
            manajer_proyek = st.text_input("Manajer Pelaksana", placeholder="Nama Penanggung Jawab...")
            
            c_owner, c_dept = st.columns(2)
            with c_owner:
                project_owner = st.selectbox("Pemilik Proyek (PMO)", PMO_SATKER_OPTIONS)
            with c_dept:
                related_department = st.selectbox("Departemen Terkait", ALL_DEPARTMENTS_OPTIONS)

            c1, c2 = st.columns(2)
            with c1:
                kategori = st.selectbox("Klasifikasi Kategori", KATEGORI_OPTIONS)
            with c2:
                tipe = st.selectbox("Divisi Utama (Folder Storage)", TIPE_DIVISI_OPTIONS)
                
            deskripsi_isu = st.text_area("Deskripsi Kendala", value=st.session_state.ai_deskripsi, placeholder="Uraikan anomali operasional...", height=120)
            dampak_isu = st.text_area("Dampak Skala Proyek", value=st.session_state.ai_dampak, placeholder="Implikasi biaya atau timeline...", height=120)
            aktivitas_pencegahan = st.text_area("Aktivitas Mitigasi", value=st.session_state.ai_pencegahan, placeholder="Langkah konkrit yang diambil...", height=120)
            tantangan = st.text_area("Risiko Lanjutan", value=st.session_state.ai_tantangan, placeholder="Limitasi yang masih ada...", height=120)
            
            st.write("")
            submitted = st.form_submit_button("Simpan & Ajukan Register")
            
            if submitted:
                if nama_proyek and deskripsi_isu:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"Menyinkronkan file ke Cloud Divisi {tipe}..."):
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
                        st.error("Terjadi galat komputasi.")
                else:
                    st.error("Mohon lengkapi parameter Identitas Proyek dan Deskripsi.")

def view_revision(repo):
    st.markdown("<div class='section-title'>Terminal <span class='holo-text'>Koreksi.</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("Antrean Lengang", "Tidak ada dokumen yang menuntut perbaikan.")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        if f'rev_desc_{rid}' not in st.session_state: st.session_state[f'rev_desc_{rid}'] = row['deskripsi_isu']
        if f'rev_dampak_{rid}' not in st.session_state: st.session_state[f'rev_dampak_{rid}'] = row['dampak_isu']
        if f'rev_prev_{rid}' not in st.session_state: st.session_state[f'rev_prev_{rid}'] = row['aktivitas_pencegahan']
        if f'rev_tant_{rid}' not in st.session_state: st.session_state[f'rev_tant_{rid}'] = row['tantangan']

        with st.container(border=True):
            st.markdown(f"<div class='section-title' style='font-size: 24px; margin-bottom: 24px;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background: rgba(255, 243, 179, 0.1); border: 1px solid rgba(255, 243, 179, 0.5); padding: 24px; border-radius: 8px; margin-bottom: 32px;"><div style="font-family:'Space Grotesk'; font-weight: 500; color: #B3A04D; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; letter-spacing:1px;">Umpan Balik PMO</div><div style="color: var(--text-main); font-size: 15px; font-weight:300; line-height: 1.6;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                nama_proyek = st.text_input("Identitas Proyek", value=row['nama_proyek'])
                manajer_proyek = st.text_input("Manajer Pelaksana", value=row['manajer_proyek'])

                c_owner, c_dept = st.columns(2)
                with c_owner:
                    owner_val = row.get('project_owner', '')
                    owner_idx = PMO_SATKER_OPTIONS.index(owner_val) if owner_val in PMO_SATKER_OPTIONS else 0
                    project_owner = st.selectbox("Pemilik Proyek (PMO)", PMO_SATKER_OPTIONS, index=owner_idx)
                with c_dept:
                    dept_val = row.get('related_department', '')
                    dept_idx = ALL_DEPARTMENTS_OPTIONS.index(dept_val) if dept_val in ALL_DEPARTMENTS_OPTIONS else 0
                    related_department = st.selectbox("Departemen Afiliasi", ALL_DEPARTMENTS_OPTIONS, index=dept_idx)
                
                c1, c2 = st.columns(2)
                with c1:
                    kat_idx = KATEGORI_OPTIONS.index(row['kategori']) if row['kategori'] in KATEGORI_OPTIONS else 0
                    kategori = st.selectbox("Klasifikasi Isu", KATEGORI_OPTIONS, index=kat_idx)
                with c2:
                    tipe_idx = TIPE_DIVISI_OPTIONS.index(row['tipe']) if row['tipe'] in TIPE_DIVISI_OPTIONS else (len(TIPE_DIVISI_OPTIONS)-1)
                    tipe = st.selectbox("Divisi Utama", TIPE_DIVISI_OPTIONS, index=tipe_idx)
                    
                deskripsi_isu = st.text_area("Deskripsi Kendala", value=st.session_state[f'rev_desc_{rid}'], height=120)
                dampak_isu = st.text_area("Dampak Skala Proyek", value=st.session_state[f'rev_dampak_{rid}'], height=120)
                aktivitas_pencegahan = st.text_area("Aktivitas Mitigasi", value=st.session_state[f'rev_prev_{rid}'], height=120)
                tantangan = st.text_area("Risiko Lanjutan", value=st.session_state[f'rev_tant_{rid}'], height=120)
                
                st.write("")
                if st.form_submit_button("Ajukan Ulang Draf"):
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
    st.markdown("<div class='section-title'>Kamar <span class='holo-text'>Kurasi PMO.</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("Antrean Bersih", "Seluruh data telah lolos tahap Quality Control.")
        return
        
    for _, row in pending_df.iterrows():
        with st.expander(f"Menunggu Kurasi  —  {row['nama_proyek']}"):
            render_knowledge_card_content(row)
            
            st.markdown("<div class='holo-divider'></div>", unsafe_allow_html=True)
            notes = st.text_area("Tinggalkan Jejak Ulasan (Krusial untuk penolakan/revisi)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Hapus Entri", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Tolak / Arsip", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Tuntut Revisi", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Sahkan Dokumen", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>Ekstraksi <span class='holo-text'>Database.</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 22px; margin-bottom: 40px;'>Unduh Repositori Master</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="Ekspor Format .CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="Ekspor Format .XLSX", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 13px; color:var(--text-muted); margin-top: 16px;'>Library 'openpyxl' terdeteksi nonaktif untuk fungsionalitas ini.</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN & ROUTING
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA Minimalist KMS", layout="wide", initial_sidebar_state="expanded")
    create_holographic_theme()
    inject_holographic_css()
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
        st.markdown("<div style='font-family:\"Space Grotesk\", sans-serif; font-size: 20px; font-weight: 500; letter-spacing: -0.5px; color: var(--text-main); margin-bottom: 32px;'><span class='holo-text'>KMS</span> Platform.</div>", unsafe_allow_html=True)
        
        navigation = st.radio("Indeks Navigasi", allowed_pages, label_visibility="collapsed")
        
        st.write("")
        st.write("")
        st.write("")
        st.markdown(f"<div style='font-family:\"Manrope\", sans-serif; font-size: 13px; font-weight: 400; color: var(--text-muted); margin-bottom: 24px; padding: 0 12px;'>Kredensial Aktif:<br><span style='color:var(--text-main); font-weight:500;'>{st.session_state.username}</span><br>Hak Akses: {role}</div>", unsafe_allow_html=True)
        if st.button("Akhiri Sesi"):
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

# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION, RBAC Login
Format: Lessons Learned Register (Mineral / Stone UI Edition)
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

# --- PLOTLY MINERAL / STONE THEME ---
def create_mineral_theme():
    font_family = "'Manrope', sans-serif"
    template = pio.templates["plotly_white"]
    template.layout.font = dict(family=font_family, color="#2C2C2C", size=14)
    template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    template.layout.colorway = ["#C9A876", "#D4B0A8", "#B5B0A1", "#8C8A84", "#D9D0C1"]
    template.layout.xaxis.showgrid = False
    template.layout.yaxis.showgrid = True
    template.layout.yaxis.gridcolor = "rgba(201, 168, 118, 0.15)"
    template.layout.xaxis.gridcolor = "rgba(201, 168, 118, 0.15)"
    pio.templates["mineral_stone"] = template
    pio.templates.default = "mineral_stone"

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
# 6. UI COMPONENTS & CSS (MINERAL / STONE THEME)
# ==============================================================================
def inject_mineral_css():
    st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Manrope:wght@300;400;500;600&display=swap](https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Manrope:wght@300;400;500;600&display=swap)');
    
    :root {
        --bg-main: #FAF7F2;
        --surface: #FFFFFF;
        --text-main: #2C2C2C;
        --text-muted: #7A7A7A;
        --accent-gold: #C9A876;
        --accent-gold-hover: #DAB988;
        --border-light: rgba(201, 168, 118, 0.25);
        --shadow-soft: 0 8px 30px rgba(0, 0, 0, 0.03);
        --shadow-hover: 0 12px 40px rgba(0, 0, 0, 0.08);
    }

    /* Ambient Subtle Marble Noise */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-main) !important;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='[http://www.w3.org/2000/svg'%3E%3Cfilter](http://www.w3.org/2000/svg'%3E%3Cfilter) id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.02' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.04'/%3E%3C/svg%3E") !important;
        font-family: 'Manrope', sans-serif !important;
        color: var(--text-main) !important;
        background-attachment: fixed !important;
    }
    
    p, label, li, div { font-family: 'Manrope', sans-serif; }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        color: var(--text-main) !important;
        letter-spacing: 0.03em;
        font-weight: 500 !important;
    }

    /* Sticky Navbar / Sidebar Styling */
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; border-bottom: 1px solid var(--border-light);}
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border-light);
        box-shadow: 2px 0 15px rgba(0,0,0,0.02);
    }
    [data-testid="collapsedControl"] {
        display: flex !important; visibility: visible !important;
        background: var(--surface) !important;
        color: var(--accent-gold) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 0 !important; /* Facet shape */
        margin: 1rem !important; z-index: 100 !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important;
    }
    
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1050px !important; }
    
    /* Typography & Layout */
    .hero-text { 
        font-family: 'Playfair Display', serif !important; 
        font-size: 68px; 
        font-weight: 500; 
        line-height: 1.15; 
        color: var(--text-main); 
        margin-bottom: 24px;
        letter-spacing: -0.5px;
    }
    .hero-sub { 
        font-size: 19px; 
        font-weight: 300; 
        color: var(--text-muted); 
        margin-bottom: 50px; 
        max-width: 650px; 
        line-height: 1.7;
        letter-spacing: 0.5px;
    }
    .section-title { 
        font-family: 'Playfair Display', serif !important; 
        font-size: 34px; 
        font-weight: 500; 
        margin-bottom: 32px; 
        color: var(--text-main);
        letter-spacing: 0.5px;
    }

    /* Minimalist Cards / Facet Panels */
    .bento, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border-light) !important;
        box-shadow: var(--shadow-soft) !important;
        border-radius: 2px !important; /* Sharp elegant corners */
        transition: all 0.4s ease !important;
        overflow: hidden;
        padding: 36px !important;
    }
    [data-testid="stExpander"] { padding: 0 !important; margin-bottom: 20px !important;}
    
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover, [data-testid="stExpander"]:hover {
        border-color: rgba(201, 168, 118, 0.6) !important; /* Gold border brightens */
        box-shadow: var(--shadow-hover) !important;
        transform: translateY(-3px) !important;
    }

    /* Accordion Details */
    [data-testid="stExpander"] summary {
        font-family: 'Playfair Display', serif !important;
        font-weight: 500 !important;
        font-size: 19px !important;
        color: var(--text-main) !important;
        padding: 24px 32px !important;
        background-color: var(--surface) !important;
        transition: background-color 0.3s ease !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: #FAFAFA !important;
    }
    [data-testid="stExpanderDetails"] {
        padding: 8px 32px 32px 32px !important;
        border-top: 1px solid var(--border-light) !important;
    }

    /* KPI Cards */
    .kpi-big-val { font-family: 'Playfair Display', serif; font-size: 76px; font-weight: 400; line-height: 1; color: var(--text-main); }
    .kpi-big-title { font-size: 14px; font-weight: 600; color: var(--accent-gold); margin-top: 16px; letter-spacing: 2px; text-transform: uppercase;}
    .kpi-small-val { font-family: 'Playfair Display', serif; font-size: 50px; font-weight: 400; line-height: 1; color: var(--text-main); }
    .kpi-small-title { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-top: 12px; letter-spacing: 1px; text-transform: uppercase;}
    
    /* Card Content Typography */
    .card-meta { font-size: 13px; font-weight: 500; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;}
    .card-section { font-family: 'Manrope', sans-serif; font-size: 12px; font-weight: 600; text-transform: uppercase; color: var(--accent-gold); margin-top: 36px; margin-bottom: 12px; letter-spacing: 1.5px;}
    .card-body { font-size: 15px; font-weight: 400; line-height: 1.8; color: var(--text-main);}
    
    /* Elegant Badges (Stone tones) */
    .badge { display: inline-block; padding: 6px 14px; border-radius: 2px; font-size: 11.5px; font-weight: 600; margin-right: 12px; margin-bottom: 8px; letter-spacing: 1px; text-transform: uppercase;}
    .badge-status-Pending { border: 1px solid #D4B0A8; color: #8F5B50; background: #FAF2F0;}
    .badge-status-Verified { border: 1px solid #A1B5A6; color: #527359; background: #F2F7F3;}
    .badge-status-NeedsRevision { border: 1px solid #D9D0C1; color: #8C7B61; background: #F8F6F2;}
    .badge-status-Rejected { border: 1px solid #C49F9F; color: #7A3F3F; background: #F7EBEB;}
    .badge-kategori { border: 1px solid var(--border-light); color: var(--text-muted); background: transparent;}
    .badge-tipe { border: 1px solid var(--border-light); color: var(--text-muted); background: transparent;}
    
    /* GDrive Outline Button */
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 10px; background-color: transparent; color: var(--accent-gold) !important; padding: 12px 24px; border-radius: 2px; font-weight: 600; font-size: 13px; text-decoration: none !important; margin-top: 32px; transition: all 0.4s ease; border: 1px solid var(--accent-gold); letter-spacing: 1px; text-transform: uppercase;}
    .gdrive-link-btn:hover { background-color: var(--accent-gold); color: #fff !important; box-shadow: 0 4px 15px rgba(201, 168, 118, 0.25);}
    
    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { 
        background-color: var(--surface) !important; 
        border: 1px solid var(--border-light) !important; 
        border-radius: 2px !important; 
        padding: 16px 20px !important; 
        font-size: 15px; font-weight: 400; 
        color: var(--text-main) !important; 
        transition: all 0.3s ease; 
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { 
        border-color: var(--accent-gold) !important; 
        box-shadow: 0 0 0 1px var(--accent-gold) !important; 
    }
    
    /* Outline Gold Buttons */
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { 
        background: transparent !important; 
        color: var(--accent-gold) !important; 
        border-radius: 2px !important; 
        padding: 14px 28px !important; 
        font-weight: 600 !important; 
        font-size: 14px !important; 
        border: 1px solid var(--accent-gold) !important; 
        width: 100%; 
        transition: all 0.4s ease !important; 
        font-family: 'Manrope', sans-serif !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { 
        background: var(--accent-gold) !important; 
        color: #FFF !important;
        box-shadow: 0 6px 20px rgba(201, 168, 118, 0.25) !important; 
        transform: translateY(-2px); 
    }
    
    /* Role-based button overrides (Muted natural tones) */
    div[data-testid="stButton"] button:has(p:contains("Reject")) { border-color: #B26B6B !important; color: #B26B6B !important;}
    div[data-testid="stButton"] button:has(p:contains("Reject")):hover { background: #B26B6B !important; color: #fff !important; box-shadow: 0 6px 20px rgba(178, 107, 107, 0.2) !important;}
    div[data-testid="stButton"] button:has(p:contains("Verify")) { border-color: #6B8E73 !important; color: #6B8E73 !important;}
    div[data-testid="stButton"] button:has(p:contains("Verify")):hover { background: #6B8E73 !important; color: #fff !important; box-shadow: 0 6px 20px rgba(107, 142, 115, 0.2) !important;}
    div[data-testid="stButton"] button:has(p:contains("Revision")) { border-color: #A6957B !important; color: #A6957B !important;}
    div[data-testid="stButton"] button:has(p:contains("Revision")):hover { background: #A6957B !important; color: #fff !important; box-shadow: 0 6px 20px rgba(166, 149, 123, 0.2) !important;}
    div[data-testid="stButton"] button:has(p:contains("Delete")) { border-color: #8C8A84 !important; color: #8C8A84 !important;}
    div[data-testid="stButton"] button:has(p:contains("Delete")):hover { background: #8C8A84 !important; color: #fff !important;}

    /* Sidebar Radio */
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 14px 20px; border-radius: 2px; font-size: 14px; font-weight: 500; color: var(--text-muted); transition: 0.3s; letter-spacing: 0.5px;}
    div[role="radiogroup"] > label:hover { color: var(--text-main); background: rgba(0,0,0,0.02) !important;}
    div[role="radiogroup"] > label[data-checked="true"] { background-color: #FDFBF7 !important; color: var(--accent-gold) !important; border-left: 3px solid var(--accent-gold);}
    
    [data-testid="stFileUploadDropzone"] { border-radius: 2px !important; border: 1px dashed var(--accent-gold) !important; background-color: transparent !important; transition: all 0.3s; }
    [data-testid="stFileUploadDropzone"]:hover { background-color: rgba(201, 168, 118, 0.05) !important; }
    
    /* Mineral Divider */
    .mineral-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(201, 168, 118, 0.5), transparent);
        margin: 32px 0;
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
        <svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        Lampiran Original
    </a></div>""" if gdrive_link else ""
    
    kat_badge = f"<span class='badge badge-kategori'>Kategori: {row.get('kategori', 'Area perbaikan')}</span>"
    tipe_badge = f"<span class='badge badge-tipe'>Divisi: {row.get('tipe', '-')}</span>"

    owner_text = row.get('project_owner', '-')
    dept_text = row.get('related_department', '-')

    card_html = f"""
    <div>
        <div class="card-meta">
            Project Manager: {row['manajer_proyek']} &nbsp; • &nbsp; 
            Owner: {owner_text} &nbsp; • &nbsp; 
            Dept: {dept_text} &nbsp; • &nbsp; 
            Diperbarui: {row['upload_date']}
        </div>
        <div style="margin-bottom: 32px;">
            <span class="badge badge-status-{status_str}">Status: {row['status']}</span>
            {kat_badge} {tipe_badge}
        </div>
        
        <div class="card-section">Akar Masalah Utama</div>
        <div class="card-body">{deskripsi}</div>
        
        <div class="mineral-divider"></div>
        
        <div class="card-section">Dampak Identifikasi</div>
        <div class="card-body">{dampak}</div>
        
        <div class="mineral-divider"></div>
        
        <div class="card-section">Tindakan Pencegahan / Rekomendasi</div>
        <div class="card-body" style="font-weight: 500;">{pencegahan}</div>
        
        <div class="mineral-divider"></div>
        
        <div class="card-section">Proyeksi Tantangan</div>
        <div class="card-body">{tantangan}</div>
        {gdrive_html}
    </div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="Data Tidak Tersedia", subtitle="Repositori pengetahuan saat ini masih kosong. Silakan inisialisasi entri pertama Anda untuk mendokumentasikan nilai perusahaan."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 100px 40px;"><div class="section-title" style="margin-bottom: 16px; font-size: 28px; border:none;">{title}</div><div class="card-body" style="color: var(--text-muted); font-weight:400;">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_login():
    st.markdown("""
        <div style="text-align: center; margin-top: 15vh; margin-bottom: 60px;">
            <div class="hero-text">Knowledge Management</div>
            <div class="hero-sub" style="margin: 0 auto; letter-spacing: 1px;">Portal Otentikasi Eksekutif PT Bukit Asam Tbk.</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; font-family:\"Playfair Display\", serif; font-size: 20px; margin-bottom: 24px; font-weight: 500; color: var(--accent-gold); letter-spacing: 0.5px;'>Akses Repositori</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Masukkan ID Pengguna...")
            password = st.text_input("Password", type="password", placeholder="Masukkan Kata Sandi...")
            
            st.write("")
            if st.button("Otorisasi Akses"):
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user["role"]
                    st.rerun()
                else:
                    st.error("Kredensial tidak valid. Silakan periksa kembali.")

def view_dashboard(repo):
    st.markdown("""
        <div class="hero-text">Lessons Learned<br>Intelligence Core.</div>
        <div class="hero-sub">Platform editorial untuk mendokumentasikan, menganalisis, dan mentransformasi pengalaman operasional menjadi aset penunjang keputusan strategis perusahaan.</div>
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
            st.markdown("<div class='section-title' style='font-size: 22px;'>Distribusi Status</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.75, color="status", color_discrete_map={'Verified': '#6B8E73', 'Pending Review': '#D4B0A8', 'Needs Revision': '#A6957B', 'Rejected': '#B26B6B'})
            fig1.update_layout(showlegend=False, height=320, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 22px;'>Berdasarkan Divisi</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="tipe", color="tipe", color_discrete_sequence=["#C9A876", "#D4B0A8", "#B5B0A1", "#8C8A84", "#D9D0C1"]) 
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=320, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Eksplorasi Arsip Pengetahuan</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    
    with st.container(border=True):
        st.markdown("<div style='font-family: \"Playfair Display\", serif; font-weight: 500; font-size: 20px; margin-bottom: 24px; color: var(--accent-gold);'>Filter Parameter Penelusuran</div>", unsafe_allow_html=True)
        
        search_query = st.text_input("Kata Kunci", placeholder="Cari penamaan proyek, deskripsi masalah, atau frasa solusi...", label_visibility="collapsed")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_kategori = st.selectbox("Kategori Laporan", ["Semua Kategori"] + KATEGORI_OPTIONS)
        with f2:
            selected_tipe = st.selectbox("Klasifikasi Proyek", ["Semua Divisi"] + TIPE_DIVISI_OPTIONS)
        with f3:
            STATUS_OPTIONS = ["Semua Status", "Verified", "Pending Review", "Needs Revision", "Rejected"]
            selected_status = st.selectbox("Status Autentikasi", STATUS_OPTIONS)

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
        render_empty_state("Hasil Penelusuran Nihil", "Tidak ditemukan rekam jejak dokumen yang sesuai dengan spesifikasi filter Anda.")
    else:
        st.markdown(f"<div style='font-size: 14px; font-weight:500; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;'>Menampilkan <b>{len(df)}</b> aset pengetahuan terkurasi.</div>", unsafe_allow_html=True)
        for _, row in df.iterrows(): 
            with st.expander(f"{row['nama_proyek']}  —  {row['tipe']}"):
                render_knowledge_card_content(row)

def view_upload(repo):
    st.markdown("<div class='section-title'>Pencatatan Lessons Learned</div>", unsafe_allow_html=True)
    
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_deskripsi' not in st.session_state: st.session_state.ai_deskripsi = ""
    if 'ai_dampak' not in st.session_state: st.session_state.ai_dampak = ""
    if 'ai_pencegahan' not in st.session_state: st.session_state.ai_pencegahan = ""
    if 'ai_tantangan' not in st.session_state: st.session_state.ai_tantangan = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("✨ Arsip berhasil ditransmisikan dan menunggu peninjauan Quality Control.")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 22px; margin-bottom: 20px;'>Analisis Artifisial (AI Gemini)</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Lampirkan dokumen otentik proyek (PDF, DOCX, TXT)", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("Mulai Pemindaian Intelijen"):
            with st.spinner("Mengekstraksi narasi dan merangkum parameter masalah..."):
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
                    st.error("Gagal menelaah berkas: Dokumen tidak mengandung teks yang dapat diidentifikasi.")
    st.write("")
    
    with st.container(border=True):
        with st.form("entry_form", border=False, clear_on_submit=True):
            nama_proyek = st.text_input("Identitas Proyek / Aktivitas", placeholder="Misal: Resolusi Hambatan Infrastruktur Tambang...")
            manajer_proyek = st.text_input("Manajer Eksekutor", placeholder="Nama Penanggung Jawab Eksekusi...")
            
            c_owner, c_dept = st.columns(2)
            with c_owner:
                project_owner = st.selectbox("Project Owner (PMO)", PMO_SATKER_OPTIONS)
            with c_dept:
                related_department = st.selectbox("Departemen Afiliasi", ALL_DEPARTMENTS_OPTIONS)

            c1, c2 = st.columns(2)
            with c1:
                kategori = st.selectbox("Klasifikasi Isu", KATEGORI_OPTIONS)
            with c2:
                tipe = st.selectbox("Divisi Utama (Folder Direktori)", TIPE_DIVISI_OPTIONS)
                
            deskripsi_isu = st.text_area("Rincian Akar Masalah", value=st.session_state.ai_deskripsi, placeholder="Uraikan anomali operasional secara mendalam...", height=120)
            dampak_isu = st.text_area("Dampak Terhadap Skala Proyek", value=st.session_state.ai_dampak, placeholder="Jelaskan implikasi terhadap biaya, waktu, atau sumber daya...", height=120)
            aktivitas_pencegahan = st.text_area("Rekomendasi Tindakan / Solusi", value=st.session_state.ai_pencegahan, placeholder="Langkah mitigasi terukur yang berhasil/direncanakan...", height=120)
            tantangan = st.text_area("Tantangan Implementasi Lanjutan", value=st.session_state.ai_tantangan, placeholder="Risiko residual atau limitasi yang mungkin timbul...", height=120)
            
            st.write("")
            submitted = st.form_submit_button("Simpan & Finalisasi Laporan")
            
            if submitted:
                if nama_proyek and deskripsi_isu:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"Menyimpan salinan fisik ke Vault Divisi {tipe}..."):
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
                        st.error("Terjadi galat komputasi saat pencatatan database.")
                else:
                    st.error("Wajib melengkapi Identitas Proyek dan Rincian Akar Masalah.")

def view_revision(repo):
    st.markdown("<div class='section-title'>Meja Kerja Editor</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("Antrean Lengang", "Tidak ada draf dokumen yang dikembalikan oleh Tim Peninjau untuk disempurnakan.")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        if f'rev_desc_{rid}' not in st.session_state: st.session_state[f'rev_desc_{rid}'] = row['deskripsi_isu']
        if f'rev_dampak_{rid}' not in st.session_state: st.session_state[f'rev_dampak_{rid}'] = row['dampak_isu']
        if f'rev_prev_{rid}' not in st.session_state: st.session_state[f'rev_prev_{rid}'] = row['aktivitas_pencegahan']
        if f'rev_tant_{rid}' not in st.session_state: st.session_state[f'rev_tant_{rid}'] = row['tantangan']

        with st.container(border=True):
            st.markdown(f"<div class='section-title' style='font-size: 26px;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background: #F8F6F2; border: 1px solid #D9D0C1; padding: 24px; border-radius: 2px; margin-bottom: 32px;"><div style="font-family:'Manrope'; font-weight: 600; color: #8C7B61; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; letter-spacing:1px;">Catatan Peninjau PMO</div><div style="color: var(--text-main); font-size: 15px; font-weight:400; line-height: 1.6;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                nama_proyek = st.text_input("Identitas Proyek", value=row['nama_proyek'])
                manajer_proyek = st.text_input("Manajer Eksekutor", value=row['manajer_proyek'])

                c_owner, c_dept = st.columns(2)
                with c_owner:
                    owner_val = row.get('project_owner', '')
                    owner_idx = PMO_SATKER_OPTIONS.index(owner_val) if owner_val in PMO_SATKER_OPTIONS else 0
                    project_owner = st.selectbox("Project Owner (PMO)", PMO_SATKER_OPTIONS, index=owner_idx)
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
                    
                deskripsi_isu = st.text_area("Rincian Akar Masalah", value=st.session_state[f'rev_desc_{rid}'], height=120)
                dampak_isu = st.text_area("Dampak Terhadap Skala Proyek", value=st.session_state[f'rev_dampak_{rid}'], height=120)
                aktivitas_pencegahan = st.text_area("Rekomendasi Tindakan / Solusi", value=st.session_state[f'rev_prev_{rid}'], height=120)
                tantangan = st.text_area("Tantangan Implementasi Lanjutan", value=st.session_state[f'rev_tant_{rid}'], height=120)
                
                st.write("")
                if st.form_submit_button("Ajukan Kembali Eksemplar"):
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
    st.markdown("<div class='section-title'>Kamar Kurasi PMO</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("Antrean Steril", "Semua masukan pengetahuan telah divalidasi dan diarsipkan secara permanen.")
        return
        
    for _, row in pending_df.iterrows():
        with st.expander(f"Menunggu Kurasi  —  {row['nama_proyek']}"):
            render_knowledge_card_content(row)
            
            st.markdown("<div class='mineral-divider'></div>", unsafe_allow_html=True)
            notes = st.text_area("Umpan Balik Kurator (Wajib diisi jika menolak/revisi)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Hapus Eksemplar", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Tolak / Arsipkan", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Perintah Revisi", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Verifikasi & Sahkan", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>Ekstraksi Master Data</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 26px; margin-bottom: 32px;'>Unduh Arsip Enterprise</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="Unduh Tabular .CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="Unduh Format .XLSX", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 13px; color:var(--text-muted); margin-top: 12px;'>Sistem menuntut modul 'openpyxl' untuk kompilasi Excel.</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN & ROUTING
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA KMS Editorial", layout="wide", initial_sidebar_state="expanded")
    create_mineral_theme()
    inject_mineral_css()
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
        st.markdown("<div style='font-family:\"Playfair Display\", serif; font-size: 24px; font-weight: 600; letter-spacing: 0.05em; color: var(--text-main); margin-bottom: 8px;'>Bukit Asam <span style='font-weight:400; color:var(--accent-gold);'>KMS</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-family:\"Manrope\", sans-serif; font-size: 13px; font-weight: 500; color: var(--text-muted); margin-bottom: 40px; padding: 16px; background: transparent; border: 1px solid var(--border-light); border-radius: 2px;'>ID: <span style='color:var(--text-main); font-weight:600; font-size:14px;'>{st.session_state.username}</span><br>Akses: {role}</div>", unsafe_allow_html=True)
        
        navigation = st.radio("Indeks Navigasi", allowed_pages, label_visibility="collapsed")
        
        st.write("")
        st.write("")
        if st.button("Tutup Sesi"):
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

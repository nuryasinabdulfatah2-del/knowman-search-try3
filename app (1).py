# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION, RBAC Login
Format: Lessons Learned Register (Full Holographic - High Contrast Edition)
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
    "Project Management Office Division": "1-bPwqpCeY4yRtdGpzfZ4UmjmQKSTk7AV",
    "Logistics & Infrastructure Development Sub-Division": "1w7nie08G8ZlXpLJzMV9V-7MytF2LIWr9",
    "Mine Development Sub-Division": "1kVAq06Jep0dLL-dTOpDLqtxR3iugcB4F",
    "Energy Business Development Sub-Division": "14Q949Rt_UNyEKYenuneBZXlgzznUMOnY",
    "Downstream Business Development Sub-Division":"12Hbi8bnngOB6q_IBA9O-jZUNpUJSp9aV",
    "Lainnya": "1Pdkc9LD7XFkFhioznFWIZozp8lyqb_q-" 
}

TIPE_DIVISI_OPTIONS = list(DIVISION_FOLDERS.keys())
KATEGORI_OPTIONS = ["Area perbaikan", "Apa yang berhasil", "Apa yang tidak berhasil"]

KEYWORDS_DESKRIPSI = ["isu", "masalah", "kendala", "terhambat", "deskripsi"]
KEYWORDS_DAMPAK = ["dampak", "akibat", "menyebabkan", "tertunda"]
KEYWORDS_PENCEGAHAN = ["pencegahan", "solusi", "rekomendasi", "memilih"]
KEYWORDS_TANTANGAN = ["tantangan", "risiko", "kemungkinan", "hambatan"]

# --- PLOTLY HIGH CONTRAST HOLOGRAPHIC THEME ---
def create_full_holographic_theme():
    font_family = "'Manrope', sans-serif"
    template = pio.templates["plotly_white"]
    template.layout.font = dict(family=font_family, color="#1A1A24", size=14)
    template.layout.paper_bgcolor = "rgba(255,255,255,0.7)" 
    template.layout.plot_bgcolor = "rgba(255,255,255,0.8)"
    template.layout.colorway = ["#8E2DE2", "#4A00E0", "#0052D4", "#E100FF", "#00C9FF"]
    template.layout.xaxis.showgrid = False
    template.layout.yaxis.showgrid = True
    template.layout.yaxis.gridcolor = "rgba(26, 26, 36, 0.08)"
    template.layout.xaxis.gridcolor = "rgba(26, 26, 36, 0.08)"
    pio.templates["full_holo"] = template
    pio.templates.default = "full_holo"

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
# 6. UI COMPONENTS & CSS (HIGH CONTRAST HOLOGRAPHIC)
# ==============================================================================
def inject_full_holo_css():
    st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Manrope:wght@300;400;500;600;700&display=swap](https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Manrope:wght@300;400;500;600;700&display=swap)');
    
    :root {
        /* Background = Terang/Pastel (Light Holographic) */
        --holo-bg-grad: linear-gradient(120deg, #FFB3E6, #A3E9FF, #C9B3FF, #FFF3B3, #FFB3E6);
        
        /* Teks & Tombol = Gelap/Pejal (Dark/Vivid Holographic) */
        --holo-text-grad: linear-gradient(120deg, #4A00E0, #8E2DE2, #0052D4, #E100FF, #4A00E0);
        
        --text-main: #1A1A24;
        --text-muted: #5A5A6A;
        --white-overlay-strong: rgba(255, 255, 255, 0.90);
        --white-overlay-medium: rgba(255, 255, 255, 0.70);
        --shadow-soft: 0 8px 32px rgba(74, 0, 224, 0.08);
    }

    /* Core Animation for Holographic Canvas */
    @keyframes holo-mesh-bg {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes float {
        0% { transform: translateY(0px) scale(1); }
        50% { transform: translateY(-20px) scale(1.05); }
        100% { transform: translateY(0px) scale(1); }
    }

    /* MAIN HOLOGRAPHIC CANVAS (PASTEL) WITH NOISE FOIL TEXTURE */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background: var(--holo-bg-grad) !important;
        background-size: 300% 300% !important;
        animation: holo-mesh-bg 20s ease-in-out infinite !important;
        font-family: 'Manrope', sans-serif !important;
        color: var(--text-main) !important;
        background-attachment: fixed !important;
        position: relative;
        z-index: 0;
    }
    
    /* Subtle Grain/Foil Texture Overlay */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='[http://www.w3.org/2000/svg'%3E%3Cfilter](http://www.w3.org/2000/svg'%3E%3Cfilter) id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
        opacity: 0.04;
        z-index: -1;
        pointer-events: none;
    }

    /* Organic Deco Blobs / Prisms behind components */
    .stApp::after {
        content: "";
        position: fixed;
        bottom: -10vh; right: -10vw;
        width: 60vw; height: 60vw;
        background: radial-gradient(circle, rgba(163, 233, 255, 0.8), transparent 70%);
        filter: blur(80px);
        z-index: -2;
        animation: float 25s ease-in-out infinite alternate;
        pointer-events: none;
    }

    p, label, li, div { font-family: 'Manrope', sans-serif; font-weight: 500; }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text-main) !important;
        letter-spacing: 0.02em;
        font-weight: 600 !important;
    }

    /* Holographic Accent Text (DARK/VIVID for Contrast) */
    .holo-text {
        background: var(--holo-text-grad);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: holo-mesh-bg 4s linear infinite;
        font-weight: 700;
    }

    /* Navbar / Sidebar (Foil Effect) */
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="stSidebar"] {
        background: linear-gradient(to bottom, var(--white-overlay-strong), var(--white-overlay-medium)), var(--holo-bg-grad) !important;
        background-size: 100% 100%, 300% 300% !important;
        animation: holo-mesh-bg 20s ease-in-out infinite !important;
        backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255,255,255,0.8);
        box-shadow: 4px 0 25px rgba(142, 45, 226, 0.05);
    }
    [data-testid="collapsedControl"] {
        display: flex !important; visibility: visible !important;
        background: var(--white-overlay-strong) !important;
        border: 1px solid rgba(142, 45, 226, 0.3) !important;
        color: #4A00E0 !important;
        border-radius: 50px !important;
        margin: 1rem !important; z-index: 100 !important;
        box-shadow: var(--shadow-soft) !important;
    }
    
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1050px !important; z-index: 2; position: relative;}
    
    /* Typography & Layout */
    .hero-text { 
        font-family: 'Space Grotesk', sans-serif !important; 
        font-size: 76px; 
        font-weight: 600; 
        line-height: 1.1; 
        color: var(--text-main); 
        margin-bottom: 24px;
        letter-spacing: -1.5px;
    }
    .hero-sub { 
        font-size: 19px; 
        font-weight: 400; 
        color: var(--text-muted); 
        margin-bottom: 50px; 
        max-width: 650px; 
        line-height: 1.8;
        letter-spacing: 0.2px;
    }
    .section-title { 
        font-family: 'Space Grotesk', sans-serif !important; 
        font-size: 34px; 
        font-weight: 600; 
        margin-bottom: 40px; 
        color: var(--text-main);
        letter-spacing: -0.5px;
    }

    /* FOIL EFFECT CARDS (Gradient Base + White Overlay) */
    .bento, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {
        background: var(--white-overlay-strong) !important;
        backdrop-filter: blur(15px) !important;
        -webkit-backdrop-filter: blur(15px) !important;
        border: 1px solid #FFFFFF !important;
        box-shadow: var(--shadow-soft) !important;
        border-radius: 20px !important; 
        transition: all 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) !important;
        overflow: hidden;
        padding: 40px !important;
        position: relative;
    }
    [data-testid="stExpander"] { padding: 0 !important; margin-bottom: 24px !important;}
    
    /* Hover effects for Cards */
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover, [data-testid="stExpander"]:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 15px 40px rgba(142, 45, 226, 0.15) !important;
    }

    /* Accordion Details */
    [data-testid="stExpander"] summary {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        font-size: 18px !important;
        color: var(--text-main) !important;
        padding: 24px 32px !important;
        background-color: transparent !important;
        transition: all 0.4s ease !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: rgba(74, 0, 224, 0.05) !important;
    }
    [data-testid="stExpanderDetails"] {
        padding: 8px 32px 32px 32px !important;
        border-top: 1px solid rgba(74, 0, 224, 0.1) !important;
    }

    /* KPI Cards using Dark Vivid Gradient */
    .kpi-big-val { 
        font-family: 'Space Grotesk', sans-serif; 
        font-size: 80px; 
        font-weight: 600; 
        line-height: 1; 
        letter-spacing: -2px;
        background: var(--holo-text-grad);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: holo-mesh-bg 5s linear infinite;
        display: inline-block;
    }
    .kpi-big-title { font-size: 14px; font-weight: 700; color: var(--text-muted); margin-top: 16px; letter-spacing: 2px; text-transform: uppercase;}
    .kpi-small-val { 
        font-family: 'Space Grotesk', sans-serif; 
        font-size: 50px; 
        font-weight: 600; 
        line-height: 1; 
        letter-spacing: -1px;
        background: var(--holo-text-grad);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: holo-mesh-bg 5s linear infinite;
        display: inline-block;
    }
    .kpi-small-title { font-size: 13px; font-weight: 700; color: var(--text-muted); margin-top: 12px; letter-spacing: 1px; text-transform: uppercase;}
    
    /* Card Content Typography */
    .card-meta { font-size: 13px; font-weight: 500; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;}
    .card-section { font-family: 'Space Grotesk', sans-serif; font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--text-main); margin-top: 40px; margin-bottom: 12px; letter-spacing: 1.5px;}
    .card-body { font-size: 15px; font-weight: 400; line-height: 1.8; color: var(--text-main);}
    
    /* Glass Badges */
    .badge { display: inline-block; padding: 6px 14px; border-radius: 40px; font-size: 12px; font-weight: 700; margin-right: 12px; margin-bottom: 8px; letter-spacing: 0.5px; border: 1px solid rgba(142, 45, 226, 0.2); background: rgba(142, 45, 226, 0.05);}
    .badge-status-Pending { color: #8E2DE2; }
    .badge-status-Verified { color: #0052D4; }
    .badge-status-NeedsRevision { color: #B38800; }
    .badge-status-Rejected { color: #E100FF; }
    .badge-kategori { color: var(--text-muted); border-color: rgba(0,0,0,0.1); background:transparent;}
    .badge-tipe { color: var(--text-muted); border-color: rgba(0,0,0,0.1); background:transparent;}
    
    /* GDrive Button (Dark Gradient Hover) */
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 10px; background-color: #FFFFFF; color: #4A00E0 !important; padding: 12px 24px; border-radius: 40px; font-weight: 700; font-size: 14px; text-decoration: none !important; margin-top: 32px; transition: all 0.4s ease; border: 1px solid rgba(74, 0, 224, 0.3); letter-spacing: 0.5px; box-shadow: 0 4px 15px rgba(74, 0, 224, 0.05);}
    .gdrive-link-btn:hover { 
        background: var(--holo-text-grad) !important;
        background-size: 200% auto !important;
        color: #FFFFFF !important;
        box-shadow: 0 8px 25px rgba(74, 0, 224, 0.25);
        transform: translateY(-2px);
        border-color: transparent !important;
    }
    
    /* Inputs inside Container */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { 
        background-color: #FFFFFF !important; 
        border: 1px solid rgba(0,0,0,0.1) !important; 
        border-radius: 12px !important; 
        padding: 16px 20px !important; 
        font-size: 15px; font-weight: 500; 
        color: var(--text-main) !important; 
        transition: all 0.3s ease; 
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { 
        border-color: #8E2DE2 !important;
        box-shadow: 0 0 0 3px rgba(142, 45, 226, 0.15) !important;
    }
    
    /* DARK VIVID HOLOGRAPHIC BUTTONS (Always readable) */
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { 
        background: var(--holo-text-grad) !important; 
        background-size: 200% auto !important;
        color: #FFFFFF !important; /* White text for contrast */
        border-radius: 40px !important; 
        padding: 14px 28px !important; 
        font-weight: 700 !important; 
        font-size: 15px !important; 
        border: none !important; 
        width: 100%; 
        transition: all 0.4s ease !important; 
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: 1px;
        box-shadow: 0 6px 20px rgba(74, 0, 224, 0.2) !important;
    }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { 
        animation: holo-mesh-bg 2s linear infinite !important; /* Shimmer effect */
        box-shadow: 0 10px 30px rgba(74, 0, 224, 0.4) !important; 
        transform: translateY(-3px); 
    }

    /* Role-based button overrides (Targeting Indonesian Words safely) */
    div[data-testid="stButton"] button:has(p:contains("Hapus")) { background: #E2E8F0 !important; color:#1A1A24 !important; box-shadow: none !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Hapus")):hover { background: #FF0055 !important; color:#FFF !important; box-shadow: 0 8px 25px rgba(255, 0, 85, 0.4) !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Tolak")) { background: #FF0055 !important; color:#FFF !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Tolak")):hover { box-shadow: 0 8px 25px rgba(255, 0, 85, 0.4) !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Tuntut")) { background: #FFD966 !important; color:#1A1A24 !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Tuntut")):hover { box-shadow: 0 8px 25px rgba(255, 217, 102, 0.4) !important;}
    
    div[data-testid="stButton"] button:has(p:contains("Sahkan")) { background: #00C9FF !important; color:#FFF !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Sahkan")):hover { box-shadow: 0 8px 25px rgba(0, 201, 255, 0.4) !important;}

    /* Sidebar Radio */
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 14px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; color: var(--text-muted); transition: 0.3s; letter-spacing: 0.5px;}
    div[role="radiogroup"] > label:hover { color: var(--text-main); background: rgba(0,0,0,0.02) !important;}
    div[role="radiogroup"] > label[data-checked="true"] { 
        background: #FFFFFF !important; 
        color: #4A00E0 !important; 
        border-left: 4px solid #4A00E0;
        border-radius: 0 8px 8px 0;
        box-shadow: 0 4px 15px rgba(74, 0, 224, 0.05);
    }
    
    [data-testid="stFileUploadDropzone"] { border-radius: 16px !important; border: 2px dashed rgba(74, 0, 224, 0.3) !important; background-color: #FFFFFF !important; transition: all 0.3s; }
    [data-testid="stFileUploadDropzone"]:hover { 
        background-color: rgba(74, 0, 224, 0.02) !important;
        border-color: #8E2DE2 !important;
    }
    
    /* Custom Wave Divider using Dark Vivid Gradient */
    .holo-wave-divider {
        width: 100%;
        height: 60px;
        margin: 40px 0;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 1200 120' preserveAspectRatio='none' xmlns='[http://www.w3.org/2000/svg'%3E%3Cpath](http://www.w3.org/2000/svg'%3E%3Cpath) d='M321.39,56.44c58-10.79,114.16-30.13,172-41.86,82.39-16.72,168.19-17.73,250.45-.39C823.78,31,906.67,72,985.66,92.83c70.05,18.48,146.53,26.09,214.34,3V0H0V27.35A600.21,600.21,0,0,0,321.39,56.44Z' fill='url(%23darkGrad)' fill-opacity='0.2'/%3E%3Cdefs%3E%3ClinearGradient id='darkGrad' x1='0%25' y1='0%25' x2='100%25' y2='0%25'%3E%3Cstop offset='0%25' stop-color='%234A00E0'/%3E%3Cstop offset='50%25' stop-color='%23E100FF'/%3E%3Cstop offset='100%25' stop-color='%2300C9FF'/%3E%3C/linearGradient%3E%3C/defs%3E%3C/svg%3E");
        background-size: cover;
        background-repeat: no-repeat;
        background-position: center;
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
        <svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        Buka Arsip Dokumen Asli
    </a></div>""" if gdrive_link else ""
    
    kat_badge = f"<span class='badge badge-kategori'>✦ {row.get('kategori', 'Area perbaikan')}</span>"
    tipe_badge = f"<span class='badge badge-tipe'>⊚ {row.get('tipe', '-')}</span>"
    dept_text = row.get('related_department', '-')

    # FORMAT STRING DIPERKETAT UNTUK MENGHINDARI BUG MARKDOWN CODE-BLOCK
    card_html = f"""<div style="padding-bottom: 16px;">
<div class="card-meta">
Eksekutor: <span style="color:#1A1A24; font-weight:700;">{row['manajer_proyek']}</span> &nbsp; • &nbsp; 
Dept: <span style="color:#1A1A24; font-weight:700;">{dept_text}</span> &nbsp; • &nbsp; 
Date: <span style="color:#1A1A24; font-weight:700;">{row['upload_date']}</span>
</div>
<div style="margin-bottom: 32px;">
<span class="badge badge-status-{status_str}">Status: {row['status']}</span>
{kat_badge} {tipe_badge}
</div>
<div class="card-section">Identifikasi Anomali</div>
<div class="card-body">{deskripsi}</div>
<div class="holo-wave-divider" style="height:20px; margin: 24px 0;"></div>
<div class="card-section">Dampak / Spektrum Skala</div>
<div class="card-body">{dampak}</div>
<div class="holo-wave-divider" style="height:20px; margin: 24px 0;"></div>
<div class="card-section">Protokol Solusi Efektif</div>
<div class="card-body" style="font-weight: 700; color: #4A00E0;">{pencegahan}</div>
<div class="holo-wave-divider" style="height:20px; margin: 24px 0;"></div>
<div class="card-section">Limitasi & Tantangan</div>
<div class="card-body">{tantangan}</div>
{gdrive_html}
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="Data Nihil", subtitle="Tidak ada data yang direkam di sektor ini. Mulai inisiasi data baru untuk mengisi basis pengetahuan."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 120px 40px;"><div class="section-title holo-text" style="margin-bottom: 16px; font-size: 32px; border:none;">{title}</div><div class="card-body" style="color: var(--text-muted); font-weight:500;">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_login():
    st.markdown("""
        <div style="text-align: center; margin-top: 15vh; margin-bottom: 60px;">
            <div class="hero-text"><span class="holo-text">Knowledge</span><br>Management System.</div>
            <div class="hero-sub" style="margin: 0 auto;">Pusat Integrasi Pembelajaran Organisasi Divisi PMO PT Bukit Asam Tbk.</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; font-family:\"Space Grotesk\", sans-serif; font-size: 18px; margin-bottom: 32px; font-weight: 600; letter-spacing: 0.5px;'>Otentikasi Akses Keamanan</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="ID Personel...")
            password = st.text_input("Password", type="password", placeholder="Kata Sandi Enkripsi...")
            
            st.write("")
            st.write("")
            if st.button("INISIASI LOGIN"):
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user["role"]
                    st.rerun()
                else:
                    st.error("Kredensial ditolak oleh sistem.")

def view_dashboard(repo):
    st.markdown("""
        <div class="hero-text"><span class="holo-text">Lessons Learned</span><br>Proyek PT Bukit Asam</div>
        <div class="hero-sub">Platform terintegrasi untuk mendokumentasikan, menganalisis, dan mentransformasi isu strategis proyek menjadi strategi perusahaan.</div>
    """, unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
    left, right = st.columns([2.2, 1])
    with left: render_big_kpi("Total Dokumen Tersimpan", len(df))
    with right:
        verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
        render_small_kpi("Tingkat Verifikasi", f"{verified_rate}%")
        
    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 22px;'>Grafik Status</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.8, color="status", color_discrete_map={'Verified': '#0052D4', 'Pending Review': '#8E2DE2', 'Needs Revision': '#E100FF', 'Rejected': '#FF0055'})
            fig1.update_layout(showlegend=False, height=340, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 22px;'>Berdasarkan Divisi</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="tipe", color="tipe", color_discrete_sequence=["#8E2DE2", "#4A00E0", "#0052D4", "#E100FF", "#00C9FF"]) 
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Eksplorasi <span class='holo-text'>Arsip Terpusat</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    
    with st.container(border=True):
        st.markdown("<div style='font-family: \"Space Grotesk\", sans-serif; font-weight: 600; font-size: 18px; margin-bottom: 24px;'>Matriks Filter Pencarian</div>", unsafe_allow_html=True)
        
        search_query = st.text_input("Kata Kunci Spesifik", placeholder="Ketik metrik pencarian (nama proyek, masalah, solusi)...", label_visibility="collapsed")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            selected_kategori = st.selectbox("Kategori Laporan", ["Semua Kategori"] + KATEGORI_OPTIONS)
        with f2:
            selected_tipe = st.selectbox("Pemilik Proyek / Divisi Utama", ["Semua Divisi"] + TIPE_DIVISI_OPTIONS)
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

    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    if df.empty: 
        render_empty_state("Pencarian Tidak Ditemukan", "Sistem tidak mendeteksi dokumen yang selaras dengan filter spesifik Anda.")
    else:
        st.markdown(f"<div style='font-size: 15px; font-weight:600; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;'>Menemukan <b>{len(df)}</b> rekaman data.</div>", unsafe_allow_html=True)
        for _, row in df.iterrows(): 
            with st.expander(f"{row['nama_proyek']}  —  {row['tipe']}"):
                render_knowledge_card_content(row)

def view_upload(repo):
    st.markdown("<div class='section-title'>New <span class='holo-text'>Register</span></div>", unsafe_allow_html=True)
    
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_deskripsi' not in st.session_state: st.session_state.ai_deskripsi = ""
    if 'ai_dampak' not in st.session_state: st.session_state.ai_dampak = ""
    if 'ai_pencegahan' not in st.session_state: st.session_state.ai_pencegahan = ""
    if 'ai_tantangan' not in st.session_state: st.session_state.ai_tantangan = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("Data telah tersimpan. Draf diteruskan ke modul otorisasi PMO.")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 22px; margin-bottom: 24px;'>Ekstraksi Gemini AI</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Unggah dokumen bukti otentik (PDF, DOCX, TXT)", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("MULAI PEMINDAIAN AI"):
            with st.spinner("Memproses sintesis data teks..."):
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
                    st.error("Gagal mengurai teks. Format dokumen mungkin korup.")
                    
    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        with st.form("entry_form", border=False, clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nama_proyek = st.text_input("Nama Proyek", placeholder="Contoh: Optimalisasi Tambang Pit 1...")
            with c2:
                manajer_proyek = st.text_input("Manajer Pelaksana", placeholder="Nama Penanggung Jawab Eksekusi...")
            
            c3, c4 = st.columns(2)
            with c3:
                # Field ini akan mengatur Tipe Divisi / Folder Awan GDrive sekaligus menjadi Project Owner di Database
                tipe = st.selectbox("Pemilik Proyek / Divisi Utama (Folder GDrive)", TIPE_DIVISI_OPTIONS)
            with c4:
                related_department = st.selectbox("Departemen Terkait", ALL_DEPARTMENTS_OPTIONS)

            kategori = st.selectbox("Klasifikasi Kategori", KATEGORI_OPTIONS)
                
            deskripsi_isu = st.text_area("Deskripsi Kendala", value=st.session_state.ai_deskripsi, placeholder="Uraikan anomali operasional...", height=120)
            dampak_isu = st.text_area("Dampak Skala Proyek", value=st.session_state.ai_dampak, placeholder="Implikasi biaya atau timeline...", height=120)
            aktivitas_pencegahan = st.text_area("Protokol Mitigasi", value=st.session_state.ai_pencegahan, placeholder="Langkah konkrit yang direkomendasikan...", height=120)
            tantangan = st.text_area("Risiko Lanjutan", value=st.session_state.ai_tantangan, placeholder="Limitasi dari solusi yang diusulkan...", height=120)
            
            st.write("")
            submitted = st.form_submit_button("SIMPAN & TRANSMISIKAN DATA")
            
            if submitted:
                if nama_proyek and deskripsi_isu:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"Menyinkronkan file ke Cloud Sektor {tipe}..."):
                                target_folder_id = DIVISION_FOLDERS.get(tipe, DIVISION_FOLDERS["Lainnya"])
                                link = upload_to_gdrive(st.session_state.uploaded_file_bytes, st.session_state.uploaded_filename, target_folder_id)
                                if link: auto_gdrive_link = link

                    data = {
                        "nama_proyek": nama_proyek, 
                        "manajer_proyek": manajer_proyek, 
                        "project_owner": tipe, # Diisi otomatis menggunakan dropdown Pemilik Proyek / Divisi
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
                        st.error("Terjadi galat komputasi SQL saat menyimpan ke Database.")
                else:
                    st.error("Parameter Identitas Proyek dan Deskripsi wajib diisi.")

def view_revision(repo):
    st.markdown("<div class='section-title'>Revision <span class='holo-text'>Desk</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("Tidak Ada Antrean", "Tidak ada dokumen yang perlu diperbaiki")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        if f'rev_desc_{rid}' not in st.session_state: st.session_state[f'rev_desc_{rid}'] = row['deskripsi_isu']
        if f'rev_dampak_{rid}' not in st.session_state: st.session_state[f'rev_dampak_{rid}'] = row['dampak_isu']
        if f'rev_prev_{rid}' not in st.session_state: st.session_state[f'rev_prev_{rid}'] = row['aktivitas_pencegahan']
        if f'rev_tant_{rid}' not in st.session_state: st.session_state[f'rev_tant_{rid}'] = row['tantangan']

        with st.container(border=True):
            st.markdown(f"<div class='section-title' style='font-size: 26px; margin-bottom: 24px;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background: rgba(255, 255, 255, 0.9); border: 1px solid #FFD966; padding: 24px; border-radius: 12px; margin-bottom: 32px; box-shadow: 0 4px 15px rgba(255,217,102,0.2);"><div style="font-family:'Space Grotesk'; font-weight: 700; color: #B38800; margin-bottom: 8px; font-size: 13px; text-transform: uppercase; letter-spacing:1px;">Catatan Penolakan PMO</div><div style="color: var(--text-main); font-size: 15px; font-weight:500; line-height: 1.6;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                c1, c2 = st.columns(2)
                with c1:
                    nama_proyek = st.text_input("Identitas Proyek", value=row['nama_proyek'])
                with c2:
                    manajer_proyek = st.text_input("Manajer Pelaksana", value=row['manajer_proyek'])

                c3, c4 = st.columns(2)
                with c3:
                    tipe_idx = TIPE_DIVISI_OPTIONS.index(row['tipe']) if row['tipe'] in TIPE_DIVISI_OPTIONS else (len(TIPE_DIVISI_OPTIONS)-1)
                    tipe = st.selectbox("Pemilik Proyek / Divisi Utama (Folder GDrive)", TIPE_DIVISI_OPTIONS, index=tipe_idx)
                with c4:
                    dept_val = row.get('related_department', '')
                    dept_idx = ALL_DEPARTMENTS_OPTIONS.index(dept_val) if dept_val in ALL_DEPARTMENTS_OPTIONS else 0
                    related_department = st.selectbox("Departemen Afiliasi", ALL_DEPARTMENTS_OPTIONS, index=dept_idx)
                
                kat_idx = KATEGORI_OPTIONS.index(row['kategori']) if row['kategori'] in KATEGORI_OPTIONS else 0
                kategori = st.selectbox("Klasifikasi Isu", KATEGORI_OPTIONS, index=kat_idx)
                    
                deskripsi_isu = st.text_area("Deskripsi Kendala", value=st.session_state[f'rev_desc_{rid}'], height=120)
                dampak_isu = st.text_area("Dampak Skala Proyek", value=st.session_state[f'rev_dampak_{rid}'], height=120)
                aktivitas_pencegahan = st.text_area("Protokol Mitigasi", value=st.session_state[f'rev_prev_{rid}'], height=120)
                tantangan = st.text_area("Risiko Lanjutan", value=st.session_state[f'rev_tant_{rid}'], height=120)
                
                st.write("")
                if st.form_submit_button("AJUKAN ULANG KE PMO"):
                    data = {
                        'nama_proyek': nama_proyek, 
                        'manajer_proyek': manajer_proyek, 
                        'project_owner': tipe, 
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
    st.markdown("<div class='section-title'>Reviewer <span class='holo-text'>Menu</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("Antrean Bersih", "Seluruh matriks draf telah disahkan dan diarsipkan secara rapi.")
        return
        
    for _, row in pending_df.iterrows():
        with st.expander(f"Menunggu Verifikasi  —  {row['nama_proyek']}"):
            render_knowledge_card_content(row)
            
            st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
            notes = st.text_area("Jejak Ulasan Auditor (Wajib diisi jika revisi/reject)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Hapus Entri", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Tolak Register", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Tuntut Revisi", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Sahkan Register", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>Ekstraksi <span class='holo-text'>Data Proyek</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 24px; margin-bottom: 40px;'>Unduh Repositori Fisik</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="EKSPOR BENTUK .CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="EKSPOR BENTUK .XLSX", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 14px; color:var(--text-muted); margin-top: 16px; font-weight:600;'>Library Python 'openpyxl' terdeteksi nonaktif untuk fungsionalitas Excel.</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN & ROUTING
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA Holographic KMS", layout="wide", initial_sidebar_state="expanded")
    create_full_holographic_theme()
    inject_full_holo_css()
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
        st.markdown("<div style='font-family:\"Space Grotesk\", sans-serif; font-size: 24px; font-weight: 700; letter-spacing: -1px; color: var(--text-main); margin-bottom: 32px;'><span class='holo-text'>KMS</span> Platform</div>", unsafe_allow_html=True)
        
        navigation = st.radio("Sektor Navigasi", allowed_pages, label_visibility="collapsed")
        
        st.write("")
        st.write("")
        st.write("")
        st.markdown(f"<div style='font-family:\"Manrope\", sans-serif; font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 24px; padding: 12px; background: rgba(255,255,255,0.9); border-radius:12px; border: 1px solid rgba(142, 45, 226, 0.2);'>Otentikasi:<br><span style='font-family:\"Space Grotesk\"; font-size:16px; font-weight:700; color:#4A00E0;'>{st.session_state.username}</span><br>Clearance: {role}</div>", unsafe_allow_html=True)
        if st.button("Logout"):
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

# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Design System: Clean Bento Box + Semantic Soft Colors
Typography: Caveat (Handwritten Headers) + Inter (Clean Body)
Architecture: Object-Oriented, Cached Repository, Feedback Loop, AI Revise Parsing, Auto GDrive Integration
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
# 1. OPTIONAL IMPORTS (DOCUMENT PARSING & GDRIVE API)
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

# ==============================================================================
# 2. CORE CONFIGURATION & THEME
# ==============================================================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_enterprise.db")

# ⚠️ KONFIGURASI GOOGLE DRIVE (Ganti dengan data Anda nanti)
GDRIVE_CREDENTIALS_FILE = "gdrive_credentials.json" 
GDRIVE_FOLDER_ID = "MASUKKAN_ID_FOLDER_GDRIVE_ANDA_DI_SINI" 

IMPACT_LEVELS = ["High", "Medium", "Low"]
CATEGORY_OPTIONS = [
    "Project Planning", "Financial & Budget", "Risk Management", 
    "Procurement", "Quality Assurance", "Technology & Systems", 
    "Operations", "Other"
]

KEYWORDS_SUMMARY = ["isu", "masalah", "kendala", "permasalahan", "issue", "problem", "hambatan", "deviation"]
KEYWORDS_ROOT_CAUSE = ["akar masalah", "akar penyebab", "disebabkan", "root cause", "sumber masalah", "due to", "caused by"]
KEYWORDS_RECOMMENDATION = ["rekomendasi", "solusi", "usulan", "tindak lanjut", "saran", "mitigasi", "action", "recommend"]

def create_apple_theme():
    font_family = "'Inter', -apple-system, sans-serif"
    template = pio.templates["plotly_white"]
    template.layout.font = dict(family=font_family, color="#1E2A32", size=14)
    template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    template.layout.colorway = ["#6BA3CE", "#8CC8A4", "#9FBFE0", "#B2DAC1", "#4A7C9D", "#629E85"]
    template.layout.xaxis.showgrid = False
    template.layout.yaxis.showgrid = True
    template.layout.yaxis.gridcolor = "rgba(107, 163, 206, 0.1)"
    pio.templates["apple_enterprise"] = template
    pio.templates.default = "apple_enterprise"

# ==============================================================================
# 3. GOOGLE DRIVE UPLOADER ENGINE
# ==============================================================================
def upload_to_gdrive(file_bytes_io, filename):
    """Mengunggah file ke Google Drive dan mengembalikan URL yang bisa dibaca publik"""
    if not GDRIVE_AVAILABLE or not os.path.exists(GDRIVE_CREDENTIALS_FILE):
        return None
        
    try:
        scopes = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_file(GDRIVE_CREDENTIALS_FILE, scopes=scopes)
        service = build('drive', 'v3', credentials=creds)

        file_bytes_io.seek(0)
        media = MediaIoBaseUpload(file_bytes_io, mimetype='application/octet-stream', resumable=True)
        file_metadata = {'name': filename, 'parents': [GDRIVE_FOLDER_ID]}

        # Upload file
        uploaded_file = service.files().create(
            body=file_metadata, media_body=media, fields='id, webViewLink'
        ).execute()
        
        file_id = uploaded_file.get('id')
        
        # Ubah permission agar bisa dibaca siapa saja yang memiliki link (Opsional)
        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return uploaded_file.get('webViewLink')
    except Exception as e:
        st.error(f"Gagal mengunggah ke GDrive: {e}")
        return None

# ==============================================================================
# 4. DATA REPOSITORY (OOP) 
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
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                project TEXT,
                category TEXT,
                impact TEXT,
                status TEXT DEFAULT 'Pending Review',
                summary TEXT,
                root_cause TEXT,
                recommendation TEXT,
                uploader TEXT,
                upload_date TEXT
            )
        """)
        
        cur.execute("PRAGMA table_info(knowledge)")
        columns = [column[1] for column in cur.fetchall()]
        if 'reviewer_notes' not in columns:
            try: cur.execute("ALTER TABLE knowledge ADD COLUMN reviewer_notes TEXT DEFAULT ''")
            except Exception: pass
        if 'gdrive_link' not in columns:
            try: cur.execute("ALTER TABLE knowledge ADD COLUMN gdrive_link TEXT DEFAULT ''")
            except Exception: pass
                
        conn.commit()
        conn.close()

    def fetch_all(self):
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM knowledge ORDER BY id DESC", conn)
        conn.close()
        return df

    def insert(self, data):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO knowledge (title, project, category, impact, status, summary, root_cause, recommendation, uploader, upload_date, reviewer_notes, gdrive_link)
                VALUES (?, ?, ?, ?, 'Pending Review', ?, ?, ?, ?, ?, '', ?)
            """, (
                data['title'], data['project'], data['category'], data['impact'], 
                data['summary'], data['root_cause'], data['recommendation'], 
                data['uploader'], datetime.now().strftime("%d %B %Y"), data.get('gdrive_link', '')
            ))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def update_status(self, record_id, new_status, notes=""):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE knowledge SET status = ?, reviewer_notes = ? WHERE id = ?", (new_status, notes, record_id))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def resubmit_record(self, record_id, data):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE knowledge 
                SET title = ?, project = ?, category = ?, impact = ?, summary = ?, root_cause = ?, recommendation = ?, gdrive_link = ?, status = 'Pending Review'
                WHERE id = ?
            """, (
                data['title'], data['project'], data['category'], data['impact'], 
                data['summary'], data['root_cause'], data['recommendation'], data.get('gdrive_link', ''), record_id
            ))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def delete_record(self, record_id):
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM knowledge WHERE id = ?", (record_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

@st.cache_resource
def get_repository():
    return KnowledgeRepository(DB_PATH)

# ==============================================================================
# 5. AI AUTO-FILL ENGINE
# ==============================================================================
def parse_document(file_bytes, filename) -> str:
    if not file_bytes: return ""
    try:
        filename = filename.lower()
        if filename.endswith(".pdf"):
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(file_bytes) as pdf:
                    return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            elif PYPDF_AVAILABLE:
                reader = PdfReader(file_bytes)
                return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        elif filename.endswith(".docx") and DOCX_AVAILABLE:
            document = docx.Document(file_bytes)
            return "\n".join([p.text for p in document.paragraphs if p.text.strip()])
        elif filename.endswith(".txt"):
            return file_bytes.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return ""

def extract_knowledge(text: str) -> dict:
    res = {"summary": "", "root_cause": "", "recommendation": ""}
    if not text: return res
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s) > 15]
    def extract_by_keywords(kw_list):
        matched = [s for s in sentences if any(kw in s.lower() for kw in kw_list)]
        return " ".join(matched[:3])
    res["summary"] = extract_by_keywords(KEYWORDS_SUMMARY) or (" ".join(sentences[:2]) if sentences else "")
    res["root_cause"] = extract_by_keywords(KEYWORDS_ROOT_CAUSE)
    res["recommendation"] = extract_by_keywords(KEYWORDS_RECOMMENDATION)
    return res

# ==============================================================================
# 6. UI COMPONENTS & CSS (Dipertahankan Persis Sama)
# ==============================================================================
def inject_enterprise_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700;800;900&display=swap');

    :root {
        --bg: #F4F9F8;
        --surface: #FFFFFF;
        --text-primary: #1E2A32;
        --text-secondary: #7A8D99;
        --border: rgba(107, 163, 206, 0.15);
        --accent-blue: #6BA3CE;
        --accent-blue-hover: #5A8DB7;
        --accent-green: #8CC8A4;
        --sem-red-bg: rgba(227, 138, 138, 0.15);
        --sem-red-text: #B85C5C;
        --sem-red-btn: #D98080;
        --sem-yellow-bg: rgba(229, 185, 110, 0.18);
        --sem-yellow-text: #B38634;
        --sem-yellow-btn: #E5B96E;
        --sem-green-bg: rgba(140, 200, 164, 0.2);
        --sem-green-text: #4A8C64;
        --sem-green-btn: #8CC8A4;
        --sem-grey-bg: rgba(122, 141, 153, 0.12);
        --sem-grey-text: #667A8A;
    }
    html, body, p, h1, h2, h3, h4, h5, h6, label, li { font-family: 'Inter', -apple-system, sans-serif !important; }
    .stApp, [data-testid="stAppViewContainer"] { background-color: var(--bg) !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; background-color: var(--surface) !important; color: var(--text-primary) !important; border-radius: 50% !important; box-shadow: 0 4px 12px rgba(107, 163, 206, 0.15) !important; border: 1px solid var(--border) !important; margin: 1rem !important; z-index: 100 !important; transition: all 0.3s ease !important; }
    [data-testid="collapsedControl"]:hover { transform: scale(1.05) !important; background-color: var(--bg) !important; }
    .stAppDeployButton { display: none !important; } 
    footer { display: none !important; }
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1200px !important; }
    .hero-text { font-family: 'Caveat', cursive !important; font-size: 110px; font-weight: 700; line-height: 0.9; color: var(--text-primary); margin-bottom: 24px; letter-spacing: 0.02em; }
    .section-title { font-family: 'Caveat', cursive !important; font-size: 54px; font-weight: 700; margin-bottom: 32px; color: var(--text-primary); }
    .hero-sub { font-size: 20px; font-weight: 500; letter-spacing: -0.01em; color: var(--text-secondary); margin-bottom: 80px; max-width: 600px; line-height: 1.5; }
    .bento { background-color: var(--surface); border-radius: 32px; padding: 40px; margin-bottom: 24px; border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(107, 163, 206, 0.04); transition: transform .35s, box-shadow .35s; height: 100%; }
    .bento:hover { transform: translateY(-6px); box-shadow: 0 35px 60px rgba(107, 163, 206, 0.08); }
    [data-testid="stVerticalBlockBorderWrapper"] { background-color: var(--surface) !important; border-radius: 32px !important; padding: 32px !important; border: 1px solid var(--border) !important; box-shadow: 0 10px 30px rgba(107, 163, 206, 0.04) !important; transition: transform .35s, box-shadow .35s !important; }
    [data-testid="stVerticalBlockBorderWrapper"]:hover { transform: translateY(-6px) !important; box-shadow: 0 35px 60px rgba(107, 163, 206, 0.08) !important; }
    .kpi-big-val { font-size: 96px; font-weight: 800; letter-spacing: -0.05em; line-height: 1; color: var(--text-primary);}
    .kpi-big-title { font-size: 20px; font-weight: 600; color: var(--accent-blue); margin-top: 12px; font-family: 'Inter', sans-serif !important;}
    .kpi-small-val { font-size: 48px; font-weight: 700; letter-spacing: -0.03em; line-height: 1; color: var(--text-primary);}
    .kpi-small-title { font-size: 16px; font-weight: 600; color: var(--text-secondary); margin-top: 8px; font-family: 'Inter', sans-serif !important;}
    .card-title { font-size: 28px; font-weight: 800; letter-spacing: -0.03em; line-height: 1.2; margin-bottom: 8px; color: var(--text-primary); font-family: 'Inter', sans-serif !important;}
    .card-meta { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 32px; font-family: 'Inter', sans-serif !important;}
    .card-section { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent-blue); margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid rgba(107,163,206,0.2); padding-bottom: 4px; font-family: 'Inter', sans-serif !important;}
    .card-body { font-size: 15px; font-weight: 400; line-height: 1.6; color: var(--text-primary); font-family: 'Inter', sans-serif !important;}
    .badge { display: inline-block; padding: 6px 14px; border-radius: 10px; font-size: 12.5px; font-weight: 700; margin-right: 8px; font-family: 'Inter', sans-serif !important;}
    .badge-status-Pending { background-color: var(--sem-grey-bg); color: var(--sem-grey-text); }
    .badge-status-Verified { background-color: var(--sem-green-bg); color: var(--sem-green-text); }
    .badge-status-NeedsRevision { background-color: var(--sem-yellow-bg); color: var(--sem-yellow-text); }
    .badge-status-Rejected { background-color: var(--sem-red-bg); color: var(--sem-red-text); }
    .badge-impact-High { background-color: var(--sem-red-bg); color: var(--sem-red-text); }
    .badge-impact-Medium { background-color: var(--sem-yellow-bg); color: var(--sem-yellow-text); }
    .badge-impact-Low { background-color: var(--sem-grey-bg); color: var(--sem-grey-text); }
    .badge-category { background-color: var(--sem-grey-bg); color: var(--sem-grey-text); border: 1px solid rgba(122, 141, 153, 0.2); }
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 8px; background-color: rgba(107, 163, 206, 0.12); color: var(--accent-blue) !important; padding: 8px 18px; border-radius: 12px; font-weight: 700; font-size: 13.5px; text-decoration: none !important; margin-top: 16px; transition: all 0.2s ease; font-family: 'Inter', sans-serif !important; border: 1px solid rgba(107, 163, 206, 0.25); }
    .gdrive-link-btn:hover { background-color: var(--accent-blue); color: var(--surface) !important; transform: translateY(-2px); }
    .custom-details { margin-top: 20px; }
    .custom-summary { cursor: pointer; font-family: 'Inter', sans-serif !important; font-size: 13px; font-weight: 700; color: var(--accent-blue); background-color: rgba(107, 163, 206, 0.1); padding: 8px 16px; border-radius: 8px; display: inline-block; transition: all 0.2s ease; list-style: none; }
    .custom-summary::-webkit-details-marker { display: none; }
    .custom-summary:hover { background-color: var(--accent-blue); color: var(--surface); }
    .custom-details[open] .custom-summary { background-color: var(--text-secondary); color: var(--surface); margin-bottom: 12px; }
    .details-content { animation: fadeIn 0.3s ease-in-out; padding-top: 16px; border-top: 1px dashed rgba(107, 163, 206, 0.3); }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { background-color: var(--bg) !important; border: 1px solid var(--border) !important; border-radius: 18px !important; padding: 16px 20px !important; font-size: 17px; font-weight: 500; color: var(--text-primary) !important; transition: .2s ease; }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { border-color: var(--accent-blue) !important; box-shadow: 0 0 0 2px rgba(107,163,206,0.3) !important; }
    .stButton button, .stDownloadButton button { background-color: var(--accent-blue) !important; color: var(--surface) !important; border-radius: 20px !important; padding: 16px 32px !important; font-weight: 600 !important; font-size: 17px !important; border: none !important; transition: transform .3s, box-shadow .3s, background-color .3s !important; width: 100%; }
    .stButton button:hover, .stDownloadButton button:hover { background-color: var(--accent-blue-hover) !important; transform: translateY(-2px); box-shadow: 0 15px 30px rgba(107, 163, 206, 0.25) !important; }
    .stButton button p, .stDownloadButton button p { color: var(--surface) !important; margin:0;}
    div[data-testid="stButton"] button:has(p:contains("Reject")) { background-color: var(--sem-red-btn) !important; }
    div[data-testid="stButton"] button:has(p:contains("Reject")):hover { background-color: #C26B6B !important; box-shadow: 0 15px 30px rgba(217, 128, 128, 0.3) !important; }
    div[data-testid="stButton"] button:has(p:contains("Verify")) { background-color: var(--accent-blue) !important; }
    div[data-testid="stButton"] button:has(p:contains("Verify")):hover { background-color: var(--accent-blue-hover) !important; box-shadow: 0 15px 30px rgba(107, 163, 206, 0.25) !important; }
    div[data-testid="stButton"] button:has(p:contains("Revision")) { background-color: var(--sem-yellow-btn) !important; }
    div[data-testid="stButton"] button:has(p:contains("Revision")):hover { background-color: #D4A373 !important; box-shadow: 0 15px 30px rgba(229, 185, 110, 0.3) !important; }
    div[data-testid="stButton"] button:has(p:contains("Delete")) { background-color: var(--text-secondary) !important; }
    div[data-testid="stButton"] button:has(p:contains("Delete")):hover { background-color: var(--text-primary) !important; box-shadow: 0 15px 30px rgba(30, 42, 50, 0.3) !important; }
    .notification { background-color: var(--accent-blue); color: var(--surface); padding: 20px 32px; border-radius: 16px; font-weight: 600; font-size: 17px; text-align: center; margin-bottom: 24px; box-shadow: 0 20px 40px rgba(107,163,206,0.2); }
    [data-testid="stSidebar"] { background-color: var(--surface) !important; border-right: 1px solid var(--border); }
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 12px 20px; border-radius: 12px; font-size: 17px; font-weight: 600; color: var(--text-secondary); transition: .2s; }
    div[role="radiogroup"] > label[data-checked="true"] { background-color: var(--accent-bg) !important; color: var(--accent-blue) !important; }
    div[role="radiogroup"] > label:hover { background-color: var(--bg) !important; }
    [data-testid="stFileUploadDropzone"] { border-radius: 18px !important; border: 1px dashed var(--accent-blue) !important; background-color: var(--bg) !important; }
    </style>
    """, unsafe_allow_html=True)

def render_big_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-big-val">{value}</div><div class="kpi-big-title">{title}</div></div>""", unsafe_allow_html=True)

def render_small_kpi(title, value):
    st.markdown(f"""<div class="bento" style="padding: 30px;"><div class="kpi-small-val">{value}</div><div class="kpi-small-title">{title}</div></div>""", unsafe_allow_html=True)

def render_knowledge_card(row, compact=True):
    status_str = str(row['status']).replace(" Pending Review", "Pending").replace(" ", "")
    impact_str = str(row['impact']).replace(" ", "")
    
    sum_txt = str(row['summary']).replace('\n', '<br>')
    rc_txt = str(row['root_cause']).replace('\n', '<br>')
    rec_txt = str(row['recommendation']).replace('\n', '<br>')
    
    gdrive_link = row['gdrive_link'] if 'gdrive_link' in row.keys() and row['gdrive_link'] else ""
    gdrive_html = f"""<div style="margin-top: 16px;"><a href="{gdrive_link}" target="_blank" class="gdrive-link-btn">📂 Open Google Drive Document</a></div>""" if gdrive_link else ""
    
    if compact:
        is_long = len(str(row['summary'])) > 150
        short_summary = (str(row['summary'])[:150] + "...").replace('\n', '<br>') if is_long else sum_txt
        
        card_html = f"""<div class="bento">
<div class="card-title">{row['title']}</div>
<div class="card-meta">{row['project']} &nbsp;|&nbsp; {row['upload_date']}</div>
<div style="margin-bottom: 24px;">
<span class="badge badge-status-{status_str}">{row['status']}</span>
<span class="badge badge-impact-{impact_str}">{row['impact']} Impact</span>
<span class="badge badge-category">{row['category']}</span>
</div>
<div class="card-section">Summary (Preview)</div>
<div class="card-body">{short_summary}</div>
{gdrive_html}
<details class="custom-details">
<summary class="custom-summary">Show Full Details</summary>
<div class="details-content">
<div class="card-section" style="margin-top:0;">Full Summary</div>
<div class="card-body">{sum_txt}</div>
<div class="card-section">Root Cause</div>
<div class="card-body">{rc_txt}</div>
<div class="card-section">Recommendation</div>
<div class="card-body" style="font-weight: 600;">{rec_txt}</div>
</div>
</details>
</div>"""
    else:
        card_html = f"""<div class="bento">
<div class="card-title">{row['title']}</div>
<div class="card-meta">{row['project']} &nbsp;|&nbsp; {row['upload_date']}</div>
<div style="margin-bottom: 24px;">
<span class="badge badge-status-{status_str}">{row['status']}</span>
<span class="badge badge-impact-{impact_str}">{row['impact']} Impact</span>
<span class="badge badge-category">{row['category']}</span>
</div>
<div class="card-section">Summary</div>
<div class="card-body">{sum_txt}</div>
<div class="card-section">Root Cause</div>
<div class="card-body">{rc_txt}</div>
<div class="card-section">Recommendation</div>
<div class="card-body" style="font-weight: 600;">{rec_txt}</div>
{gdrive_html}
</div>"""
        
    st.markdown(card_html, unsafe_allow_html=True)

def render_notification(message):
    st.markdown(f"<div class='notification'>{message}</div>", unsafe_allow_html=True)

def render_empty_state(title="Knowledge Repository", subtitle="No entries available.<br>Create your first knowledge entry to start building organizational memory."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 80px 40px;">
<div class="section-title" style="margin-bottom: 16px; font-family: 'Inter', sans-serif !important; font-size: 32px;">{title}</div>
<div class="card-body" style="color: var(--text-secondary);">{subtitle}</div>
</div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_dashboard(repo):
    st.markdown("""<div class="hero-text">PT Bukit Asam<br>Knowledge<br>Management</div>
<div class="hero-sub">Capture organizational knowledge and transform operational experience into strategic assets.</div>""", unsafe_allow_html=True)

    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return

    left, right = st.columns([2.2, 1])
    with left:
        render_big_kpi("Total Knowledge Base", len(df))
    with right:
        top, bottom = st.container(), st.container()
        with top:
            verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
            render_small_kpi("Verified", f"{verified_rate}%")
        with bottom:
            high_impact = len(df[df['impact'] == 'High'])
            render_small_kpi("High Impact", high_impact)

    st.write("")
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='card-title' style='font-size: 20px;'>Status Distribution</div>", unsafe_allow_html=True)
            color_map = {'Verified': '#8CC8A4', 'Pending Review': '#A0AEB8', 'Needs Revision': '#E5B96E', 'Rejected': '#D98080'}
            fig1 = px.pie(df, names="status", hole=0.8, color="status", color_discrete_map=color_map)
            fig1.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
            
    with c2:
        with st.container(border=True):
            st.markdown("<div class='card-title' style='font-size: 20px;'>Impact Analysis</div>", unsafe_allow_html=True)
            color_map_impact = {'High': '#D98080', 'Medium': '#E5B96E', 'Low': '#A0AEB8'}
            fig2 = px.histogram(df, x="impact", color="impact", color_discrete_map=color_map_impact)
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Browse Repository</div>", unsafe_allow_html=True)
    compact_mode = st.toggle("Enable Compact View", value=True, help="Sembunyikan detail isu agar tampilan lebih ringkas")
    df = repo.fetch_all()
    search_query = st.text_input("Search", placeholder="Search title, project or keyword...", label_visibility="collapsed")
    if search_query:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]

    st.write("")
    if df.empty: render_empty_state()
    else:
        for _, row in df.iterrows(): render_knowledge_card(row, compact=compact_mode)

def view_upload(repo):
    st.markdown("<div class='section-title'>New Knowledge Entry</div>", unsafe_allow_html=True)
    
    if 'ai_summary' not in st.session_state: st.session_state.ai_summary = ""
    if 'ai_root' not in st.session_state: st.session_state.ai_root = ""
    if 'ai_rec' not in st.session_state: st.session_state.ai_rec = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    with st.container(border=True):
        st.markdown("<div class='card-title' style='font-size: 20px; margin-bottom: 16px;'>AI Document Parsing & Auto-Upload</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: var(--text-secondary); margin-bottom: 16px; font-weight: 500;'>Dokumen yang diunggah di sini akan dibaca oleh AI, dan secara otomatis disimpan ke Google Drive saat Anda menyimpan entri.</div>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Format: PDF, DOCX, TXT", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("Analyze Document"):
            with st.spinner("Extracting knowledge..."):
                file_bytes = io.BytesIO(uploaded_file.read())
                
                # Simpan file di memory agar bisa di-upload ke GDrive nanti
                st.session_state.uploaded_file_bytes = file_bytes
                st.session_state.uploaded_filename = uploaded_file.name
                
                raw_text = parse_document(file_bytes, uploaded_file.name)
                if raw_text:
                    ai_result = extract_knowledge(raw_text)
                    st.session_state.ai_summary = ai_result["summary"]
                    st.session_state.ai_root = ai_result["root_cause"]
                    st.session_state.ai_rec = ai_result["recommendation"]
                    render_notification("Document analyzed. Form populated below.")
                else:
                    st.error("Could not extract text from document.")
    st.write("")
    
    with st.container(border=True):
        with st.form("entry_form", border=False):
            title = st.text_input("Title", placeholder="Entry Title")
            c1, c2 = st.columns(2)
            with c1:
                project = st.text_input("Project", placeholder="Project Name")
                category = st.selectbox("Category", CATEGORY_OPTIONS)
            with c2:
                uploader = st.text_input("Uploader", placeholder="Your Name")
                impact = st.selectbox("Impact", IMPACT_LEVELS)
                
            # Field Gdrive ditiadakan karena prosesnya kini otomatis
            summary = st.text_area("Summary", value=st.session_state.ai_summary, placeholder="Brief description...", height=120)
            root_cause = st.text_area("Root Cause", value=st.session_state.ai_root, placeholder="Underlying issue...", height=120)
            recommendation = st.text_area("Recommendation", value=st.session_state.ai_rec, placeholder="Action plan...", height=120)
            
            st.write("")
            if st.form_submit_button("Save Entry"):
                if title and summary:
                    auto_gdrive_link = ""
                    
                    # Logika Auto-Upload ke GDrive
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and os.path.exists(GDRIVE_CREDENTIALS_FILE):
                            with st.spinner("Mengunggah dokumen asli ke Google Drive..."):
                                link = upload_to_gdrive(st.session_state.uploaded_file_bytes, st.session_state.uploaded_filename)
                                if link: auto_gdrive_link = link
                        else:
                            st.warning("Google Drive API belum dikonfigurasi (credentials.json tidak ditemukan). Tautan GDrive akan dikosongkan.")

                    data = {
                        "title": title, "project": project, "category": category,
                        "impact": impact, "summary": summary, "root_cause": root_cause,
                        "recommendation": recommendation, "uploader": uploader,
                        "gdrive_link": auto_gdrive_link
                    }
                    if repo.insert(data):
                        st.session_state.ai_summary = ""
                        st.session_state.ai_root = ""
                        st.session_state.ai_rec = ""
                        st.session_state.uploaded_file_bytes = None
                        st.session_state.uploaded_filename = ""
                        render_notification("Entry successfully saved.")
                else:
                    st.error("Title and Summary are required.")

def view_revision(repo):
    st.markdown("<div class='section-title'>Revision Desk</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    
    if rev_df.empty:
        render_empty_state("Clean Workspace", "No documents require your revision. Great job!")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        
        if f'rev_sum_{rid}' not in st.session_state: st.session_state[f'rev_sum_{rid}'] = row['summary']
        if f'rev_root_{rid}' not in st.session_state: st.session_state[f'rev_root_{rid}'] = row['root_cause']
        if f'rev_rec_{rid}' not in st.session_state: st.session_state[f'rev_rec_{rid}'] = row['recommendation']
        
        # Simpan state file revisi yang diupload
        if f'rev_file_{rid}' not in st.session_state: st.session_state[f'rev_file_{rid}'] = None
        if f'rev_filename_{rid}' not in st.session_state: st.session_state[f'rev_filename_{rid}'] = ""

        with st.container(border=True):
            st.markdown(f"<div class='card-title' style='font-size: 24px;'>{row['title']}</div>", unsafe_allow_html=True)
            
            st.markdown(f"""
            <div style="background-color: var(--sem-yellow-bg); border-left: 4px solid var(--sem-yellow-text); padding: 16px 20px; border-radius: 12px; margin-bottom: 24px; margin-top: 12px;">
                <div style="font-weight: 700; color: var(--sem-yellow-text); margin-bottom: 4px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; font-family: 'Inter', sans-serif;">PMO Feedback</div>
                <div style="color: var(--text-primary); font-size: 15px; line-height: 1.5; font-family: 'Inter', sans-serif;">{row['reviewer_notes']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<div style='font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;'>Auto-Revise via Document</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 14px; color: var(--text-secondary); margin-bottom: 12px;'>Upload dokumen baru. Dokumen ini akan menggantikan versi lama di Google Drive.</div>", unsafe_allow_html=True)
            
            uploaded_rev = st.file_uploader("Format: PDF, DOCX, TXT", type=["pdf", "txt", "docx"], label_visibility="collapsed", key=f"up_rev_{rid}")
            if uploaded_rev and st.button("Extract Revised Knowledge", key=f"btn_rev_{rid}"):
                with st.spinner("Extracting..."):
                    file_bytes = io.BytesIO(uploaded_rev.read())
                    st.session_state[f'rev_file_{rid}'] = file_bytes
                    st.session_state[f'rev_filename_{rid}'] = uploaded_rev.name
                    
                    raw_text = parse_document(file_bytes, uploaded_rev.name)
                    if raw_text:
                        ai_result = extract_knowledge(raw_text)
                        st.session_state[f'rev_sum_{rid}'] = ai_result["summary"]
                        st.session_state[f'rev_root_{rid}'] = ai_result["root_cause"]
                        st.session_state[f'rev_rec_{rid}'] = ai_result["recommendation"]
                        render_notification("Fields successfully updated from new document!")
                    else:
                        st.error("Failed to extract data.")
            
            st.write("")
            with st.form(f"form_rev_{rid}", border=False):
                title = st.text_input("Title", value=row['title'])
                c1, c2 = st.columns(2)
                with c1:
                    project = st.text_input("Project", value=row['project'])
                    cat_idx = CATEGORY_OPTIONS.index(row['category']) if row['category'] in CATEGORY_OPTIONS else 0
                    category = st.selectbox("Category", CATEGORY_OPTIONS, index=cat_idx)
                with c2:
                    imp_idx = IMPACT_LEVELS.index(row['impact']) if row['impact'] in IMPACT_LEVELS else 0
                    impact = st.selectbox("Impact", IMPACT_LEVELS, index=imp_idx)
                    
                summary = st.text_area("Summary", value=st.session_state[f'rev_sum_{rid}'], height=120)
                root_cause = st.text_area("Root Cause", value=st.session_state[f'rev_root_{rid}'], height=120)
                recommendation = st.text_area("Recommendation", value=st.session_state[f'rev_rec_{rid}'], height=120)
                
                st.write("")
                if st.form_submit_button("Resubmit for Review"):
                    
                    new_gdrive_link = row['gdrive_link']
                    # Auto upload GDrive untuk revisi jika ada file baru yang diunggah
                    if st.session_state[f'rev_file_{rid}']:
                        if GDRIVE_AVAILABLE and os.path.exists(GDRIVE_CREDENTIALS_FILE):
                            link = upload_to_gdrive(st.session_state[f'rev_file_{rid}'], st.session_state[f'rev_filename_{rid}'])
                            if link: new_gdrive_link = link
                    
                    data = {
                        'title': title, 'project': project, 'category': category,
                        'impact': impact, 'summary': summary, 'root_cause': root_cause,
                        'recommendation': recommendation, 'gdrive_link': new_gdrive_link
                    }
                    if repo.resubmit_record(rid, data):
                        # Bersihkan cache revisi
                        for key in [f'rev_sum_{rid}', f'rev_root_{rid}', f'rev_rec_{rid}', f'rev_file_{rid}', f'rev_filename_{rid}']:
                            if key in st.session_state: del st.session_state[key]
                        st.rerun()

def view_approval(repo):
    st.markdown("<div class='section-title'>Knowledge Review</div>", unsafe_allow_html=True)
    compact_mode = st.toggle("Enable Compact View", value=True, help="Sembunyikan detail isu untuk menyortir data lebih cepat")
    st.write("")
    
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("Inbox Zero", "No pending reviews. Workspace is clear.")
        return

    for _, row in pending_df.iterrows():
        render_knowledge_card(row, compact=compact_mode)
        
        with st.container(border=True):
            notes = st.text_area("PMO Feedback (Required if returning for revision)", placeholder="Write your feedback to the uploader here...", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Delete", key=f"del_{row['id']}"):
                    repo.delete_record(row['id'])
                    st.rerun()
            with c2:
                if st.button("Reject (Final)", key=f"rej_{row['id']}"):
                    repo.update_status(row['id'], "Rejected", notes)
                    st.rerun()
            with c3:
                if st.button("Needs Revision", key=f"rev_{row['id']}"):
                    repo.update_status(row['id'], "Needs Revision", notes)
                    st.rerun()
            with c4:
                if st.button("Verify", key=f"ver_{row['id']}"):
                    repo.update_status(row['id'], "Verified", notes)
                    st.rerun()
        st.write("")

def view_export(repo):
    st.markdown("<div class='section-title'>Data Export</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
        
    with st.container(border=True):
        st.markdown("<div class='card-title' style='font-size: 24px; margin-bottom: 8px;'>Export Knowledge Base</div>", unsafe_allow_html=True)
        st.markdown("<div style='color: var(--text-secondary); margin-bottom: 32px; font-weight: 500;'>Download the entire repository data for offline analysis and reporting.</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(label="Download CSV", data=csv_bytes, file_name=f"PTBA_KM_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Knowledge_Base")
                excel_bytes = output.getvalue()
                st.download_button(label="Download Excel", data=excel_bytes, file_name=f"PTBA_KM_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            except Exception:
                st.markdown("<div style='color: var(--text-secondary); font-size: 14px; text-align: center; margin-top: 16px;'>Requires 'openpyxl' module.</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN ROUTING & SIDEBAR
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA KM System", layout="wide", initial_sidebar_state="expanded")
    create_apple_theme()
    inject_enterprise_css()
    repo = get_repository()

    with st.sidebar:
        st.markdown("<div style='font-size: 14px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 24px; padding-left: 10px; font-family: \"Inter\", sans-serif;'>PT Bukit Asam KM</div>", unsafe_allow_html=True)
        navigation = st.radio("Nav", ["Dashboard", "Browse", "New Entry", "Revision Desk", "Approval", "Export"], label_visibility="collapsed")
        st.markdown("<div style='margin-top: 60px; padding-left: 10px; font-size: 12px; font-weight: 600; color: var(--text-secondary); font-family: \"Inter\", sans-serif;'>Repository<br>Version 1.4</div>", unsafe_allow_html=True)

    if navigation == "Dashboard": view_dashboard(repo)
    elif navigation == "Browse": view_browse(repo)
    elif navigation == "New Entry": view_upload(repo)
    elif navigation == "Revision Desk": view_revision(repo)
    elif navigation == "Approval": view_approval(repo)
    elif navigation == "Export": view_export(repo)

if __name__ == "__main__":
    main()

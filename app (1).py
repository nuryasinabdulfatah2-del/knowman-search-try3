# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION
Format: Lessons Learned Register
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

# MAPPING FOLDER G-DRIVE BERDASARKAN TIPE / DIVISI
# Ganti dengan ID Folder masing-masing divisi yang sudah di-share ke email Service Account
DIVISION_FOLDERS = {
    "Human Resources (HR)": "14Q949Rt_UNyEKYenuneBZXlgzznUMOnY",
    "Information Technology (IT)": "1-bPwqpCeY4yRtdGpzfZ4UmjmQKSTk7AV",
    "Finance": "1Pdkc9LD7XFkFhioznFWIZozp8lyqb_q-",
    "Operations": "1kVAq06Jep0dLL-dTOpDLqtxR3iugcB4F",
    "Lainnya": "1Pdkc9LD7XFkFhioznFWIZozp8lyqb_q-" # Folder Default
}

TIPE_DIVISI_OPTIONS = list(DIVISION_FOLDERS.keys())
KATEGORI_OPTIONS = ["Area perbaikan", "Apa yang berhasil", "Apa yang tidak berhasil"]

KEYWORDS_DESKRIPSI = ["isu", "masalah", "kendala", "terhambat", "deskripsi"]
KEYWORDS_DAMPAK = ["dampak", "akibat", "menyebabkan", "tertunda"]
KEYWORDS_PENCEGAHAN = ["pencegahan", "solusi", "rekomendasi", "memilih"]
KEYWORDS_TANTANGAN = ["tantangan", "risiko", "kemungkinan", "hambatan"]

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
# 4. DATA REPOSITORY (NEW SCHEMA: LESSONS LEARNED)
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
                (nama_proyek, manajer_proyek, kategori, tipe, deskripsi_isu, dampak_isu, aktivitas_pencegahan, tantangan, status, upload_date, gdrive_link) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending Review', ?, ?)
            """, (
                data['nama_proyek'], data['manajer_proyek'], data['kategori'], data['tipe'], 
                data['deskripsi_isu'], data['dampak_isu'], data['aktivitas_pencegahan'], data['tantangan'], 
                datetime.now().strftime("%d %B %Y"), data.get('gdrive_link', '')
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
                SET nama_proyek = ?, manajer_proyek = ?, kategori = ?, tipe = ?, deskripsi_isu = ?, dampak_isu = ?, aktivitas_pencegahan = ?, tantangan = ?, gdrive_link = ?, status = 'Pending Review' 
                WHERE id = ?
            """, (
                data['nama_proyek'], data['manajer_proyek'], data['kategori'], data['tipe'], 
                data['deskripsi_isu'], data['dampak_isu'], data['aktivitas_pencegahan'], data['tantangan'], 
                data.get('gdrive_link', ''), record_id
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
    """Membaca file dan mengekstrak teks kasarnya"""
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
    """Menganalisis teks ke dalam format Lessons Learned menggunakan Gemini AI"""
    res = {"deskripsi_isu": "", "dampak_isu": "", "aktivitas_pencegahan": "", "tantangan": ""}
    if not text: return res

    if GEMINI_AVAILABLE and "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Anda adalah analis Lessons Learned Register profesional di industri pertambangan/enterprise.
            Baca teks laporan di bawah ini dan rangkum menjadi 4 bagian spesifik.
            
            WAJIB balas HANYA dengan format JSON persis seperti ini (tanpa tambahan teks apa pun):
            {{
                "deskripsi_isu": "Jelaskan masalah utama yang terjadi secara ringkas...",
                "dampak_isu": "Jelaskan apa akibat dari masalah tersebut terhadap operasional/proyek...",
                "aktivitas_pencegahan": "Jelaskan tindakan korektif atau solusi yang direkomendasikan...",
                "tantangan": "Jelaskan kemungkinan risiko atau hambatan saat menerapkan solusi tersebut..."
            }}

            TEKS DOKUMEN:
            {text[:15000]} 
            """
            response = model.generate_content(prompt)
            
            clean_text = response.text.strip()
            if clean_text.startswith("```json"): clean_text = clean_text[7:]
            elif clean_text.startswith("```"): clean_text = clean_text[3:]
            if clean_text.endswith("```"): clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            ai_data = json.loads(clean_text)
            
            res["deskripsi_isu"] = ai_data.get("deskripsi_isu", "")
            res["dampak_isu"] = ai_data.get("dampak_isu", "")
            res["aktivitas_pencegahan"] = ai_data.get("aktivitas_pencegahan", "")
            res["tantangan"] = ai_data.get("tantangan", "")
            return res
            
        except Exception as e:
            st.error(f"❌ GEMINI GAGAL: {e}")
            
    # Metode Fallback (Keyword Sederhana)
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
# 6. UI COMPONENTS & CSS 
# ==============================================================================
def inject_enterprise_css():
    st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700;800;900&display=swap](https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Inter:wght@400;500;600;700;800;900&display=swap)');
    :root {
        --bg: #F4F9F8; --surface: #FFFFFF; --text-primary: #1E2A32; --text-secondary: #7A8D99;
        --border: rgba(107, 163, 206, 0.15); --accent-blue: #6BA3CE; --accent-blue-hover: #5A8DB7;
        --sem-red-bg: rgba(227, 138, 138, 0.15); --sem-red-text: #B85C5C; --sem-red-btn: #D98080;
        --sem-yellow-bg: rgba(229, 185, 110, 0.18); --sem-yellow-text: #B38634; --sem-yellow-btn: #E5B96E;
        --sem-green-bg: rgba(140, 200, 164, 0.2); --sem-green-text: #4A8C64;
        --sem-grey-bg: rgba(122, 141, 153, 0.12); --sem-grey-text: #667A8A;
        --sem-purple-bg: rgba(147, 112, 219, 0.15); --sem-purple-text: #6A4C9C;
    }
    html, body, p, h1, h2, h3, h4, h5, h6, label, li { font-family: 'Inter', sans-serif !important; }
    .stApp, [data-testid="stAppViewContainer"] { background-color: var(--bg) !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; background-color: var(--surface) !important; color: var(--text-primary) !important; border-radius: 50% !important; box-shadow: 0 4px 12px rgba(107, 163, 206, 0.15) !important; border: 1px solid var(--border) !important; margin: 1rem !important; z-index: 100 !important; }
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1200px !important; }
    .hero-text { font-family: 'Caveat', cursive !important; font-size: 110px; font-weight: 700; line-height: 0.9; color: var(--text-primary); margin-bottom: 24px; }
    .section-title { font-family: 'Caveat', cursive !important; font-size: 54px; font-weight: 700; margin-bottom: 32px; color: var(--text-primary); }
    .hero-sub { font-size: 20px; font-weight: 500; color: var(--text-secondary); margin-bottom: 80px; max-width: 600px; line-height: 1.5; }
    .bento, [data-testid="stVerticalBlockBorderWrapper"] { background-color: var(--surface) !important; border-radius: 32px !important; padding: 32px !important; border: 1px solid var(--border) !important; box-shadow: 0 10px 30px rgba(107, 163, 206, 0.04) !important; transition: transform .35s, box-shadow .35s !important; height: 100%; }
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover { transform: translateY(-6px) !important; box-shadow: 0 35px 60px rgba(107, 163, 206, 0.08) !important; }
    .kpi-big-val { font-size: 96px; font-weight: 800; line-height: 1; color: var(--text-primary);}
    .kpi-big-title { font-size: 20px; font-weight: 600; color: var(--accent-blue); margin-top: 12px;}
    .kpi-small-val { font-size: 48px; font-weight: 700; line-height: 1; color: var(--text-primary);}
    .kpi-small-title { font-size: 16px; font-weight: 600; color: var(--text-secondary); margin-top: 8px;}
    .card-title { font-size: 28px; font-weight: 800; line-height: 1.2; margin-bottom: 8px; color: var(--text-primary);}
    .card-meta { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 32px;}
    .card-section { font-size: 12px; font-weight: 800; text-transform: uppercase; color: var(--accent-blue); margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid rgba(107,163,206,0.2); padding-bottom: 4px;}
    .card-body { font-size: 15px; font-weight: 400; line-height: 1.6; color: var(--text-primary);}
    .badge { display: inline-block; padding: 6px 14px; border-radius: 10px; font-size: 12.5px; font-weight: 700; margin-right: 8px;}
    .badge-status-Pending { background-color: var(--sem-grey-bg); color: var(--sem-grey-text); }
    .badge-status-Verified { background-color: var(--sem-green-bg); color: var(--sem-green-text); }
    .badge-status-NeedsRevision { background-color: var(--sem-yellow-bg); color: var(--sem-yellow-text); }
    .badge-status-Rejected { background-color: var(--sem-red-bg); color: var(--sem-red-text); }
    .badge-kategori { background-color: var(--sem-purple-bg); color: var(--sem-purple-text); border: 1px solid rgba(147, 112, 219, 0.2); }
    .badge-tipe { background-color: var(--sem-blue-bg); color: var(--accent-blue); border: 1px solid rgba(107, 163, 206, 0.2); }
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 8px; background-color: rgba(107, 163, 206, 0.12); color: var(--accent-blue) !important; padding: 8px 18px; border-radius: 12px; font-weight: 700; font-size: 13.5px; text-decoration: none !important; margin-top: 16px; transition: all 0.2s ease; border: 1px solid rgba(107, 163, 206, 0.25); }
    .gdrive-link-btn:hover { background-color: var(--accent-blue); color: var(--surface) !important; transform: translateY(-2px); }
    .custom-details { margin-top: 20px; }
    .custom-summary { cursor: pointer; font-size: 13px; font-weight: 700; color: var(--accent-blue); background-color: rgba(107, 163, 206, 0.1); padding: 8px 16px; border-radius: 8px; display: inline-block; transition: all 0.2s ease; list-style: none; }
    .custom-summary::-webkit-details-marker { display: none; }
    .custom-summary:hover { background-color: var(--accent-blue); color: var(--surface); }
    .custom-details[open] .custom-summary { background-color: var(--text-secondary); color: var(--surface); margin-bottom: 12px; }
    .details-content { animation: fadeIn 0.3s ease-in-out; padding-top: 16px; border-top: 1px dashed rgba(107, 163, 206, 0.3); }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { background-color: var(--bg) !important; border: 1px solid var(--border) !important; border-radius: 18px !important; padding: 16px 20px !important; font-size: 17px; font-weight: 500; color: var(--text-primary) !important; transition: .2s ease; }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { border-color: var(--accent-blue) !important; box-shadow: 0 0 0 2px rgba(107,163,206,0.3) !important; }
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { background-color: var(--accent-blue) !important; color: var(--surface) !important; border-radius: 20px !important; padding: 16px 32px !important; font-weight: 600 !important; font-size: 17px !important; border: none !important; width: 100%; transition: transform .3s, box-shadow .3s !important; }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { background-color: var(--accent-blue-hover) !important; transform: translateY(-2px); box-shadow: 0 15px 30px rgba(107, 163, 206, 0.25) !important; }
    div[data-testid="stButton"] button:has(p:contains("Reject")) { background-color: var(--sem-red-btn) !important; }
    div[data-testid="stButton"] button:has(p:contains("Verify")) { background-color: var(--accent-blue) !important; }
    div[data-testid="stButton"] button:has(p:contains("Revision")) { background-color: var(--sem-yellow-btn) !important; }
    div[data-testid="stButton"] button:has(p:contains("Delete")) { background-color: var(--text-secondary) !important; }
    [data-testid="stSidebar"] { background-color: var(--surface) !important; border-right: 1px solid var(--border); }
    div[role="radiogroup"] > label { background-color: transparent !important; padding: 12px 20px; border-radius: 12px; font-size: 17px; font-weight: 600; color: var(--text-secondary); transition: .2s; }
    div[role="radiogroup"] > label[data-checked="true"] { background-color: var(--bg) !important; color: var(--accent-blue) !important; }
    [data-testid="stFileUploadDropzone"] { border-radius: 18px !important; border: 1px dashed var(--accent-blue) !important; background-color: var(--bg) !important; }
    </style>
    """, unsafe_allow_html=True)

def render_big_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-big-val">{value}</div><div class="kpi-big-title">{title}</div></div>""", unsafe_allow_html=True)

def render_small_kpi(title, value):
    st.markdown(f"""<div class="bento" style="padding: 30px;"><div class="kpi-small-val">{value}</div><div class="kpi-small-title">{title}</div></div>""", unsafe_allow_html=True)

def render_knowledge_card(row, compact=True):
    status_str = str(row['status']).replace(" Pending Review", "Pending").replace(" ", "")
    
    # Text clean up for HTML
    deskripsi = str(row['deskripsi_isu']).replace('\n', '<br>')
    dampak = str(row['dampak_isu']).replace('\n', '<br>')
    pencegahan = str(row['aktivitas_pencegahan']).replace('\n', '<br>')
    tantangan = str(row['tantangan']).replace('\n', '<br>')
    
    gdrive_link = row['gdrive_link'] if 'gdrive_link' in row.keys() and row['gdrive_link'] else ""
    gdrive_html = f"""<div style="margin-top: 16px;"><a href="{gdrive_link}" target="_blank" class="gdrive-link-btn">📂 Open Google Drive Document</a></div>""" if gdrive_link else ""
    
    kat_badge = f"<span class='badge badge-kategori'>{row.get('kategori', 'Area perbaikan')}</span>"
    tipe_badge = f"<span class='badge badge-tipe'>Divisi: {row.get('tipe', '-')}</span>"

    if compact:
        is_long = len(str(row['deskripsi_isu'])) > 120
        short_desc = (str(row['deskripsi_isu'])[:120] + "...").replace('\n', '<br>') if is_long else deskripsi
        card_html = f"""
        <div class="bento">
            <div class="card-title">{row['nama_proyek']}</div>
            <div class="card-meta">PM: {row['manajer_proyek']} &nbsp;|&nbsp; Last Updated: {row['upload_date']}</div>
            <div style="margin-bottom: 24px;">
                <span class="badge badge-status-{status_str}">{row['status']}</span>
                {kat_badge} {tipe_badge}
            </div>
            <div class="card-section">Deskripsi Isu (Preview)</div>
            <div class="card-body">{short_desc}</div>
            {gdrive_html}
            <details class="custom-details">
                <summary class="custom-summary">Show Full Register Details</summary>
                <div class="details-content">
                    <div class="card-section" style="margin-top:0;">Deskripsi Isu</div>
                    <div class="card-body">{deskripsi}</div>
                    <div class="card-section">Dampak Isu</div>
                    <div class="card-body">{dampak}</div>
                    <div class="card-section">Aktivitas Pencegahan yang Dapat Dilakukan</div>
                    <div class="card-body" style="font-weight: 600;">{pencegahan}</div>
                    <div class="card-section">Tantangan yang Mungkin Dihadapi</div>
                    <div class="card-body">{tantangan}</div>
                </div>
            </details>
        </div>"""
    else:
        card_html = f"""
        <div class="bento">
            <div class="card-title">{row['nama_proyek']}</div>
            <div class="card-meta">PM: {row['manajer_proyek']} &nbsp;|&nbsp; Last Updated: {row['upload_date']}</div>
            <div style="margin-bottom: 24px;">
                <span class="badge badge-status-{status_str}">{row['status']}</span>
                {kat_badge} {tipe_badge}
            </div>
            <div class="card-section">Deskripsi Isu</div>
            <div class="card-body">{deskripsi}</div>
            <div class="card-section">Dampak Isu</div>
            <div class="card-body">{dampak}</div>
            <div class="card-section">Aktivitas Pencegahan yang Dapat Dilakukan</div>
            <div class="card-body" style="font-weight: 600;">{pencegahan}</div>
            <div class="card-section">Tantangan yang Mungkin Dihadapi</div>
            <div class="card-body">{tantangan}</div>
            {gdrive_html}
        </div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="Lessons Learned Register", subtitle="Belum ada data yang tersimpan.<br>Buat entri pertama Anda untuk mulai membangun basis data organisasi."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 80px 40px;"><div class="section-title" style="margin-bottom: 16px; font-size: 32px;">{title}</div><div class="card-body" style="color: var(--text-secondary);">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_dashboard(repo):
    st.markdown("""<div class="hero-text">PT Bukit Asam<br>Lessons Learned</div><div class="hero-sub">Register and transform operational challenges into organizational strategic assets.</div>""", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
    left, right = st.columns([2.2, 1])
    with left: render_big_kpi("Total Register Data", len(df))
    with right:
        verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
        render_small_kpi("Verified Data", f"{verified_rate}%")
        
    st.write("")
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='card-title' style='font-size: 20px;'>Status Distribusi</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.8, color="status", color_discrete_map={'Verified': '#8CC8A4', 'Pending Review': '#A0AEB8', 'Needs Revision': '#E5B96E', 'Rejected': '#D98080'})
            fig1.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='card-title' style='font-size: 20px;'>Distribusi per Divisi</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="tipe", color="tipe") # Berubah menjadi visualisasi per tipe/divisi
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Browse Lessons Learned</div>", unsafe_allow_html=True)
    compact_mode = st.toggle("Enable Compact View", value=True)
    df = repo.fetch_all()
    search_query = st.text_input("Search", placeholder="Cari nama proyek, masalah, atau divisi...", label_visibility="collapsed")
    if search_query: df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]
    st.write("")
    if df.empty: render_empty_state()
    else:
        for _, row in df.iterrows(): render_knowledge_card(row, compact=compact_mode)

def view_upload(repo):
    st.markdown("<div class='section-title'>Lessons Learned Register Project</div>", unsafe_allow_html=True)
    
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_deskripsi' not in st.session_state: st.session_state.ai_deskripsi = ""
    if 'ai_dampak' not in st.session_state: st.session_state.ai_dampak = ""
    if 'ai_pencegahan' not in st.session_state: st.session_state.ai_pencegahan = ""
    if 'ai_tantangan' not in st.session_state: st.session_state.ai_tantangan = ""
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("✅ HORE! Dokumen Register berhasil disimpan ke Database!")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='card-title' style='font-size: 20px; margin-bottom: 16px;'>Gemini AI Document Extraction</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload lampiran atau laporan pendukung (Format: PDF, DOCX, TXT)", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("Extract Data with Gemini AI"):
            with st.spinner("Gemini sedang membaca dan menyusun laporan ke dalam 4 format tabel..."):
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
                    st.error("Teks tidak dapat diekstrak dari dokumen tersebut.")
    st.write("")
    
    with st.container(border=True):
        with st.form("entry_form", border=False, clear_on_submit=True):
            nama_proyek = st.text_input("Nama Proyek", placeholder="Contoh: Pembangunan Sistem X...")
            manajer_proyek = st.text_input("Manajer Proyek", placeholder="Nama PM...")
            
            c1, c2 = st.columns(2)
            with c1:
                kategori = st.selectbox("Kategori", KATEGORI_OPTIONS)
            with c2:
                # SEKARANG MENGGUNAKAN DROPDOWN AGAR SESUAI DENGAN NAMA FOLDER DRIVE
                tipe = st.selectbox("Tipe / Divisi (Folder Tujuan)", TIPE_DIVISI_OPTIONS)
                
            deskripsi_isu = st.text_area("Deskripsi Isu", value=st.session_state.ai_deskripsi, placeholder="Tuliskan isu utama...", height=100)
            dampak_isu = st.text_area("Dampak Isu", value=st.session_state.ai_dampak, placeholder="Dampak yang dirasakan...", height=100)
            aktivitas_pencegahan = st.text_area("Aktivitas Pencegahan yang Dapat Dilakukan", value=st.session_state.ai_pencegahan, placeholder="Solusi / mitigasi...", height=100)
            tantangan = st.text_area("Tantangan yang Mungkin Dihadapi", value=st.session_state.ai_tantangan, placeholder="Risiko lanjutan...", height=100)
            
            st.write("")
            submitted = st.form_submit_button("Simpan Register")
            
            if submitted:
                if nama_proyek and deskripsi_isu:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"Mengunggah dokumen ke Folder GDrive Divisi {tipe}..."):
                                # MENGARAHKAN FOLDER BERDASARKAN INPUT TIPE/DIVISI (Bukan Kategori)
                                target_folder_id = DIVISION_FOLDERS.get(tipe, DIVISION_FOLDERS["Lainnya"])
                                link = upload_to_gdrive(st.session_state.uploaded_file_bytes, st.session_state.uploaded_filename, target_folder_id)
                                if link: auto_gdrive_link = link

                    data = {
                        "nama_proyek": nama_proyek, "manajer_proyek": manajer_proyek, 
                        "kategori": kategori, "tipe": tipe, 
                        "deskripsi_isu": deskripsi_isu, "dampak_isu": dampak_isu, 
                        "aktivitas_pencegahan": aktivitas_pencegahan, "tantangan": tantangan,
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
                        st.error("❌ Gagal menyimpan ke Database.")
                else:
                    st.error("Nama Proyek dan Deskripsi Isu wajib diisi!")

def view_revision(repo):
    st.markdown("<div class='section-title'>Revision Desk</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("Meja Kerja Bersih", "Tidak ada dokumen yang membutuhkan revisi.")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        if f'rev_desc_{rid}' not in st.session_state: st.session_state[f'rev_desc_{rid}'] = row['deskripsi_isu']
        if f'rev_dampak_{rid}' not in st.session_state: st.session_state[f'rev_dampak_{rid}'] = row['dampak_isu']
        if f'rev_prev_{rid}' not in st.session_state: st.session_state[f'rev_prev_{rid}'] = row['aktivitas_pencegahan']
        if f'rev_tant_{rid}' not in st.session_state: st.session_state[f'rev_tant_{rid}'] = row['tantangan']

        with st.container(border=True):
            st.markdown(f"<div class='card-title' style='font-size: 24px;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background-color: var(--sem-yellow-bg); border-left: 4px solid var(--sem-yellow-text); padding: 16px 20px; border-radius: 12px; margin-bottom: 24px; margin-top: 12px;"><div style="font-weight: 700; color: var(--sem-yellow-text); margin-bottom: 4px; font-size: 13px; text-transform: uppercase;">Reviewer Notes</div><div style="color: var(--text-primary); font-size: 15px; line-height: 1.5;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                nama_proyek = st.text_input("Nama Proyek", value=row['nama_proyek'])
                manajer_proyek = st.text_input("Manajer Proyek", value=row['manajer_proyek'])
                c1, c2 = st.columns(2)
                with c1:
                    kat_idx = KATEGORI_OPTIONS.index(row['kategori']) if row['kategori'] in KATEGORI_OPTIONS else 0
                    kategori = st.selectbox("Kategori", KATEGORI_OPTIONS, index=kat_idx)
                with c2:
                    # Menyesuaikan form revisi dengan dropdown divisi
                    tipe_idx = TIPE_DIVISI_OPTIONS.index(row['tipe']) if row['tipe'] in TIPE_DIVISI_OPTIONS else (len(TIPE_DIVISI_OPTIONS)-1)
                    tipe = st.selectbox("Tipe / Divisi", TIPE_DIVISI_OPTIONS, index=tipe_idx)
                    
                deskripsi_isu = st.text_area("Deskripsi Isu", value=st.session_state[f'rev_desc_{rid}'], height=100)
                dampak_isu = st.text_area("Dampak Isu", value=st.session_state[f'rev_dampak_{rid}'], height=100)
                aktivitas_pencegahan = st.text_area("Aktivitas Pencegahan", value=st.session_state[f'rev_prev_{rid}'], height=100)
                tantangan = st.text_area("Tantangan", value=st.session_state[f'rev_tant_{rid}'], height=100)
                
                st.write("")
                if st.form_submit_button("Resubmit for Review"):
                    data = {
                        'nama_proyek': nama_proyek, 'manajer_proyek': manajer_proyek, 'kategori': kategori, 'tipe': tipe, 
                        'deskripsi_isu': deskripsi_isu, 'dampak_isu': dampak_isu, 'aktivitas_pencegahan': aktivitas_pencegahan, 
                        'tantangan': tantangan, 'gdrive_link': row['gdrive_link']
                    }
                    if repo.resubmit_record(rid, data):
                        st.rerun()

def view_approval(repo):
    st.markdown("<div class='section-title'>Review & Approval</div>", unsafe_allow_html=True)
    compact_mode = st.toggle("Enable Compact View", value=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    if pending_df.empty:
        render_empty_state("Inbox Kosong", "Semua register telah direview.")
        return
    for _, row in pending_df.iterrows():
        render_knowledge_card(row, compact=compact_mode)
        with st.container(border=True):
            notes = st.text_area("Catatan Reviewer (Wajib diisi jika revisi)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Delete", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Reject", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Revision", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Verify", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>Data Export</div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='card-title' style='font-size: 24px; margin-bottom: 32px;'>Export Lessons Learned Register</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="Download CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="Download Excel", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 14px;'>Membutuhkan library 'openpyxl'</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. MAIN
# ==============================================================================
def main():
    st.set_page_config(page_title="PTBA Lessons Learned", layout="wide", initial_sidebar_state="expanded")
    create_apple_theme()
    inject_enterprise_css()
    repo = get_repository()

    with st.sidebar:
        st.markdown("<div style='font-size: 14px; font-weight: 800; letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 24px;'>PT BUKIT ASAM</div>", unsafe_allow_html=True)
        navigation = st.radio("Nav", ["Dashboard", "Browse", "New Register", "Revision Desk", "Approval", "Export"], label_visibility="collapsed")
        
    if navigation == "Dashboard": view_dashboard(repo)
    elif navigation == "Browse": view_browse(repo)
    elif navigation == "New Register": view_upload(repo)
    elif navigation == "Revision Desk": view_revision(repo)
    elif navigation == "Approval": view_approval(repo)
    elif navigation == "Export": view_export(repo)

if __name__ == "__main__":
    main()

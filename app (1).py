# -*- coding: utf-8 -*-
"""
PT Bukit Asam Knowledge Management System
Architecture: Object-Oriented, Auto GDrive Integration, Dynamic Routing, GEMINI AI INTEGRATION, RBAC Login
Format: Lessons Learned Register (Holographic Edition - JSON Mode Enabled)
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime
import os
import io
import json
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
STATUS_PROYEK_OPTIONS = ["Selesai", "Berjalan Sebagian", "Dihentikan"]

# Kolom baku untuk tabel dinamis
COLS_AKAR_MASALAH = ["Masalah / Isu", "Akar Penyebab", "Dampak terhadap Proyek"]
COLS_METRIK = ["Indikator", "Target", "Aktual", "Keterangan"]
COLS_REKOMENDASI = ["Rekomendasi / Tindakan", "Penanggung Jawab", "Tenggat Waktu", "Status"]

# Fungsi Pembantu untuk Inisialisasi Tabel Kosong yang Aman bagi st.data_editor
def get_empty_df(columns):
    return pd.DataFrame([{col: "" for col in columns}])

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
        st.error(f"Koneksi GDrive terputus: {e}")
        return None

# ==============================================================================
# 4. DATA REPOSITORY (ADAPTED TO NEW TEMPLATE WITH JSON TABLES)
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
                uploader_id TEXT, 
                project_owner TEXT,
                related_department TEXT,
                periode_start TEXT,
                periode_end TEXT,
                status_proyek TEXT,
                ringkasan_proyek TEXT, 
                what_went_well TEXT, 
                what_didnt_go_well TEXT,
                analisis_akar_masalah TEXT,
                metrik_keberhasilan TEXT,
                rekomendasi_tindak_lanjut TEXT,
                key_takeaways TEXT,
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
                (nama_proyek, uploader_id, project_owner, related_department, periode_start, periode_end, status_proyek, 
                ringkasan_proyek, what_went_well, what_didnt_go_well, analisis_akar_masalah, 
                metrik_keberhasilan, rekomendasi_tindak_lanjut, key_takeaways, status, upload_date, gdrive_link) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Review', ?, ?)
            """, (
                data['nama_proyek'], data['uploader_id'], data['project_owner'], data['related_department'],
                data['periode_start'], data['periode_end'], data['status_proyek'], data['ringkasan_proyek'], 
                data['what_went_well'], data['what_didnt_go_well'], data['analisis_akar_masalah'], 
                data['metrik_keberhasilan'], data['rekomendasi_tindak_lanjut'], data['key_takeaways'], 
                datetime.now().strftime("%d %B %Y"), data.get('gdrive_link', '')
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e: 
            st.error(f"Gagal merekam ke database: {e}")
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
                SET nama_proyek = ?, uploader_id = ?, project_owner = ?, related_department = ?, periode_start = ?, periode_end = ?, 
                status_proyek = ?, ringkasan_proyek = ?, what_went_well = ?, what_didnt_go_well = ?, analisis_akar_masalah = ?, 
                metrik_keberhasilan = ?, rekomendasi_tindak_lanjut = ?, key_takeaways = ?, gdrive_link = ?, status = 'Pending Review' 
                WHERE id = ?
            """, (
                data['nama_proyek'], data['uploader_id'], data['project_owner'], data['related_department'],
                data['periode_start'], data['periode_end'], data['status_proyek'], data['ringkasan_proyek'], 
                data['what_went_well'], data['what_didnt_go_well'], data['analisis_akar_masalah'], 
                data['metrik_keberhasilan'], data['rekomendasi_tindak_lanjut'], data['key_takeaways'], 
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
# 5. AI GENERATIVE ENGINE DENGAN JSON MODE
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
    res = {
        "ringkasan_proyek": "", "what_went_well": "", "what_didnt_go_well": "", 
        "analisis_akar_masalah": [], "metrik_keberhasilan": [], 
        "rekomendasi_tindak_lanjut": [], "key_takeaways": ""
    }
    if not text: return res

    if GEMINI_AVAILABLE and "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # MEMAKSA GEMINI UNTUK SELALU MENGHASILKAN JSON MURNI TANPA MARKDOWN
            model = genai.GenerativeModel(
                'gemini-1.5-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            prompt = f"""
            Anda adalah staf PMO profesional di PT Bukit Asam.
            Baca teks laporan di bawah ini dan rangkum isinya sesuai dengan struktur template.
            Untuk bagian berbentuk tabel, hasilkan list of objects (JSON Array) dengan nama kolom yang sesuai.
            
            Gunakan format JSON yang valid persis seperti kerangka ini:
            {{
                "ringkasan_proyek": "Penjelasan latar belakang, tujuan...",
                "what_went_well": "Hal-hal yang berhasil...",
                "what_didnt_go_well": "Hambatan atau kendala...",
                "analisis_akar_masalah": [
                    {{"Masalah / Isu": "...", "Akar Penyebab": "...", "Dampak terhadap Proyek": "..."}}
                ],
                "metrik_keberhasilan": [
                    {{"Indikator": "...", "Target": "...", "Aktual": "...", "Keterangan": "..."}}
                ],
                "rekomendasi_tindak_lanjut": [
                    {{"Rekomendasi / Tindakan": "...", "Penanggung Jawab": "...", "Tenggat Waktu": "...", "Status": "..."}}
                ],
                "key_takeaways": "Pembelajaran utama..."
            }}
            TEKS DOKUMEN:
            {text[:15000]} 
            """
            response = model.generate_content(prompt)
            
            # Karena response_mime_type = application/json, kita bisa melangsungkan parse tanpa regex markdown
            ai_data = json.loads(response.text)
            res.update(ai_data)
            return res
        except Exception as e:
            # Tetap tangkap pesan error jikalau kuota API habis dll.
            print(f"Detail Error AI: {e}")
            pass
            
    res["ringkasan_proyek"] = "Koneksi ke sistem AI gagal atau API Key tidak terbaca. Silakan isi form manual."
    return res

# ==============================================================================
# 6. UI COMPONENTS & CSS (HIGH CONTRAST HOLOGRAPHIC)
# ==============================================================================
def inject_full_holo_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Manrope:wght@300;400;500;600;700&display=swap');
    
    :root {
        --holo-bg-grad: linear-gradient(120deg, #FFB3E6, #A3E9FF, #C9B3FF, #FFF3B3, #FFB3E6);
        --holo-text-grad: linear-gradient(120deg, #4A00E0, #8E2DE2, #0052D4, #E100FF, #4A00E0);
        --text-main: #1A1A24;
        --text-muted: #5A5A6A;
        --white-overlay-strong: rgba(255, 255, 255, 0.90);
        --white-overlay-medium: rgba(255, 255, 255, 0.70);
        --shadow-soft: 0 8px 32px rgba(74, 0, 224, 0.08);
    }

    @keyframes holo-mesh-bg { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    @keyframes float { 0% { transform: translateY(0px) scale(1); } 50% { transform: translateY(-20px) scale(1.05); } 100% { transform: translateY(0px) scale(1); } }

    html, body, .stApp, [data-testid="stAppViewContainer"] { background: var(--holo-bg-grad) !important; background-size: 300% 300% !important; animation: holo-mesh-bg 20s ease-in-out infinite !important; font-family: 'Manrope', sans-serif !important; color: var(--text-main) !important; background-attachment: fixed !important; position: relative; z-index: 0; }
    .stApp::before { content: ""; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E"); opacity: 0.04; z-index: -1; pointer-events: none; }
    .stApp::after { content: ""; position: fixed; bottom: -10vh; right: -10vw; width: 60vw; height: 60vw; background: radial-gradient(circle, rgba(163, 233, 255, 0.8), transparent 70%); filter: blur(80px); z-index: -2; animation: float 25s ease-in-out infinite alternate; pointer-events: none; }

    p, label, li, div { font-family: 'Manrope', sans-serif; font-weight: 500; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Space Grotesk', sans-serif !important; color: var(--text-main) !important; letter-spacing: 0.02em; font-weight: 600 !important; }

    .holo-text { background: var(--holo-text-grad); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: holo-mesh-bg 4s linear infinite; font-weight: 700; }

    header[data-testid="stHeader"] { background-color: transparent !important; z-index: 99 !important; }
    [data-testid="stSidebar"] { background: linear-gradient(to bottom, var(--white-overlay-strong), var(--white-overlay-medium)), var(--holo-bg-grad) !important; background-size: 100% 100%, 300% 300% !important; animation: holo-mesh-bg 20s ease-in-out infinite !important; backdrop-filter: blur(15px); border-right: 1px solid rgba(255,255,255,0.8); box-shadow: 4px 0 25px rgba(142, 45, 226, 0.05); }
    [data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; background: var(--white-overlay-strong) !important; border: 1px solid rgba(142, 45, 226, 0.3) !important; color: #4A00E0 !important; border-radius: 50px !important; margin: 1rem !important; z-index: 100 !important; box-shadow: var(--shadow-soft) !important; }
    
    .stAppDeployButton, footer { display: none !important; } 
    .block-container { padding-top: 5rem !important; padding-bottom: 6rem !important; max-width: 1050px !important; z-index: 2; position: relative;}
    
    .hero-text { font-family: 'Space Grotesk', sans-serif !important; font-size: 76px; font-weight: 600; line-height: 1.1; color: var(--text-main); margin-bottom: 24px; letter-spacing: -1.5px; }
    .hero-sub { font-size: 19px; font-weight: 400; color: var(--text-muted); margin-bottom: 50px; max-width: 650px; line-height: 1.8; letter-spacing: 0.2px; }
    .section-title { font-family: 'Space Grotesk', sans-serif !important; font-size: 34px; font-weight: 600; margin-bottom: 40px; color: var(--text-main); letter-spacing: -0.5px; }

    .bento, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] { background: var(--white-overlay-strong) !important; backdrop-filter: blur(15px) !important; border: 1px solid #FFFFFF !important; box-shadow: var(--shadow-soft) !important; border-radius: 20px !important; transition: all 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) !important; overflow: hidden; padding: 40px !important; position: relative; }
    [data-testid="stExpander"] { padding: 0 !important; margin-bottom: 24px !important;}
    .bento:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover, [data-testid="stExpander"]:hover { transform: translateY(-4px) !important; box-shadow: 0 15px 40px rgba(142, 45, 226, 0.15) !important; }

    [data-testid="stExpander"] summary { font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; font-size: 18px !important; color: var(--text-main) !important; padding: 24px 32px !important; background-color: transparent !important; transition: all 0.4s ease !important; }
    [data-testid="stExpander"] summary:hover { background-color: rgba(74, 0, 224, 0.05) !important; }
    [data-testid="stExpanderDetails"] { padding: 8px 32px 32px 32px !important; border-top: 1px solid rgba(74, 0, 224, 0.1) !important; }

    .kpi-big-val { font-family: 'Space Grotesk', sans-serif; font-size: 80px; font-weight: 600; line-height: 1; letter-spacing: -2px; background: var(--holo-text-grad); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: holo-mesh-bg 5s linear infinite; display: inline-block; }
    .kpi-big-title { font-size: 14px; font-weight: 700; color: var(--text-muted); margin-top: 16px; letter-spacing: 2px; text-transform: uppercase;}
    .kpi-small-val { font-family: 'Space Grotesk', sans-serif; font-size: 50px; font-weight: 600; line-height: 1; letter-spacing: -1px; background: var(--holo-text-grad); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: holo-mesh-bg 5s linear infinite; display: inline-block; }
    .kpi-small-title { font-size: 13px; font-weight: 700; color: var(--text-muted); margin-top: 12px; letter-spacing: 1px; text-transform: uppercase;}
    
    .card-meta { font-size: 14px; font-weight: 500; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px; line-height: 1.6;}
    .card-section { font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700; color: var(--text-main); margin-top: 36px; margin-bottom: 16px; letter-spacing: 0.5px;}
    .card-body { font-size: 15px; font-weight: 400; line-height: 1.7; color: var(--text-main);}
    
    /* HTML Table rendering within cards */
    .holo-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 14px; background: rgba(255,255,255,0.5); border-radius: 8px; overflow: hidden; }
    .holo-table th { background: rgba(142, 45, 226, 0.08); color: var(--text-main); padding: 12px; border: 1px solid rgba(0,0,0,0.05); text-align: left; font-weight: 700; font-family: 'Space Grotesk', sans-serif; }
    .holo-table td { padding: 12px; border: 1px solid rgba(0,0,0,0.05); color: var(--text-muted); }
    
    .badge { display: inline-block; padding: 6px 14px; border-radius: 40px; font-size: 12px; font-weight: 700; margin-right: 12px; margin-bottom: 8px; letter-spacing: 0.5px; border: 1px solid rgba(142, 45, 226, 0.2); background: rgba(142, 45, 226, 0.05);}
    .badge-status-Pending { color: #8E2DE2; }
    .badge-status-Verified { color: #0052D4; }
    .badge-status-NeedsRevision { color: #B38800; }
    .badge-status-Rejected { color: #E100FF; }
    
    .gdrive-link-btn { display: inline-flex; align-items: center; gap: 10px; background-color: #FFFFFF; color: #4A00E0 !important; padding: 12px 24px; border-radius: 40px; font-weight: 700; font-size: 14px; text-decoration: none !important; margin-top: 32px; transition: all 0.4s ease; border: 1px solid rgba(74, 0, 224, 0.3); letter-spacing: 0.5px; box-shadow: 0 4px 15px rgba(74, 0, 224, 0.05);}
    .gdrive-link-btn:hover { background: var(--holo-text-grad) !important; background-size: 200% auto !important; color: #FFFFFF !important; box-shadow: 0 8px 25px rgba(74, 0, 224, 0.25); transform: translateY(-2px); border-color: transparent !important; }
    
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div { background-color: #FFFFFF !important; border: 1px solid rgba(0,0,0,0.1) !important; border-radius: 12px !important; padding: 16px 20px !important; font-size: 15px; font-weight: 500; color: var(--text-main) !important; transition: all 0.3s ease; }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within { border-color: #8E2DE2 !important; box-shadow: 0 0 0 3px rgba(142, 45, 226, 0.15) !important; }
    
    .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button { background: var(--holo-text-grad) !important; background-size: 200% auto !important; color: #FFFFFF !important; border-radius: 40px !important; padding: 14px 28px !important; font-weight: 700 !important; font-size: 15px !important; border: none !important; width: 100%; transition: all 0.4s ease !important; font-family: 'Space Grotesk', sans-serif !important; letter-spacing: 1px; box-shadow: 0 6px 20px rgba(74, 0, 224, 0.2) !important; }
    .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover { animation: holo-mesh-bg 2s linear infinite !important; box-shadow: 0 10px 30px rgba(74, 0, 224, 0.4) !important; transform: translateY(-3px); }

    div[data-testid="stButton"] button:has(p:contains("Hapus")) { background: #E2E8F0 !important; color:#1A1A24 !important; box-shadow: none !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Hapus")):hover { background: #FF0055 !important; color:#FFF !important; box-shadow: 0 8px 25px rgba(255, 0, 85, 0.4) !important;}
    div[data-testid="stButton"] button:has(p:contains("Tolak")) { background: #FF0055 !important; color:#FFF !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Tolak")):hover { box-shadow: 0 8px 25px rgba(255, 0, 85, 0.4) !important;}
    div[data-testid="stButton"] button:has(p:contains("Tuntut")) { background: #FFD966 !important; color:#1A1A24 !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Tuntut")):hover { box-shadow: 0 8px 25px rgba(255, 217, 102, 0.4) !important;}
    div[data-testid="stButton"] button:has(p:contains("Sahkan")) { background: #00C9FF !important; color:#FFF !important; border:none !important;}
    div[data-testid="stButton"] button:has(p:contains("Sahkan")):hover { box-shadow: 0 8px 25px rgba(0, 201, 255, 0.4) !important;}

    div[role="radiogroup"] > label { background-color: transparent !important; padding: 14px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; color: var(--text-muted); transition: 0.3s; letter-spacing: 0.5px;}
    div[role="radiogroup"] > label:hover { color: var(--text-main); background: rgba(0,0,0,0.02) !important;}
    div[role="radiogroup"] > label[data-checked="true"] { background: #FFFFFF !important; color: #4A00E0 !important; border-left: 4px solid #4A00E0; border-radius: 0 8px 8px 0; box-shadow: 0 4px 15px rgba(74, 0, 224, 0.05); }
    
    [data-testid="stFileUploadDropzone"] { border-radius: 16px !important; border: 2px dashed rgba(74, 0, 224, 0.3) !important; background-color: #FFFFFF !important; transition: all 0.3s; }
    [data-testid="stFileUploadDropzone"]:hover { background-color: rgba(74, 0, 224, 0.02) !important; border-color: #8E2DE2 !important; }
    
    .holo-wave-divider {
        width: 100%; height: 60px; margin: 40px 0;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 1200 120' preserveAspectRatio='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M321.39,56.44c58-10.79,114.16-30.13,172-41.86,82.39-16.72,168.19-17.73,250.45-.39C823.78,31,906.67,72,985.66,92.83c70.05,18.48,146.53,26.09,214.34,3V0H0V27.35A600.21,600.21,0,0,0,321.39,56.44Z' fill='url(%23darkGrad)' fill-opacity='0.15'/%3E%3Cdefs%3E%3ClinearGradient id='darkGrad' x1='0%25' y1='0%25' x2='100%25' y2='0%25'%3E%3Cstop offset='0%25' stop-color='%234A00E0'/%3E%3Cstop offset='50%25' stop-color='%23E100FF'/%3E%3Cstop offset='100%25' stop-color='%2300C9FF'/%3E%3C/linearGradient%3E%3C/defs%3E%3C/svg%3E");
        background-size: cover; background-repeat: no-repeat; background-position: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Helper function to convert JSON string to HTML Table
def json_to_html_table(json_str, columns):
    try:
        data = json.loads(json_str)
        if not data or len(data) == 0:
            return "<div class='card-body' style='color:#a0a0a0;'>Data tidak diisi.</div>"
        
        df = pd.DataFrame(data)
        # Ensure columns match even if missing
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns] 
        
        # Build raw HTML to apply specific css classes smoothly
        html = "<table class='holo-table'><thead><tr>"
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"
        
        for _, row in df.iterrows():
            html += "<tr>"
            for col in columns:
                val = str(row[col]).replace('\n', '<br>')
                html += f"<td>{val}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html
    except Exception:
        return "<div class='card-body' style='color:#a0a0a0;'>Format tabel tidak valid.</div>"

def render_big_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-big-val">{value}</div><div class="kpi-big-title">{title}</div></div>""", unsafe_allow_html=True)

def render_small_kpi(title, value):
    st.markdown(f"""<div class="bento"><div class="kpi-small-val">{value}</div><div class="kpi-small-title">{title}</div></div>""", unsafe_allow_html=True)

def render_knowledge_card_content(row):
    status_str = str(row['status']).replace(" Pending Review", "Pending").replace(" ", "")
    
    # Text Replace for HTML
    ringkasan = str(row['ringkasan_proyek']).replace('\n', '<br>')
    went_well = str(row['what_went_well']).replace('\n', '<br>')
    didnt_go_well = str(row['what_didnt_go_well']).replace('\n', '<br>')
    takeaways = str(row['key_takeaways']).replace('\n', '<br>')
    
    # Convert JSON Strings to HTML Tables
    html_akar = json_to_html_table(row['analisis_akar_masalah'], COLS_AKAR_MASALAH)
    html_metrik = json_to_html_table(row['metrik_keberhasilan'], COLS_METRIK)
    html_rekomendasi = json_to_html_table(row['rekomendasi_tindak_lanjut'], COLS_REKOMENDASI)

    gdrive_link = row['gdrive_link'] if 'gdrive_link' in row.keys() and row['gdrive_link'] else ""
    gdrive_html = f"""<div><a href="{gdrive_link}" target="_blank" class="gdrive-link-btn">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        Akses Dokumen Fisik
    </a></div>""" if gdrive_link else ""
    
    dept_text = row.get('related_department', '-')
    periode = f"{row['periode_start']} hingga {row['periode_end']}"

    card_html = f"""<div style="padding-bottom: 16px;">
<div class="card-meta">
    Tim/Departemen: <span style="color:#1A1A24; font-weight:700;">{dept_text}</span> &nbsp; • &nbsp; 
    Periode Proyek: <span style="color:#1A1A24; font-weight:700;">{periode}</span> &nbsp; • &nbsp; 
    Dibuat: <span style="color:#1A1A24; font-weight:700;">{row['upload_date']}</span>
</div>
<div style="margin-bottom: 32px;">
    <span class="badge badge-status-{status_str}">Status Laporan: {row['status']}</span>
    <span class="badge" style="border-color:rgba(0,0,0,0.1);">Status Proyek: {row['status_proyek']}</span>
</div>

<div class="card-section">1. Ringkasan Proyek</div>
<div class="card-body">{ringkasan}</div>

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">2. Apa yang Berjalan Baik (What Went Well)</div>
<div class="card-body">{went_well}</div>

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">3. Tantangan dan Kendala (What Didn't Go Well)</div>
<div class="card-body">{didnt_go_well}</div>

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">4. Analisis Akar Masalah</div>
{html_akar}

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">5. Metrik Keberhasilan Proyek</div>
{html_metrik}

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">6. Rekomendasi dan Rencana Tindak Lanjut</div>
{html_rekomendasi}

<div class="holo-wave-divider" style="height:15px; margin: 16px 0; opacity: 0.5;"></div>

<div class="card-section">7. Poin Pembelajaran Utama (Key Takeaways)</div>
<div class="card-body">{takeaways}</div>

<div style="margin-top: 32px;">{gdrive_html}</div>
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_empty_state(title="Data Nihil", subtitle="Belum ada rekam jejak pada folder ini. Silakan mulai entri pertamamu."):
    st.markdown(f"""<div class="bento" style="text-align: center; padding: 120px 40px;"><div class="section-title holo-text" style="margin-bottom: 16px; font-size: 32px; border:none;">{title}</div><div class="card-body" style="color: var(--text-muted); font-weight:500;">{subtitle}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# 7. PAGE VIEWS
# ==============================================================================
def view_login():
    st.markdown("""
        <div style="text-align: center; margin-top: 15vh; margin-bottom: 60px;">
            <div class="hero-text"><span class="holo-text">Knowledge</span><br>Management System</div>
            <div class="hero-sub" style="margin: 0 auto;">Pusat Integrasi Pembelajaran Organisasi PT Bukit Asam Tbk.</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; font-family:\"Space Grotesk\", sans-serif; font-size: 18px; margin-bottom: 32px; font-weight: 600; letter-spacing: 0.5px;'>Masuk ke Dashboard</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Ketik ID kamu...")
            password = st.text_input("Password", type="password", placeholder="Kata Sandi...")
            
            st.write("")
            st.write("")
            if st.button("LANJUTKAN"):
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user["role"]
                    st.rerun()
                else:
                    st.error("Gagal masuk. Periksa kembali ID atau kata sandi.")

def view_dashboard(repo):
    st.markdown("""
        <div class="hero-text"><span class="holo-text">Lessons Learned</span><br>Proyek PT Bukit Asam</div>
        <div class="hero-sub">Platform terintegrasi untuk mendokumentasikan, menganalisis, dan meramu strategi operasional ke depan.</div>
    """, unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty:
        render_empty_state()
        return
    left, right = st.columns([2.2, 1])
    with left: render_big_kpi("Dokumen Tersimpan", len(df))
    with right:
        verified_rate = int((len(df[df['status'] == 'Verified']) / len(df)) * 100) if len(df) > 0 else 0
        render_small_kpi("Telah Terverifikasi", f"{verified_rate}%")
        
    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 22px;'>Persentase Status</div>", unsafe_allow_html=True)
            fig1 = px.pie(df, names="status", hole=0.8, color="status", color_discrete_map={'Verified': '#0052D4', 'Pending Review': '#8E2DE2', 'Needs Revision': '#E100FF', 'Rejected': '#FF0055'})
            fig1.update_layout(showlegend=False, height=340, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown("<div class='section-title' style='font-size: 22px;'>Distribusi per Divisi</div>", unsafe_allow_html=True)
            fig2 = px.histogram(df, y="project_owner", color="project_owner", color_discrete_sequence=["#8E2DE2", "#4A00E0", "#0052D4", "#E100FF", "#00C9FF"]) 
            fig2.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340, margin=dict(t=20, b=20, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

def view_browse(repo):
    st.markdown("<div class='section-title'>Eksplorasi <span class='holo-text'>Arsip Pengetahuan</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    
    with st.container(border=True):
        st.markdown("<div style='font-family: \"Space Grotesk\", sans-serif; font-weight: 600; font-size: 18px; margin-bottom: 24px;'>Kolom Pencarian</div>", unsafe_allow_html=True)
        
        search_query = st.text_input("Kata Kunci", placeholder="Bisa cari berdasarkan nama proyek atau isi kendalanya...", label_visibility="collapsed")
        
        f1, f2 = st.columns(2)
        with f1:
            selected_tipe = st.selectbox("Pemilik Proyek / Divisi Utama", ["Semua Divisi"] + TIPE_DIVISI_OPTIONS)
        with f2:
            STATUS_OPTIONS = ["Semua Status", "Verified", "Pending Review", "Needs Revision", "Rejected"]
            selected_status = st.selectbox("Status Verifikasi", STATUS_OPTIONS)

    if selected_tipe != "Semua Divisi":
        df = df[df['project_owner'] == selected_tipe]
    if selected_status != "Semua Status":
        df = df[df['status'] == selected_status]
    if search_query:
        df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]

    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    if df.empty: 
        render_empty_state("Tidak Ada Dokumen", "Wah, sepertinya tidak ada arsip yang cocok dengan pencarianmu.")
    else:
        st.markdown(f"<div style='font-size: 15px; font-weight:600; color: var(--text-muted); margin-bottom: 24px; letter-spacing: 0.5px;'>Menemukan <b>{len(df)}</b> rekaman.</div>", unsafe_allow_html=True)
        for _, row in df.iterrows(): 
            with st.expander(f"{row['nama_proyek']}  —  {row['project_owner']}"):
                render_knowledge_card_content(row)

def view_upload(repo):
    st.markdown("<div class='section-title'>Formulir <span class='holo-text'>Baru</span></div>", unsafe_allow_html=True)
    
    # Initialize session states for form
    if 'save_success' not in st.session_state: st.session_state.save_success = False
    if 'ai_ringkasan' not in st.session_state: st.session_state.ai_ringkasan = ""
    if 'ai_went_well' not in st.session_state: st.session_state.ai_went_well = ""
    if 'ai_didnt_go_well' not in st.session_state: st.session_state.ai_didnt_go_well = ""
    if 'ai_takeaways' not in st.session_state: st.session_state.ai_takeaways = ""
    
    # Session state for dynamic tables, forced to object types to avoid arrow schema errors
    if 'ai_akar_masalah' not in st.session_state: 
        st.session_state.ai_akar_masalah = get_empty_df(COLS_AKAR_MASALAH)
    if 'ai_metrik' not in st.session_state: 
        st.session_state.ai_metrik = get_empty_df(COLS_METRIK)
    if 'ai_rekomendasi' not in st.session_state: 
        st.session_state.ai_rekomendasi = get_empty_df(COLS_REKOMENDASI)
        
    if 'uploaded_file_bytes' not in st.session_state: st.session_state.uploaded_file_bytes = None
    if 'uploaded_filename' not in st.session_state: st.session_state.uploaded_filename = ""
    
    if st.session_state.save_success:
        st.success("Laporan berhasil disubmit dan akan segera diperiksa oleh PMO.")
        st.session_state.save_success = False
        
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 22px; margin-bottom: 24px;'>Bantu Isi dengan AI</div>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Punya laporannya dalam bentuk PDF atau Word? Unggah di sini, biar AI bantu susun poin-poinnya.", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if uploaded_file and st.button("MULAI ANALISIS"):
            with st.spinner("Membaca dan memetakan dokumen ke dalam template..."):
                file_bytes = io.BytesIO(uploaded_file.read())
                st.session_state.uploaded_file_bytes = file_bytes
                st.session_state.uploaded_filename = uploaded_file.name
                
                raw_text = parse_document(file_bytes, uploaded_file.name)
                if raw_text:
                    ai_result = extract_knowledge(raw_text)
                    st.session_state.ai_ringkasan = ai_result.get("ringkasan_proyek", "")
                    st.session_state.ai_went_well = ai_result.get("what_went_well", "")
                    st.session_state.ai_didnt_go_well = ai_result.get("what_didnt_go_well", "")
                    st.session_state.ai_takeaways = ai_result.get("key_takeaways", "")
                    
                    # Convert AI arrays to pandas DataFrame safely and cast to string to avoid PyArrow mixed type errors
                    raw_akar = ai_result.get("analisis_akar_masalah", [])
                    if isinstance(raw_akar, list):
                        st.session_state.ai_akar_masalah = pd.DataFrame(raw_akar, columns=COLS_AKAR_MASALAH).fillna("").astype(str) if len(raw_akar) > 0 else get_empty_df(COLS_AKAR_MASALAH)
                    else:
                        st.session_state.ai_akar_masalah = get_empty_df(COLS_AKAR_MASALAH)
                    
                    raw_metrik = ai_result.get("metrik_keberhasilan", [])
                    if isinstance(raw_metrik, list):
                        st.session_state.ai_metrik = pd.DataFrame(raw_metrik, columns=COLS_METRIK).fillna("").astype(str) if len(raw_metrik) > 0 else get_empty_df(COLS_METRIK)
                    else:
                        st.session_state.ai_metrik = get_empty_df(COLS_METRIK)
                    
                    raw_rek = ai_result.get("rekomendasi_tindak_lanjut", [])
                    if isinstance(raw_rek, list):
                        st.session_state.ai_rekomendasi = pd.DataFrame(raw_rek, columns=COLS_REKOMENDASI).fillna("").astype(str) if len(raw_rek) > 0 else get_empty_df(COLS_REKOMENDASI)
                    else:
                        st.session_state.ai_rekomendasi = get_empty_df(COLS_REKOMENDASI)
                    
                    st.rerun() 
                else:
                    st.error("Oops! Sepertinya dokumen tersebut kosong atau formatnya sulit dibaca.")
                    
    st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 26px; margin-bottom: 32px;'>Dokumen Lessons Learned</div>", unsafe_allow_html=True)
        with st.form("entry_form", border=False, clear_on_submit=True):
            
            nama_proyek = st.text_input("Nama Proyek", placeholder="Tulis judul yang jelas, misal: Pembangunan Gudang X...")
            
            c1, c2 = st.columns(2)
            with c1:
                periode_start = st.date_input("Tanggal Mulai")
            with c2:
                periode_end = st.date_input("Tanggal Selesai")
                
            c3, c4 = st.columns(2)
            with c3:
                status_proyek = st.selectbox("Status Proyek Saat Ini", STATUS_PROYEK_OPTIONS)
            with c4:
                tipe = st.selectbox("Pemilik Proyek / Divisi Utama (Folder GDrive)", TIPE_DIVISI_OPTIONS)
            
            related_department = st.selectbox("Tim / Departemen yang Terlibat", ALL_DEPARTMENTS_OPTIONS)

            st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
            ringkasan = st.text_area("1. Ringkasan Proyek", value=st.session_state.ai_ringkasan, placeholder="Latar Belakang, Tujuan, dan Ruang Lingkup...", height=100)
            
            st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
            went_well = st.text_area("2. Apa yang Berjalan Baik (What Went Well)", value=st.session_state.ai_went_well, placeholder="Strategi atau hal apa yang menunjang kelancaran proyek ini...", height=100)
            
            st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
            didnt_go_well = st.text_area("3. Tantangan dan Kendala (What Didn't Go Well)", value=st.session_state.ai_didnt_go_well, placeholder="Hambatan atau hal yang bikin jadwal berantakan...", height=100)
            
            # --- TABEL DINAMIS ---
            st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>4. Analisis Akar Masalah</label></div>", unsafe_allow_html=True)
            edited_akar = st.data_editor(st.session_state.ai_akar_masalah, num_rows="dynamic", use_container_width=True, hide_index=True)
            
            st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>5. Metrik Keberhasilan Proyek</label></div>", unsafe_allow_html=True)
            edited_metrik = st.data_editor(st.session_state.ai_metrik, num_rows="dynamic", use_container_width=True, hide_index=True)
            
            st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>6. Rekomendasi dan Rencana Tindak Lanjut</label></div>", unsafe_allow_html=True)
            edited_rekomendasi = st.data_editor(st.session_state.ai_rekomendasi, num_rows="dynamic", use_container_width=True, hide_index=True)
            # ---------------------

            st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
            takeaways = st.text_area("7. Poin Pembelajaran Utama (Key Takeaways)", value=st.session_state.ai_takeaways, placeholder="Tuliskan 3-5 poin paling penting untuk diingat...", height=100)
            
            st.write("")
            submitted = st.form_submit_button("SUBMIT LAPORAN")
            
            if submitted:
                if nama_proyek and ringkasan:
                    auto_gdrive_link = ""
                    if st.session_state.uploaded_file_bytes:
                        if GDRIVE_AVAILABLE and "gcp_service_account" in st.secrets:
                            with st.spinner(f"Menyimpan lampiran fisik ke GDrive Divisi {tipe}..."):
                                target_folder_id = DIVISION_FOLDERS.get(tipe, DIVISION_FOLDERS["Lainnya"])
                                link = upload_to_gdrive(st.session_state.uploaded_file_bytes, st.session_state.uploaded_filename, target_folder_id)
                                if link: auto_gdrive_link = link

                    # Ubah DataFrame tabel ke bentuk JSON String
                    json_akar = json.dumps(edited_akar.to_dict(orient="records"))
                    json_metrik = json.dumps(edited_metrik.to_dict(orient="records"))
                    json_rekomendasi = json.dumps(edited_rekomendasi.to_dict(orient="records"))

                    data = {
                        "nama_proyek": nama_proyek, 
                        "uploader_id": st.session_state.username, 
                        "project_owner": tipe, 
                        "related_department": related_department,
                        "periode_start": periode_start.strftime("%d %B %Y"),
                        "periode_end": periode_end.strftime("%d %B %Y"),
                        "status_proyek": status_proyek,
                        "ringkasan_proyek": ringkasan,
                        "what_went_well": went_well,
                        "what_didnt_go_well": didnt_go_well,
                        "analisis_akar_masalah": json_akar,
                        "metrik_keberhasilan": json_metrik,
                        "rekomendasi_tindak_lanjut": json_rekomendasi,
                        "key_takeaways": takeaways,
                        "gdrive_link": auto_gdrive_link
                    }
                    
                    if repo.insert(data):
                        # Clear AI session states using the helper function
                        st.session_state.ai_ringkasan = ""
                        st.session_state.ai_went_well = ""
                        st.session_state.ai_didnt_go_well = ""
                        st.session_state.ai_takeaways = ""
                        st.session_state.ai_akar_masalah = get_empty_df(COLS_AKAR_MASALAH)
                        st.session_state.ai_metrik = get_empty_df(COLS_METRIK)
                        st.session_state.ai_rekomendasi = get_empty_df(COLS_REKOMENDASI)
                        st.session_state.uploaded_file_bytes = None
                        st.session_state.uploaded_filename = ""
                        
                        st.session_state.save_success = True
                        st.rerun()
                    else:
                        st.error("Waduh, terjadi kendala saat mencatat ke database.")
                else:
                    st.error("Nama Proyek dan Ringkasan wajib diisi ya.")

def view_revision(repo):
    st.markdown("<div class='section-title'>Kamar <span class='holo-text'>Revisi</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    rev_df = df[df['status'] == 'Needs Revision']
    if rev_df.empty:
        render_empty_state("Santai Dulu", "Belum ada dokumen yang dikembalikan dari tim PMO untuk direvisi.")
        return

    for _, row in rev_df.iterrows():
        rid = row['id']
        # Load form values to session state once
        if f'rev_ring_{rid}' not in st.session_state: st.session_state[f'rev_ring_{rid}'] = row['ringkasan_proyek']
        if f'rev_well_{rid}' not in st.session_state: st.session_state[f'rev_well_{rid}'] = row['what_went_well']
        if f'rev_bad_{rid}' not in st.session_state: st.session_state[f'rev_bad_{rid}'] = row['what_didnt_go_well']
        if f'rev_take_{rid}' not in st.session_state: st.session_state[f'rev_take_{rid}'] = row['key_takeaways']
        
        # Parse JSON tables safely and enforce column structure
        if f'rev_akar_{rid}' not in st.session_state:
            try: 
                df_akar = pd.DataFrame(json.loads(row['analisis_akar_masalah']), columns=COLS_AKAR_MASALAH).fillna("").astype(str)
                st.session_state[f'rev_akar_{rid}'] = df_akar if not df_akar.empty else get_empty_df(COLS_AKAR_MASALAH)
            except: 
                st.session_state[f'rev_akar_{rid}'] = get_empty_df(COLS_AKAR_MASALAH)
        
        if f'rev_metrik_{rid}' not in st.session_state:
            try: 
                df_met = pd.DataFrame(json.loads(row['metrik_keberhasilan']), columns=COLS_METRIK).fillna("").astype(str)
                st.session_state[f'rev_metrik_{rid}'] = df_met if not df_met.empty else get_empty_df(COLS_METRIK)
            except: 
                st.session_state[f'rev_metrik_{rid}'] = get_empty_df(COLS_METRIK)
            
        if f'rev_rek_{rid}' not in st.session_state:
            try: 
                df_rek = pd.DataFrame(json.loads(row['rekomendasi_tindak_lanjut']), columns=COLS_REKOMENDASI).fillna("").astype(str)
                st.session_state[f'rev_rek_{rid}'] = df_rek if not df_rek.empty else get_empty_df(COLS_REKOMENDASI)
            except: 
                st.session_state[f'rev_rek_{rid}'] = get_empty_df(COLS_REKOMENDASI)

        with st.container(border=True):
            st.markdown(f"<div class='section-title' style='font-size: 26px; margin-bottom: 24px;'>{row['nama_proyek']}</div>", unsafe_allow_html=True)
            st.markdown(f"""<div style="background: rgba(255, 255, 255, 0.9); border: 1px solid #FFD966; padding: 24px; border-radius: 12px; margin-bottom: 32px; box-shadow: 0 4px 15px rgba(255,217,102,0.2);"><div style="font-family:'Space Grotesk'; font-weight: 700; color: #B38800; margin-bottom: 8px; font-size: 13px; text-transform: uppercase; letter-spacing:1px;">Masukan dari PMO</div><div style="color: var(--text-main); font-size: 15px; font-weight:500; line-height: 1.6;">{row['reviewer_notes']}</div></div>""", unsafe_allow_html=True)
            
            with st.form(f"form_rev_{rid}", border=False):
                nama_proyek = st.text_input("Nama Proyek", value=row['nama_proyek'])

                c1, c2 = st.columns(2)
                with c1:
                    # Trik sederhana agar kolom tanggal tetap terisi secara statis atau direvisi bentuk teks jika mau
                    periode_start = st.text_input("Tanggal Mulai", value=row['periode_start'])
                with c2:
                    periode_end = st.text_input("Tanggal Selesai", value=row['periode_end'])

                c3, c4 = st.columns(2)
                with c3:
                    status_idx = STATUS_PROYEK_OPTIONS.index(row['status_proyek']) if row['status_proyek'] in STATUS_PROYEK_OPTIONS else 0
                    status_proyek = st.selectbox("Status Proyek Saat Ini", STATUS_PROYEK_OPTIONS, index=status_idx)
                with c4:
                    tipe_idx = TIPE_DIVISI_OPTIONS.index(row['project_owner']) if row['project_owner'] in TIPE_DIVISI_OPTIONS else (len(TIPE_DIVISI_OPTIONS)-1)
                    tipe = st.selectbox("Pemilik Proyek / Divisi Utama (Folder GDrive)", TIPE_DIVISI_OPTIONS, index=tipe_idx)
                    
                related_department = st.selectbox(
                    "Tim / Departemen Terkait", 
                    ALL_DEPARTMENTS_OPTIONS, 
                    index=ALL_DEPARTMENTS_OPTIONS.index(row.get('related_department', 'Lainnya')) if row.get('related_department') in ALL_DEPARTMENTS_OPTIONS else 0
                )
                
                st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
                ringkasan = st.text_area("1. Ringkasan Proyek", value=st.session_state[f'rev_ring_{rid}'], height=100)
                went_well = st.text_area("2. Apa yang Berjalan Baik", value=st.session_state[f'rev_well_{rid}'], height=100)
                didnt_go_well = st.text_area("3. Tantangan dan Kendala", value=st.session_state[f'rev_bad_{rid}'], height=100)
                
                st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>4. Analisis Akar Masalah</label></div>", unsafe_allow_html=True)
                edited_akar = st.data_editor(st.session_state[f'rev_akar_{rid}'], num_rows="dynamic", use_container_width=True, hide_index=True)
                
                st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>5. Metrik Keberhasilan Proyek</label></div>", unsafe_allow_html=True)
                edited_metrik = st.data_editor(st.session_state[f'rev_metrik_{rid}'], num_rows="dynamic", use_container_width=True, hide_index=True)
                
                st.markdown("<div style='margin-top: 24px; margin-bottom: 8px;'><label style='font-size:15px; font-weight:600; color:var(--text-main);'>6. Rekomendasi dan Rencana Tindak Lanjut</label></div>", unsafe_allow_html=True)
                edited_rekomendasi = st.data_editor(st.session_state[f'rev_rek_{rid}'], num_rows="dynamic", use_container_width=True, hide_index=True)

                st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
                takeaways = st.text_area("7. Poin Pembelajaran Utama", value=st.session_state[f'rev_take_{rid}'], height=100)
                
                st.write("")
                if st.form_submit_button("SUBMIT REVISI KE PMO"):
                    data = {
                        'nama_proyek': nama_proyek, 
                        'uploader_id': row['uploader_id'], 
                        'project_owner': tipe, 
                        'related_department': related_department,
                        'periode_start': periode_start,
                        'periode_end': periode_end,
                        'status_proyek': status_proyek,
                        'kategori': row['kategori'], 
                        'tipe': tipe, 
                        'ringkasan_proyek': ringkasan,
                        'what_went_well': went_well,
                        'what_didnt_go_well': didnt_go_well,
                        'analisis_akar_masalah': json.dumps(edited_akar.to_dict(orient="records")),
                        'metrik_keberhasilan': json.dumps(edited_metrik.to_dict(orient="records")),
                        'rekomendasi_tindak_lanjut': json.dumps(edited_rekomendasi.to_dict(orient="records")),
                        'key_takeaways': takeaways,
                        'gdrive_link': row['gdrive_link']
                    }
                    if repo.resubmit_record(rid, data):
                        st.rerun()

def view_approval(repo):
    st.markdown("<div class='section-title'>Dapur <span class='holo-text'>PMO</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    pending_df = df[df['status'] == 'Pending Review']
    
    if pending_df.empty:
        render_empty_state("Tidak Ada Antrean", "Tugasmu beres! Semua dokumen telah disahkan.")
        return
        
    for _, row in pending_df.iterrows():
        with st.expander(f"Cek Laporan Baru  —  {row['nama_proyek']}"):
            render_knowledge_card_content(row)
            
            st.markdown("<div class='holo-wave-divider'></div>", unsafe_allow_html=True)
            notes = st.text_area("Berikan Catatan/Koreksi di Sini (Penting kalau mau menolak atau minta revisi)", key=f"note_{row['id']}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Hapus Entri", key=f"del_{row['id']}"): repo.delete_record(row['id']); st.rerun()
            with c2:
                if st.button("Tolak Laporan", key=f"rej_{row['id']}"): repo.update_status(row['id'], "Rejected", notes); st.rerun()
            with c3:
                if st.button("Minta Revisi", key=f"rev_{row['id']}"): repo.update_status(row['id'], "Needs Revision", notes); st.rerun()
            with c4:
                if st.button("Sahkan Laporan", key=f"ver_{row['id']}"): repo.update_status(row['id'], "Verified", notes); st.rerun()

def view_export(repo):
    st.markdown("<div class='section-title'>Unduh <span class='holo-text'>Database</span></div>", unsafe_allow_html=True)
    df = repo.fetch_all()
    if df.empty: return render_empty_state()
    with st.container(border=True):
        st.markdown("<div class='section-title' style='font-size: 24px; margin-bottom: 40px;'>Ekspor Data Master</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(label="Unduh Tabular (.CSV)", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"PTBA_Lessons_Learned_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        with c2:
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer: df.to_excel(writer, index=False, sheet_name="Register")
                st.download_button(label="Unduh Spreadsheet (.XLSX)", data=output.getvalue(), file_name=f"PTBA_Lessons_Learned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: st.markdown("<div style='text-align: center; font-size: 14px; color:var(--text-muted); margin-top: 16px; font-weight:600;'>Oh ya, sistem butuh modul 'openpyxl' biar fitur Excel-nya nyala.</div>", unsafe_allow_html=True)

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
        
        navigation = st.radio("Menu Navigasi", allowed_pages, label_visibility="collapsed")
        
        st.write("")
        st.write("")
        st.write("")
        st.markdown(f"<div style='font-family:\"Manrope\", sans-serif; font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 24px; padding: 12px; background: rgba(255,255,255,0.9); border-radius:12px; border: 1px solid rgba(142, 45, 226, 0.2);'>Login Sebagai:<br><span style='font-family:\"Space Grotesk\"; font-size:16px; font-weight:700; color:#4A00E0;'>{st.session_state.username}</span><br>Role: {role}</div>", unsafe_allow_html=True)
        if st.button("Keluar Akun"):
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

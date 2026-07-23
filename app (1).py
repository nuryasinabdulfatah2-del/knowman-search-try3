# -*- coding: utf-8 -*-
"""
================================================================================
ENTERPRISE KNOWLEDGE SEARCH & STRATEGIC LESSONS LEARNED PLATFORM
================================================================================
Production-Grade Prototype
Dibangun dengan Streamlit + SQLite (Persistent Storage)

Fitur Utama:
1. Penyimpanan permanen menggunakan SQLite (bukan session_state)
2. Automated Document Parsing (PDF/DOCX/TXT) + AI Smart Auto-Fill
3. Governance Workflow (Draft -> Verified/Rejected) + Approval Center
4. Pencarian & Filtering tingkat lanjut (multi-kategori, highlight)
5. UI/UX Enterprise modern (Glassmorphism, KPI Cards, Dashboard Analitik)
6. Export data ke CSV/Excel

Author: Senior Full-Stack Python & AI Engineer
================================================================================
"""

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime, date
import io
import os
import re
import html as html_lib
import traceback

# ------------------------------------------------------------------------------
# OPTIONAL / GRACEFUL IMPORTS UNTUK PARSING DOKUMEN
# Aplikasi tidak boleh crash walau salah satu library parsing tidak tersedia.
# ------------------------------------------------------------------------------
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
    import docx  # python-docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


# ==============================================================================
# 1. KONFIGURASI GLOBAL & KONSTANTA
# ==============================================================================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_platform.db")

STATUS_DRAFT = "🟡 Draft / Pending Review"
STATUS_VERIFIED = "🟢 Verified"
STATUS_REJECTED = "🔴 Rejected/Archived"
ALL_STATUSES = [STATUS_DRAFT, STATUS_VERIFIED, STATUS_REJECTED]

# ------------------------------------------------------------------------------
# TEMA PLOTLY GLOBAL - agar seluruh grafik konsisten dengan bahasa desain Apple
# (font sistem, latar transparan agar menyatu dengan kartu glassmorphism)
# ------------------------------------------------------------------------------
_APPLE_FONT_STACK = ("-apple-system, BlinkMacSystemFont, 'SF Pro Display', "
                     "'SF Pro Text', 'Helvetica Neue', Arial, sans-serif")
try:
    _apple_template = pio.templates["plotly_white"]
    _apple_template.layout.font = dict(family=_APPLE_FONT_STACK, color="#1D1D1F", size=13)
    _apple_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    _apple_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    pio.templates["apple_light"] = _apple_template
    pio.templates.default = "apple_light"
except Exception:
    pass  # Jika gagal, Plotly tetap memakai template bawaan tanpa membuat aplikasi crash

IMPACT_LEVELS = ["Tinggi", "Sedang", "Rendah"]

CATEGORY_OPTIONS = [
    "Perencanaan Proyek", "Manajemen Risiko", "Pengadaan & Kontrak",
    "Kualitas & Kepatuhan (QA/QC)", "Sumber Daya Manusia", "Teknologi & Sistem",
    "Keuangan & Anggaran", "Operasional", "Stakeholder & Komunikasi", "Lainnya"
]

# Kata kunci untuk mesin "AI Smart Auto-Fill" (ekstraksi berbasis kata kunci)
KEYWORDS_SUMMARY = [
    "isu", "masalah", "kendala", "permasalahan", "issue", "problem",
    "hambatan", "tantangan", "ditemukan bahwa", "terjadi"
]
KEYWORDS_ROOT_CAUSE = [
    "akar masalah", "akar penyebab", "disebabkan", "root cause", "penyebab",
    "faktor penyebab", "diakibatkan", "dikarenakan", "sumber masalah", "berawal dari"
]
KEYWORDS_RECOMMENDATION = [
    "rekomendasi", "solusi", "usulan", "tindak lanjut", "saran", "recommendation",
    "action plan", "mitigasi", "langkah perbaikan", "perlu dilakukan", "disarankan"
]

# ------------------------------------------------------------------------------
# PALET WARNA - DESIGN SYSTEM ala Apple / macOS-iOS
# ------------------------------------------------------------------------------
# Latar neutral gray khas macOS (bukan putih polos, bukan hitam pekat)
COLOR_BG = "#F5F5F7"

# Teks: hitam-lembut (Apple label color) & abu sekunder
COLOR_TEXT_PRIMARY = "#1D1D1F"
COLOR_TEXT_SECONDARY = "#6E6E73"

# Satu-satunya warna aksen dominan untuk aksi utama: Apple Blue
COLOR_ACCENT = "#007AFF"
COLOR_ACCENT_DARK = "#0062CC"

# Warna status berkejenuhan rendah (soft / desaturated), bukan warna neon
COLOR_SOFT_GREEN = "#8FCB9B"        # Verified
COLOR_SOFT_GREEN_DARK = "#4E9B62"   # aksen teks/garis untuk elemen "hijau" yang perlu kontras lebih
COLOR_SOFT_ORANGE = "#F0B67F"       # Draft / Pending
COLOR_SOFT_RED = "#E3A0A0"          # Rejected / Dampak Tinggi
COLOR_SOFT_RED_DARK = "#C97A7A"

# Border tipis & halus khas kartu glass ala macOS
COLOR_GLASS_BORDER = "rgba(0,0,0,0.06)"

# Warna highlight pencarian (soft yellow, senada dengan nuansa low-saturation)
COLOR_HIGHLIGHT = "#FFE39B"

# ---- Alias kompatibilitas mundur (dipetakan ke token warna baru di atas) ----
# Sengaja dipertahankan agar seluruh referensi lama pada chart Plotly & CSS
# tetap konsisten mengikuti palet baru tanpa perlu diganti satu per satu.
COLOR_NAVY = COLOR_TEXT_PRIMARY
COLOR_NAVY_LIGHT = COLOR_TEXT_PRIMARY
COLOR_SLATE = COLOR_TEXT_SECONDARY
COLOR_SLATE_LIGHT = COLOR_TEXT_SECONDARY
COLOR_EMERALD = COLOR_SOFT_GREEN
COLOR_EMERALD_DARK = COLOR_SOFT_GREEN_DARK
COLOR_AMBER = COLOR_SOFT_ORANGE
COLOR_RED = COLOR_SOFT_RED


# ==============================================================================
# 2. LAPISAN DATABASE (SQLite) - PERSISTENCE STORAGE
# ==============================================================================

def get_connection():
    """Membuka koneksi ke database SQLite. check_same_thread=False agar aman
    dipakai lintas thread yang dibuat oleh Streamlit."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inisialisasi database & tabel jika belum ada. Dipanggil otomatis
    setiap kali aplikasi start, aman dipanggil berulang kali (idempotent)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                project_name TEXT,
                category TEXT,
                impact_level TEXT,
                status TEXT DEFAULT '🟡 Draft / Pending Review',
                summary TEXT,
                root_cause TEXT,
                recommendation TEXT,
                uploader TEXT,
                upload_date TEXT,
                project_year INTEGER,
                document_version TEXT,
                file_name TEXT,
                extracted_text TEXT,
                reviewer_notes TEXT,
                reviewed_by TEXT,
                reviewed_date TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"❌ Gagal inisialisasi database: {e}")


def insert_issue(data: dict) -> bool:
    """Menyimpan satu entri isu baru ke database. Mengembalikan True/False
    sebagai indikator sukses, dengan error handling penuh."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO issues (
                title, project_name, category, impact_level, status,
                summary, root_cause, recommendation, uploader, upload_date,
                project_year, document_version, file_name, extracted_text,
                reviewer_notes, reviewed_by, reviewed_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("title", "").strip(),
            data.get("project_name", "").strip(),
            data.get("category", "Lainnya"),
            data.get("impact_level", "Sedang"),
            data.get("status", STATUS_DRAFT),
            data.get("summary", "").strip(),
            data.get("root_cause", "").strip(),
            data.get("recommendation", "").strip(),
            data.get("uploader", "Anonim").strip(),
            data.get("upload_date", datetime.now().strftime("%Y-%m-%d %H:%M")),
            data.get("project_year", datetime.now().year),
            data.get("document_version", "v1.0"),
            data.get("file_name", ""),
            data.get("extracted_text", ""),
            data.get("reviewer_notes", ""),
            data.get("reviewed_by", ""),
            data.get("reviewed_date", ""),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Gagal menyimpan data ke database: {e}")
        return False


def update_issue_status(issue_id: int, new_status: str, reviewer_notes: str = "", reviewed_by: str = "PMO/Manager") -> bool:
    """Mengubah status governance sebuah entri (Verified/Rejected) beserta
    metadata reviewer."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE issues
            SET status = ?, reviewer_notes = ?, reviewed_by = ?, reviewed_date = ?
            WHERE id = ?
        """, (new_status, reviewer_notes, reviewed_by,
              datetime.now().strftime("%Y-%m-%d %H:%M"), issue_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Gagal memperbarui status: {e}")
        return False


def delete_issue(issue_id: int) -> bool:
    """Menghapus entri isu secara permanen dari database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Gagal menghapus data: {e}")
        return False


def fetch_all_issues() -> pd.DataFrame:
    """Mengambil seluruh data isu sebagai DataFrame. Selalu mengembalikan
    DataFrame (kosong jika tidak ada data / terjadi error), tidak pernah None,
    agar kode pemanggil tidak crash."""
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM issues ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Gagal mengambil data dari database: {e}")
        return pd.DataFrame(columns=[
            "id", "title", "project_name", "category", "impact_level", "status",
            "summary", "root_cause", "recommendation", "uploader", "upload_date",
            "project_year", "document_version", "file_name", "extracted_text",
            "reviewer_notes", "reviewed_by", "reviewed_date"
        ])


# ==============================================================================
# 3. MODUL PARSING DOKUMEN (PDF / DOCX / TXT)
# ==============================================================================

def extract_text_from_pdf(uploaded_file) -> str:
    """Mengekstrak teks dari file PDF menggunakan pdfplumber (utama) dengan
    fallback ke pypdf. Mengembalikan string kosong jika file corrupt/gagal,
    tidak pernah melempar exception ke pemanggil."""
    raw_bytes = uploaded_file.read()
    text_parts = []

    # Coba pdfplumber terlebih dahulu (lebih akurat untuk layout kompleks)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                return "\n".join(text_parts)
        except Exception:
            text_parts = []  # reset, coba fallback di bawah

    # Fallback ke pypdf jika pdfplumber gagal / tidak tersedia
    if PYPDF_AVAILABLE:
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts)
        except Exception as e:
            st.warning(f"⚠️ File PDF tampak rusak atau terenkripsi, tidak bisa diekstrak sepenuhnya ({e}).")
            return ""

    st.warning("⚠️ Library pembaca PDF tidak tersedia di lingkungan ini.")
    return ""


def extract_text_from_docx(uploaded_file) -> str:
    """Mengekstrak teks dari file DOCX (paragraf + tabel) dengan penanganan
    error penuh."""
    if not DOCX_AVAILABLE:
        st.warning("⚠️ Library python-docx tidak tersedia di lingkungan ini.")
        return ""
    try:
        raw_bytes = uploaded_file.read()
        document = docx.Document(io.BytesIO(raw_bytes))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        # Ambil juga isi tabel jika ada
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        return "\n".join(parts)
    except Exception as e:
        st.warning(f"⚠️ File DOCX tampak rusak atau tidak valid ({e}).")
        return ""


def extract_text_from_txt(uploaded_file) -> str:
    """Membaca file TXT dengan penanganan encoding yang aman."""
    try:
        raw_bytes = uploaded_file.read()
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="ignore")
    except Exception as e:
        st.warning(f"⚠️ Gagal membaca file TXT ({e}).")
        return ""


def parse_uploaded_document(uploaded_file) -> str:
    """Router utama: mendeteksi ekstensi file dan memanggil parser yang sesuai.
    Selalu mengembalikan string (bisa kosong), tidak pernah crash."""
    if uploaded_file is None:
        return ""
    try:
        filename = uploaded_file.name.lower()
        if filename.endswith(".pdf"):
            return extract_text_from_pdf(uploaded_file)
        elif filename.endswith(".docx"):
            return extract_text_from_docx(uploaded_file)
        elif filename.endswith(".txt"):
            return extract_text_from_txt(uploaded_file)
        else:
            st.warning("⚠️ Format file tidak didukung. Gunakan PDF, DOCX, atau TXT.")
            return ""
    except Exception as e:
        st.error(f"❌ Terjadi kesalahan tak terduga saat memproses dokumen: {e}")
        return ""


# ==============================================================================
# 4. MESIN "AI SMART AUTO-FILL" - EKSTRAKSI KALIMAT KUNCI
# ==============================================================================

def split_into_sentences(text: str) -> list:
    """Memecah teks panjang menjadi daftar kalimat menggunakan heuristik
    tanda baca akhir kalimat."""
    if not text or not text.strip():
        return []
    # Bersihkan whitespace berlebih dan pecah per kalimat
    cleaned = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def extract_relevant_sentences(sentences: list, keywords: list, max_sentences: int = 3) -> str:
    """Mengambil kalimat-kalimat yang mengandung salah satu keyword target,
    lalu menggabungkannya menjadi satu ringkasan singkat."""
    matched = []
    for sentence in sentences:
        lower_sentence = sentence.lower()
        if any(kw in lower_sentence for kw in keywords):
            matched.append(sentence)
        if len(matched) >= max_sentences:
            break
    return " ".join(matched)


def smart_auto_fill(extracted_text: str) -> dict:
    """Fungsi inti 'AI Smart Auto-Fill'. Menganalisis teks dokumen yang
    diunggah dan menyarankan isi Ringkasan Isu, Akar Masalah, dan
    Rekomendasi Solusi secara otomatis berdasarkan pola kata kunci.

    Catatan: ini adalah simulasi ekstraksi berbasis keyword/heuristik teks
    (bukan pemanggilan LLM eksternal), dirancang agar berjalan offline &
    deterministik untuk keperluan prototipe.
    """
    result = {"summary": "", "root_cause": "", "recommendation": ""}
    if not extracted_text or not extracted_text.strip():
        return result

    try:
        sentences = split_into_sentences(extracted_text)
        if not sentences:
            return result

        summary = extract_relevant_sentences(sentences, KEYWORDS_SUMMARY, max_sentences=3)
        root_cause = extract_relevant_sentences(sentences, KEYWORDS_ROOT_CAUSE, max_sentences=3)
        recommendation = extract_relevant_sentences(sentences, KEYWORDS_RECOMMENDATION, max_sentences=3)

        # Fallback cerdas: jika tidak ada kalimat yang cocok dengan keyword,
        # gunakan kalimat awal dokumen sebagai draf ringkasan awal.
        if not summary:
            summary = " ".join(sentences[:2])
        if not root_cause:
            root_cause = "Tidak ditemukan pola 'akar masalah' secara eksplisit. Mohon lengkapi manual."
        if not recommendation:
            recommendation = "Tidak ditemukan pola 'rekomendasi' secara eksplisit. Mohon lengkapi manual."

        result["summary"] = summary
        result["root_cause"] = root_cause
        result["recommendation"] = recommendation
        return result
    except Exception as e:
        st.warning(f"⚠️ Smart Auto-Fill tidak dapat memproses teks sepenuhnya ({e}).")
        return result


# ==============================================================================
# 5. UTILITAS UI: HIGHLIGHTING, EXPORT, STYLING
# ==============================================================================

def highlight_keyword(text: str, keyword: str) -> str:
    """Membungkus kemunculan keyword dalam teks dengan tag <mark> HTML untuk
    fitur real-time highlighting pada hasil pencarian. Teks di-escape dahulu
    untuk mencegah HTML injection."""
    if not text:
        return ""
    safe_text = html_lib.escape(str(text))
    if not keyword or not keyword.strip():
        return safe_text
    try:
        safe_keyword = html_lib.escape(keyword.strip())
        pattern = re.compile(re.escape(safe_keyword), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f'<mark style="background-color:{COLOR_HIGHLIGHT};color:{COLOR_TEXT_PRIMARY};padding:0 3px;border-radius:3px;">{m.group(0)}</mark>',
            safe_text
        )
        return highlighted
    except Exception:
        return safe_text


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Mengonversi DataFrame menjadi file Excel (bytes) siap diunduh."""
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Lessons_Learned")
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ Gagal membuat file Excel: {e}")
        return b""


def load_custom_css():
    """Menyuntikkan Custom CSS bergaya Apple / macOS-iOS Human Interface:

    - Tipografi sistem Apple (-apple-system, SF Pro) dengan letter-spacing
      dirapatkan pada judul untuk kesan presisi tinggi.
    - Latar neutral gray #F5F5F7 (bukan putih polos / hitam pekat).
    - Kartu glassmorphism: backdrop-filter blur(20px), latar putih transparan
      rgba(255,255,255,0.75), dengan border tipis & halus.
    - Satu warna aksen dominan (Apple Blue #007AFF) untuk aksi utama, serta
      warna status berkejenuhan rendah (soft orange / soft green).
    """
    st.markdown(f"""
    <style>
    /* ---------- Tipografi sistem Apple ---------- */
    html, body, [class*="css"], .stApp, button, input, textarea, select {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                     "SF Pro Text", "Helvetica Neue", "Segoe UI", Arial, sans-serif !important;
        color: {COLOR_TEXT_PRIMARY};
    }}
    h1, h2, h3, h4, .km-header h1, .kpi-value, .issue-title {{
        letter-spacing: -0.022em;
    }}
    h1, h2, h3 {{
        font-weight: 700;
        color: {COLOR_TEXT_PRIMARY};
    }}

    /* ---------- Latar Aplikasi: Neutral Gray khas macOS ---------- */
    .stApp {{
        background-color: {COLOR_BG};
    }}
    [data-testid="stHeader"] {{
        background-color: rgba(245,245,247,0.0);
    }}
    [data-testid="stAppViewContainer"] {{
        background-color: {COLOR_BG};
    }}

    /* ---------- Header Utama (Glass Panel, bukan gradient gelap) ---------- */
    .km-header {{
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        padding: 26px 32px;
        border-radius: 20px;
        margin-bottom: 22px;
        border: 1px solid {COLOR_GLASS_BORDER};
        box-shadow: 0 8px 30px rgba(0,0,0,0.06);
    }}
    .km-header h1 {{
        color: {COLOR_TEXT_PRIMARY};
        font-weight: 700;
        font-size: 27px;
        margin: 0;
        letter-spacing: -0.025em;
    }}
    .km-header p {{
        color: {COLOR_TEXT_SECONDARY};
        margin: 6px 0 0 0;
        font-size: 14px;
        letter-spacing: -0.006em;
    }}

    /* ---------- KPI Card (Glassmorphism, blur 20px) ---------- */
    .kpi-card {{
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-radius: 18px;
        padding: 18px 20px;
        border: 1px solid {COLOR_GLASS_BORDER};
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
        text-align: left;
        height: 118px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(0,0,0,0.08);
    }}
    .kpi-label {{
        color: {COLOR_TEXT_SECONDARY};
        font-size: 12.5px;
        font-weight: 590;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        margin-bottom: 6px;
    }}
    .kpi-value {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.025em;
    }}
    .kpi-sub {{
        color: {COLOR_ACCENT};
        font-size: 12.5px;
        font-weight: 590;
        margin-top: 2px;
    }}

    /* ---------- Issue / Search Result Card (Glassmorphism) ---------- */
    .issue-card {{
        background: rgba(255,255,255,0.75);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 14px;
        border: 1px solid {COLOR_GLASS_BORDER};
        border-left: 4px solid {COLOR_TEXT_SECONDARY};
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
    }}
    .issue-card.status-verified {{ border-left-color: {COLOR_SOFT_GREEN}; }}
    .issue-card.status-draft {{ border-left-color: {COLOR_SOFT_ORANGE}; }}
    .issue-card.status-rejected {{ border-left-color: {COLOR_SOFT_RED}; }}

    .issue-title {{
        font-size: 17px;
        font-weight: 650;
        color: {COLOR_TEXT_PRIMARY};
        margin-bottom: 4px;
        letter-spacing: -0.02em;
    }}
    .issue-meta {{
        font-size: 12.5px;
        color: {COLOR_TEXT_SECONDARY};
        margin-bottom: 10px;
    }}
    .issue-badge {{
        display: inline-block;
        padding: 3px 11px;
        border-radius: 20px;
        font-size: 11.5px;
        font-weight: 650;
        margin-right: 6px;
        background: rgba(110,110,115,0.14);
        color: {COLOR_TEXT_SECONDARY};
    }}
    .issue-badge.impact-tinggi {{ background: rgba(227,160,160,0.35); color: {COLOR_SOFT_RED_DARK}; }}
    .issue-badge.impact-sedang {{ background: rgba(240,182,127,0.35); color: #B9701F; }}
    .issue-badge.impact-rendah {{ background: rgba(143,203,155,0.35); color: {COLOR_SOFT_GREEN_DARK}; }}

    .issue-section-label {{
        font-weight: 650;
        color: {COLOR_TEXT_SECONDARY};
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        margin-top: 8px;
    }}
    .issue-section-text {{
        font-size: 14px;
        color: {COLOR_TEXT_PRIMARY};
        line-height: 1.5;
    }}

    /* ---------- Sidebar: panel kaca terang, senada dengan latar ---------- */
    section[data-testid="stSidebar"] {{
        background: rgba(245, 245, 247, 0.85);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-right: 1px solid {COLOR_GLASS_BORDER};
    }}
    section[data-testid="stSidebar"] * {{
        color: {COLOR_TEXT_PRIMARY} !important;
    }}
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {{
        color: {COLOR_TEXT_SECONDARY} !important;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        background: {COLOR_ACCENT};
        color: white !important;
        border: none;
        font-weight: 600;
        border-radius: 10px;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background: {COLOR_ACCENT_DARK};
    }}

    /* ---------- Buttons: satu aksen dominan (Apple Blue) ---------- */
    .stButton button {{
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid {COLOR_GLASS_BORDER};
        background: rgba(255,255,255,0.7);
        color: {COLOR_ACCENT};
        transition: background 0.15s ease;
    }}
    .stButton button:hover {{
        background: rgba(0,122,255,0.10);
        border-color: {COLOR_ACCENT};
        color: {COLOR_ACCENT_DARK};
    }}
    div[data-testid="stFormSubmitButton"] button {{
        background: {COLOR_ACCENT};
        color: white;
        border: none;
    }}
    div[data-testid="stFormSubmitButton"] button:hover {{
        background: {COLOR_ACCENT_DARK};
        color: white;
    }}

    /* ---------- Input fields: rapi & presisi ---------- */
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    .stDateInput input, div[data-baseweb="select"] > div {{
        border-radius: 10px !important;
        border: 1px solid {COLOR_GLASS_BORDER} !important;
        background: rgba(255,255,255,0.7) !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {COLOR_ACCENT} !important;
        box-shadow: 0 0 0 3px rgba(0,122,255,0.15) !important;
    }}

    /* ---------- Tabs ---------- */
    button[data-baseweb="tab"] {{
        font-weight: 590;
        font-size: 14.5px;
        color: {COLOR_TEXT_SECONDARY};
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {COLOR_ACCENT};
    }}
    div[data-baseweb="tab-highlight"] {{
        background-color: {COLOR_ACCENT} !important;
    }}

    /* ---------- Expander (Approval Center) ---------- */
    .streamlit-expanderHeader {{
        background: rgba(255,255,255,0.6);
        border-radius: 12px;
        font-weight: 590;
    }}
    div[data-testid="stExpander"] {{
        background: rgba(255,255,255,0.55);
        backdrop-filter: blur(20px);
        border: 1px solid {COLOR_GLASS_BORDER};
        border-radius: 14px;
    }}

    /* ---------- Metric mark / highlight pencarian ---------- */
    mark {{
        background-color: {COLOR_HIGHLIGHT} !important;
        color: {COLOR_TEXT_PRIMARY} !important;
        padding: 0 3px;
        border-radius: 3px;
    }}

    hr {{
        border-color: {COLOR_GLASS_BORDER};
    }}
    </style>
    """, unsafe_allow_html=True)


def status_css_class(status: str) -> str:
    """Mengembalikan class CSS sesuai status governance untuk pewarnaan kartu."""
    if status == STATUS_VERIFIED:
        return "status-verified"
    elif status == STATUS_DRAFT:
        return "status-draft"
    elif status == STATUS_REJECTED:
        return "status-rejected"
    return ""


def impact_css_class(impact: str) -> str:
    """Mengembalikan class CSS badge sesuai level dampak."""
    mapping = {"Tinggi": "impact-tinggi", "Sedang": "impact-sedang", "Rendah": "impact-rendah"}
    return mapping.get(impact, "")


# ==============================================================================
# 6. KOMPONEN UI: KPI CARDS
# ==============================================================================

def render_kpi_cards(df: pd.DataFrame):
    """Merender 4 kartu KPI utama di bagian atas dashboard."""
    total_issues = len(df)
    total_verified = len(df[df["status"] == STATUS_VERIFIED]) if total_issues > 0 else 0
    pct_verified = (total_verified / total_issues * 100) if total_issues > 0 else 0.0
    total_high_impact = len(df[df["impact_level"] == "Tinggi"]) if total_issues > 0 else 0
    total_documents = len(df[df["file_name"].astype(str).str.strip() != ""]) if total_issues > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    kpi_data = [
        (col1, "Total Isu Tercatat", f"{total_issues:,}", "📋 Seluruh entri Lessons Learned"),
        (col2, "% Isu Terverifikasi", f"{pct_verified:.1f}%", f"🟢 {total_verified} dari {total_issues} entri"),
        (col3, "Isu Dampak Tinggi", f"{total_high_impact:,}", "🔴 Memerlukan perhatian prioritas"),
        (col4, "Total Dokumen Terunggah", f"{total_documents:,}", "📁 File pendukung tersimpan"),
    ]
    for col, label, value, sub in kpi_data:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)


# ==============================================================================
# 7. HALAMAN: DASHBOARD UTAMA
# ==============================================================================

def page_dashboard(df: pd.DataFrame):
    st.markdown("### 📊 Ringkasan Eksekutif")
    render_kpi_cards(df)
    st.markdown("<br>", unsafe_allow_html=True)

    if df.empty:
        st.info("Belum ada data isu. Silakan unggah isu baru melalui menu **📤 Unggah Isu Baru**.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Distribusi Status Governance")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Jumlah"]
        color_map = {STATUS_VERIFIED: COLOR_EMERALD, STATUS_DRAFT: COLOR_AMBER, STATUS_REJECTED: COLOR_RED}
        fig = px.pie(status_counts, names="Status", values="Jumlah", hole=0.55,
                     color="Status", color_discrete_map=color_map)
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Isu Berdasarkan Level Dampak")
        impact_counts = df["impact_level"].value_counts().reindex(IMPACT_LEVELS).fillna(0).reset_index()
        impact_counts.columns = ["Dampak", "Jumlah"]
        color_map_impact = {"Tinggi": COLOR_RED, "Sedang": COLOR_AMBER, "Rendah": COLOR_EMERALD_DARK}
        fig2 = px.bar(impact_counts, x="Dampak", y="Jumlah", color="Dampak",
                      color_discrete_map=color_map_impact, text="Jumlah")
        fig2.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=320,
                           xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### 🕒 Isu Terbaru Diunggah")
    recent = df.sort_values("id", ascending=False).head(5)
    for _, row in recent.iterrows():
        render_issue_card(row, search_keyword="")


# ==============================================================================
# 8. KOMPONEN UI: KARTU ISU (untuk hasil pencarian & dashboard)
# ==============================================================================

def render_issue_card(row, search_keyword: str = ""):
    """Merender satu kartu isu lengkap dengan highlight kata kunci pencarian."""
    css_status = status_css_class(row["status"])
    css_impact = impact_css_class(row["impact_level"])

    title_html = highlight_keyword(row["title"], search_keyword)
    summary_html = highlight_keyword(row["summary"], search_keyword)
    root_cause_html = highlight_keyword(row["root_cause"], search_keyword)
    recommendation_html = highlight_keyword(row["recommendation"], search_keyword)

    project_name = row["project_name"] if pd.notna(row["project_name"]) and row["project_name"] else "-"
    file_info = f"📎 {row['file_name']}" if pd.notna(row["file_name"]) and row["file_name"] else "📎 Tidak ada dokumen"

    st.markdown(f"""
    <div class="issue-card {css_status}">
        <div class="issue-title">{title_html}</div>
        <div class="issue-meta">
            🗂️ {html_lib.escape(str(row['category']))} &nbsp;|&nbsp;
            📁 Proyek: {html_lib.escape(str(project_name))} &nbsp;|&nbsp;
            👤 {html_lib.escape(str(row['uploader']))} &nbsp;|&nbsp;
            🗓️ {html_lib.escape(str(row['upload_date']))} &nbsp;|&nbsp;
            🔢 Versi {html_lib.escape(str(row['document_version']))} &nbsp;|&nbsp;
            {file_info}
        </div>
        <span class="issue-badge {css_impact}">Dampak: {html_lib.escape(str(row['impact_level']))}</span>
        <span class="issue-badge">{html_lib.escape(str(row['status']))}</span>
        <div class="issue-section-label">📝 Ringkasan Isu</div>
        <div class="issue-section-text">{summary_html if summary_html else '<i>Belum diisi</i>'}</div>
        <div class="issue-section-label">🔎 Akar Masalah (Know-Why)</div>
        <div class="issue-section-text">{root_cause_html if root_cause_html else '<i>Belum diisi</i>'}</div>
        <div class="issue-section-label">✅ Rekomendasi / Tindak Lanjut</div>
        <div class="issue-section-text">{recommendation_html if recommendation_html else '<i>Belum diisi</i>'}</div>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 9. HALAMAN: PENCARIAN & FILTER TINGKAT LANJUT
# ==============================================================================

def page_search(df: pd.DataFrame, filters: dict):
    st.markdown("### 🔍 Pencarian & Telusuri Isu Strategis")

    search_query = st.text_input(
        "Cari berdasarkan judul, ringkasan, akar masalah, atau rekomendasi...",
        placeholder="Contoh: keterlambatan pengadaan, risiko anggaran, dsb.",
        key="main_search_box"
    )

    filtered_df = apply_filters(df, filters)

    if search_query and search_query.strip():
        query_lower = search_query.strip().lower()
        mask = (
            filtered_df["title"].astype(str).str.lower().str.contains(re.escape(query_lower), na=False) |
            filtered_df["summary"].astype(str).str.lower().str.contains(re.escape(query_lower), na=False) |
            filtered_df["root_cause"].astype(str).str.lower().str.contains(re.escape(query_lower), na=False) |
            filtered_df["recommendation"].astype(str).str.lower().str.contains(re.escape(query_lower), na=False) |
            filtered_df["project_name"].astype(str).str.lower().str.contains(re.escape(query_lower), na=False)
        )
        filtered_df = filtered_df[mask]

    st.markdown(f"**{len(filtered_df)}** isu ditemukan dari total **{len(df)}** entri.")
    st.markdown("---")

    if filtered_df.empty:
        st.warning("Tidak ada isu yang cocok dengan pencarian/filter Anda. Coba ubah kata kunci atau filter.")
        return

    sort_option = st.selectbox(
        "Urutkan berdasarkan", ["Terbaru", "Terlama", "Dampak Tertinggi", "Judul (A-Z)"], index=0
    )
    if sort_option == "Terbaru":
        filtered_df = filtered_df.sort_values("id", ascending=False)
    elif sort_option == "Terlama":
        filtered_df = filtered_df.sort_values("id", ascending=True)
    elif sort_option == "Dampak Tertinggi":
        impact_order = {"Tinggi": 0, "Sedang": 1, "Rendah": 2}
        filtered_df = filtered_df.assign(_ord=filtered_df["impact_level"].map(impact_order)).sort_values("_ord")
    elif sort_option == "Judul (A-Z)":
        filtered_df = filtered_df.sort_values("title", ascending=True)

    for _, row in filtered_df.iterrows():
        render_issue_card(row, search_keyword=search_query)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Menerapkan seluruh filter sidebar (kategori, dampak, status, tahun)
    ke DataFrame secara aman."""
    if df.empty:
        return df
    result = df.copy()
    try:
        if filters.get("categories"):
            result = result[result["category"].isin(filters["categories"])]
        if filters.get("impacts"):
            result = result[result["impact_level"].isin(filters["impacts"])]
        if filters.get("statuses"):
            result = result[result["status"].isin(filters["statuses"])]
        if filters.get("year_range"):
            y_min, y_max = filters["year_range"]
            result = result[
                (result["project_year"].fillna(0).astype(int) >= y_min) &
                (result["project_year"].fillna(0).astype(int) <= y_max)
            ]
        return result
    except Exception as e:
        st.warning(f"⚠️ Gagal menerapkan sebagian filter: {e}")
        return df


# ==============================================================================
# 10. HALAMAN: UNGGAH ISU BARU (dengan AI Smart Auto-Fill)
# ==============================================================================

def page_upload():
    st.markdown("### 📤 Unggah Isu Strategis Baru")
    st.caption("Unggah dokumen pendukung (opsional) untuk mengaktifkan **AI Smart Auto-Fill**, "
               "atau isi form secara manual.")

    # ---- Tahap 1: Upload Dokumen & Ekstraksi ----
    st.markdown("#### 1️⃣ Unggah Dokumen Pendukung (Opsional)")
    uploaded_file = st.file_uploader(
        "Format didukung: PDF, DOCX, TXT",
        type=["pdf", "docx", "txt"],
        key="doc_uploader"
    )

    if "autofill_result" not in st.session_state:
        st.session_state.autofill_result = {"summary": "", "root_cause": "", "recommendation": ""}
    if "extracted_text_cache" not in st.session_state:
        st.session_state.extracted_text_cache = ""

    if uploaded_file is not None:
        if st.button("🤖 Jalankan AI Smart Auto-Fill dari Dokumen Ini", use_container_width=True):
            with st.spinner("Membaca dan menganalisis dokumen..."):
                extracted_text = parse_uploaded_document(uploaded_file)
                st.session_state.extracted_text_cache = extracted_text
                if extracted_text.strip():
                    st.session_state.autofill_result = smart_auto_fill(extracted_text)
                    st.success("✅ Berhasil mengekstrak & menyarankan isi form di bawah. Silakan tinjau dan sunting.")
                else:
                    st.warning("⚠️ Tidak ada teks yang berhasil diekstrak dari dokumen ini. Silakan isi form secara manual.")

    st.markdown("---")
    st.markdown("#### 2️⃣ Lengkapi Detail Isu")

    with st.form("upload_issue_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Judul Isu *", placeholder="Contoh: Keterlambatan Pengadaan Material Utama")
            project_name = st.text_input("Nama Proyek", placeholder="Contoh: Proyek Pembangunan Gedung A")
            category = st.selectbox("Kategori Isu *", CATEGORY_OPTIONS)
            impact_level = st.selectbox("Level Dampak *", IMPACT_LEVELS, index=1)
        with col2:
            uploader = st.text_input("Nama Pengunggah / Pemilik Isu *", placeholder="Contoh: Budi Santoso")
            project_year = st.number_input("Tahun Proyek *", min_value=2000, max_value=2100,
                                            value=datetime.now().year, step=1)
            document_version = st.text_input("Versi Dokumen", value="v1.0")
            upload_date_input = st.date_input("Tanggal Diunggah", value=date.today())

        summary = st.text_area(
            "📝 Ringkasan Isu *", height=100,
            value=st.session_state.autofill_result.get("summary", ""),
            placeholder="Jelaskan secara singkat isu/masalah yang terjadi..."
        )
        root_cause = st.text_area(
            "🔎 Akar Masalah (Know-Why) *", height=100,
            value=st.session_state.autofill_result.get("root_cause", ""),
            placeholder="Jelaskan akar penyebab dari isu tersebut..."
        )
        recommendation = st.text_area(
            "✅ Rekomendasi Solusi / Tindak Lanjut *", height=100,
            value=st.session_state.autofill_result.get("recommendation", ""),
            placeholder="Jelaskan rekomendasi atau tindakan korektif yang diusulkan..."
        )

        submitted = st.form_submit_button("💾 Simpan Isu (Status: Draft/Pending Review)", use_container_width=True)

        if submitted:
            # ---- Validasi form agar tidak ada data kosong yang menyebabkan crash ----
            errors = []
            if not title or not title.strip():
                errors.append("Judul Isu wajib diisi.")
            if not uploader or not uploader.strip():
                errors.append("Nama Pengunggah wajib diisi.")
            if not summary or not summary.strip():
                errors.append("Ringkasan Isu wajib diisi.")
            if not root_cause or not root_cause.strip():
                errors.append("Akar Masalah wajib diisi.")
            if not recommendation or not recommendation.strip():
                errors.append("Rekomendasi Solusi wajib diisi.")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                data = {
                    "title": title,
                    "project_name": project_name,
                    "category": category,
                    "impact_level": impact_level,
                    "status": STATUS_DRAFT,
                    "summary": summary,
                    "root_cause": root_cause,
                    "recommendation": recommendation,
                    "uploader": uploader,
                    "upload_date": upload_date_input.strftime("%Y-%m-%d"),
                    "project_year": int(project_year),
                    "document_version": document_version if document_version.strip() else "v1.0",
                    "file_name": uploaded_file.name if uploaded_file is not None else "",
                    "extracted_text": st.session_state.extracted_text_cache,
                }
                success = insert_issue(data)
                if success:
                    st.success("✅ Isu berhasil disimpan dengan status **Draft / Pending Review**. "
                               "Menunggu verifikasi PMO/Manager di Approval Center.")
                    st.session_state.autofill_result = {"summary": "", "root_cause": "", "recommendation": ""}
                    st.session_state.extracted_text_cache = ""
                    st.balloons()


# ==============================================================================
# 11. HALAMAN: APPROVAL CENTER (Governance Workflow)
# ==============================================================================

def page_approval_center(df: pd.DataFrame):
    st.markdown("### ✅ Approval Center — Khusus PMO / Manager")
    st.caption("Tinjau dan tetapkan status governance untuk setiap entri isu yang diunggah.")

    pending_df = df[df["status"] == STATUS_DRAFT] if not df.empty else df

    tab_pending, tab_all = st.tabs([f"🟡 Menunggu Review ({len(pending_df)})", "📋 Riwayat Seluruh Status"])

    with tab_pending:
        if pending_df.empty:
            st.success("🎉 Tidak ada entri yang menunggu review saat ini. Semua isu sudah diverifikasi/ditindaklanjuti.")
        else:
            for _, row in pending_df.iterrows():
                with st.expander(f"📄 {row['title']}  —  Diunggah oleh {row['uploader']} ({row['upload_date']})"):
                    st.markdown(f"**Kategori:** {row['category']} &nbsp;|&nbsp; **Dampak:** {row['impact_level']} "
                                f"&nbsp;|&nbsp; **Proyek:** {row['project_name'] or '-'} "
                                f"&nbsp;|&nbsp; **Versi Dokumen:** {row['document_version']}")
                    st.markdown(f"**📝 Ringkasan Isu:**\n\n{row['summary']}")
                    st.markdown(f"**🔎 Akar Masalah:**\n\n{row['root_cause']}")
                    st.markdown(f"**✅ Rekomendasi:**\n\n{row['recommendation']}")
                    if row['file_name']:
                        st.markdown(f"**📎 Dokumen Pendukung:** {row['file_name']}")

                    reviewer_notes = st.text_area(
                        "Catatan Reviewer (opsional)", key=f"notes_{row['id']}",
                        placeholder="Tambahkan catatan verifikasi di sini..."
                    )
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        if st.button("🟢 Verifikasi (Approve)", key=f"approve_{row['id']}", use_container_width=True):
                            if update_issue_status(row['id'], STATUS_VERIFIED, reviewer_notes):
                                st.success(f"Isu '{row['title']}' berhasil diverifikasi.")
                                st.rerun()
                    with col_b:
                        if st.button("🔴 Tolak / Arsipkan", key=f"reject_{row['id']}", use_container_width=True):
                            if update_issue_status(row['id'], STATUS_REJECTED, reviewer_notes):
                                st.warning(f"Isu '{row['title']}' ditolak/diarsipkan.")
                                st.rerun()
                    with col_c:
                        if st.button("🗑️ Hapus Permanen", key=f"delete_{row['id']}", use_container_width=True):
                            if delete_issue(row['id']):
                                st.warning(f"Isu '{row['title']}' dihapus permanen dari database.")
                                st.rerun()

    with tab_all:
        if df.empty:
            st.info("Belum ada data untuk ditampilkan.")
        else:
            display_cols = ["id", "title", "category", "impact_level", "status",
                             "uploader", "upload_date", "reviewed_by", "reviewed_date", "reviewer_notes"]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


# ==============================================================================
# 12. HALAMAN: DASHBOARD ANALITIK MENDALAM
# ==============================================================================

def page_analytics(df: pd.DataFrame):
    st.markdown("### 📈 Dashboard Analitik Mendalam")

    if df.empty:
        st.info("Belum ada data untuk dianalisis. Silakan unggah isu terlebih dahulu.")
        return

    render_kpi_cards(df)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Tren Isu berdasarkan Kategori")
        cat_counts = df["category"].value_counts().reset_index()
        cat_counts.columns = ["Kategori", "Jumlah"]
        fig = px.bar(cat_counts, x="Jumlah", y="Kategori", orientation="h",
                     color="Jumlah", color_continuous_scale=["#D6E4FF", COLOR_ACCENT])
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=380,
                          yaxis=dict(categoryorder="total ascending"), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Status Governance per Kategori")
        cross = df.groupby(["category", "status"]).size().reset_index(name="Jumlah")
        color_map = {STATUS_VERIFIED: COLOR_EMERALD, STATUS_DRAFT: COLOR_AMBER, STATUS_REJECTED: COLOR_RED}
        fig2 = px.bar(cross, x="category", y="Jumlah", color="status", barmode="stack",
                      color_discrete_map=color_map)
        fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=380,
                           xaxis_title=None, yaxis_title=None, legend_title_text="Status")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### Tren Jumlah Isu per Tahun Proyek")
    try:
        year_trend = df.groupby("project_year").size().reset_index(name="Jumlah").sort_values("project_year")
        fig3 = px.line(year_trend, x="project_year", y="Jumlah", markers=True)
        fig3.update_traces(line_color=COLOR_ACCENT, line_width=3, marker=dict(size=9, color=COLOR_ACCENT_DARK))
        fig3.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320,
                           xaxis_title="Tahun Proyek", yaxis_title="Jumlah Isu")
        st.plotly_chart(fig3, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ Tidak dapat menampilkan grafik tren tahunan: {e}")

    st.markdown("#### Matriks Dampak vs Kategori")
    try:
        matrix = df.pivot_table(index="category", columns="impact_level", aggfunc="size", fill_value=0)
        for col in IMPACT_LEVELS:
            if col not in matrix.columns:
                matrix[col] = 0
        matrix = matrix[IMPACT_LEVELS]
        fig4 = px.imshow(matrix, text_auto=True, color_continuous_scale=["#F5F5F7", COLOR_ACCENT],
                         aspect="auto")
        fig4.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=380)
        st.plotly_chart(fig4, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ Tidak dapat menampilkan matriks dampak: {e}")


# ==============================================================================
# 13. HALAMAN: EXPORT DATA
# ==============================================================================

def page_export(df: pd.DataFrame, filters: dict):
    st.markdown("### 📁 Export Data untuk Laporan Formal")
    st.caption("Ekspor data terfilter (sesuai pengaturan sidebar) atau seluruh dataset.")

    export_scope = st.radio("Pilih cakupan data:", ["Seluruh Data", "Data Terfilter (sesuai sidebar)"], horizontal=True)

    if export_scope == "Data Terfilter (sesuai sidebar)":
        export_df = apply_filters(df, filters)
    else:
        export_df = df

    st.markdown(f"Total baris yang akan diekspor: **{len(export_df)}**")
    st.dataframe(export_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        try:
            csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Unduh sebagai CSV", data=csv_bytes,
                file_name=f"lessons_learned_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv", use_container_width=True
            )
        except Exception as e:
            st.error(f"❌ Gagal membuat file CSV: {e}")

    with col2:
        try:
            excel_bytes = dataframe_to_excel_bytes(export_df)
            if excel_bytes:
                st.download_button(
                    "⬇️ Unduh sebagai Excel (.xlsx)", data=excel_bytes,
                    file_name=f"lessons_learned_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"❌ Gagal membuat file Excel: {e}")


# ==============================================================================
# 14. SIDEBAR: FILTER GLOBAL & NAVIGASI PERAN
# ==============================================================================

def render_sidebar(df: pd.DataFrame) -> dict:
    """Merender seluruh kontrol sidebar (filter & role) dan mengembalikan
    dict filter yang akan dipakai oleh halaman-halaman lain."""
    with st.sidebar:
        st.markdown("## 🧭 Navigasi & Filter")
        st.markdown("---")

        role = st.selectbox("👤 Login Sebagai", ["Staff / Uploader", "PMO / Manager"], index=0)
        st.session_state["current_role"] = role

        st.markdown("---")
        st.markdown("### 🔎 Filter Data")

        categories_available = sorted(df["category"].dropna().unique().tolist()) if not df.empty else CATEGORY_OPTIONS
        selected_categories = st.multiselect("Kategori Isu", categories_available, default=[])

        selected_impacts = st.multiselect("Level Dampak", IMPACT_LEVELS, default=[])

        selected_statuses = st.multiselect("Status Verifikasi", ALL_STATUSES, default=[])

        if not df.empty and df["project_year"].notna().any():
            min_year = int(df["project_year"].min())
            max_year = int(df["project_year"].max())
        else:
            min_year, max_year = 2015, datetime.now().year

        if min_year == max_year:
            max_year = min_year + 1
        year_range = st.slider("Rentang Tahun Proyek", min_value=min_year, max_value=max_year,
                                value=(min_year, max_year))

        st.markdown("---")
        if st.button("🔄 Reset Semua Filter", use_container_width=True):
            st.rerun()

        st.markdown("---")
        st.caption("© 2026 Enterprise Knowledge Management Platform\nStrategic Lessons Learned System")

    return {
        "categories": selected_categories,
        "impacts": selected_impacts,
        "statuses": selected_statuses,
        "year_range": year_range,
    }


# ==============================================================================
# 15. FUNGSI UTAMA (MAIN)
# ==============================================================================

def main():
    st.set_page_config(
        page_title="Enterprise KM & Strategic Lessons Learned",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Inisialisasi database di awal, aman dipanggil berulang
    init_db()

    # Muat custom CSS
    load_custom_css()

    # Header utama aplikasi
    st.markdown("""
    <div class="km-header">
        <h1>🧠 Enterprise Knowledge Search & Strategic Lessons Learned Platform</h1>
        <p>Dokumentasikan, telusuri, dan analisis isu strategis proyek — dari akar masalah hingga tindakan korektif.</p>
    </div>
    """, unsafe_allow_html=True)

    # Ambil seluruh data terkini dari database
    df = fetch_all_issues()

    # Render sidebar & ambil nilai filter
    filters = render_sidebar(df)

    # Navigasi utama menggunakan tabs
    tabs = st.tabs([
        "📊 Dashboard Utama",
        "🔍 Pencarian & Telusuri",
        "📤 Unggah Isu Baru",
        "✅ Approval Center",
        "📈 Analitik Mendalam",
        "📁 Export Data",
    ])

    with tabs[0]:
        try:
            page_dashboard(apply_filters(df, filters))
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada Dashboard: {e}")

    with tabs[1]:
        try:
            page_search(df, filters)
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada halaman Pencarian: {e}")

    with tabs[2]:
        try:
            page_upload()
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada halaman Unggah: {e}")

    with tabs[3]:
        try:
            if st.session_state.get("current_role") == "PMO / Manager":
                page_approval_center(df)
            else:
                st.warning("🔒 Halaman ini khusus untuk peran **PMO / Manager**. "
                           "Silakan ubah peran Anda di sidebar untuk mengakses Approval Center.")
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada Approval Center: {e}")

    with tabs[4]:
        try:
            page_analytics(apply_filters(df, filters))
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada Analitik: {e}")

    with tabs[5]:
        try:
            page_export(df, filters)
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan pada Export Data: {e}")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("❌ Terjadi kesalahan tak terduga pada aplikasi.")
        st.exception(e)

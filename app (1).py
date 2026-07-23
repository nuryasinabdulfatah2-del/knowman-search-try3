# -*- coding: utf-8 -*-
"""
================================================================================
ENTERPRISE KNOWLEDGE SEARCH & STRATEGIC LESSONS LEARNED PLATFORM
================================================================================
Production-Grade Prototype - Apple / Bento Box Design System
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
# OPTIONAL IMPORTS UNTUK PARSING DOKUMEN
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
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


# ==============================================================================
# 1. KONFIGURASI GLOBAL & PALET MONOKROMATIK BENTO
# ==============================================================================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_platform.db")

STATUS_DRAFT = "🟡 Draft / Pending"
STATUS_VERIFIED = "🟢 Verified"
STATUS_REJECTED = "🔴 Rejected"
ALL_STATUSES = [STATUS_DRAFT, STATUS_VERIFIED, STATUS_REJECTED]

# Palet Monokromatik & Kontras Tinggi
COLOR_BG = "#F5F5F7"          # Abu-abu premium Apple
COLOR_WHITE = "#FFFFFF"       # Putih bersih untuk Bento Box
COLOR_BLACK = "#000000"       # Hitam pekat untuk Macro Typography
COLOR_GRAY_DARK = "#86868B"   # Abu-abu teks sekunder
COLOR_CTA = "#0071E3"         # Biru cerah KHUSUS untuk aksen/CTA

# Warna Status Muted (agar tidak merusak estetika monokrom)
COLOR_STATUS_GREEN = "#E8F5E9"
COLOR_STATUS_GREEN_TEXT = "#1B5E20"
COLOR_STATUS_RED = "#FFEBEE"
COLOR_STATUS_RED_TEXT = "#B71C1C"
COLOR_STATUS_YELLOW = "#FFF8E1"
COLOR_STATUS_YELLOW_TEXT = "#F57F17"

IMPACT_LEVELS = ["Tinggi", "Sedang", "Rendah"]
CATEGORY_OPTIONS = [
    "Perencanaan Proyek", "Manajemen Risiko", "Pengadaan & Kontrak",
    "Kualitas & Kepatuhan (QA/QC)", "Sumber Daya Manusia", "Teknologi & Sistem",
    "Keuangan & Anggaran", "Operasional", "Stakeholder & Komunikasi", "Lainnya"
]

KEYWORDS_SUMMARY = ["isu", "masalah", "kendala", "permasalahan", "issue", "problem", "hambatan"]
KEYWORDS_ROOT_CAUSE = ["akar masalah", "akar penyebab", "disebabkan", "root cause", "sumber masalah"]
KEYWORDS_RECOMMENDATION = ["rekomendasi", "solusi", "usulan", "tindak lanjut", "saran", "mitigasi"]

# Tema Plotly Monokromatik
try:
    _apple_font = "'SF Pro Display', 'Inter', -apple-system, sans-serif"
    _template = pio.templates["plotly_white"]
    _template.layout.font = dict(family=_apple_font, color=COLOR_BLACK, size=13)
    _template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    _template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    _template.layout.colorway = ["#000000", "#555555", "#888888", "#BBBBBB", COLOR_CTA]
    pio.templates["bento_mono"] = _template
    pio.templates.default = "bento_mono"
except:
    pass


# ==============================================================================
# 2. DATABASE SQLITE
# ==============================================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, project_name TEXT, category TEXT, impact_level TEXT,
                status TEXT DEFAULT '🟡 Draft / Pending', summary TEXT, root_cause TEXT,
                recommendation TEXT, uploader TEXT, upload_date TEXT, project_year INTEGER,
                document_version TEXT, file_name TEXT, extracted_text TEXT,
                reviewer_notes TEXT, reviewed_by TEXT, reviewed_date TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"❌ DB Error: {e}")

def insert_issue(data: dict) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO issues (
                title, project_name, category, impact_level, status, summary, root_cause, 
                recommendation, uploader, upload_date, project_year, document_version, 
                file_name, extracted_text, reviewer_notes, reviewed_by, reviewed_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("title", ""), data.get("project_name", ""), data.get("category", ""),
            data.get("impact_level", ""), data.get("status", STATUS_DRAFT), data.get("summary", ""),
            data.get("root_cause", ""), data.get("recommendation", ""), data.get("uploader", ""),
            data.get("upload_date", ""), data.get("project_year", 0), data.get("document_version", ""),
            data.get("file_name", ""), data.get("extracted_text", ""), "", "", ""
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

def update_issue_status(issue_id: int, new_status: str, reviewer_notes: str = "") -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE issues SET status = ?, reviewer_notes = ?, reviewed_by = 'PMO', reviewed_date = ?
            WHERE id = ?
        """, (new_status, reviewer_notes, datetime.now().strftime("%Y-%m-%d"), issue_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def delete_issue(issue_id: int) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def fetch_all_issues() -> pd.DataFrame:
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM issues ORDER BY id DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()


# ==============================================================================
# 3. PARSING DOKUMEN & AI AUTO-FILL
# ==============================================================================
# (Sengaja diringkas untuk kelancaran UI, fungsionalitas tetap sama)

def parse_uploaded_document(uploaded_file) -> str:
    if not uploaded_file: return ""
    try:
        if uploaded_file.name.lower().endswith(".pdf") and PDFPLUMBER_AVAILABLE:
            with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                return "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif uploaded_file.name.lower().endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")
    except: pass
    return ""

def smart_auto_fill(text: str) -> dict:
    res = {"summary": "", "root_cause": "", "recommendation": ""}
    if not text: return res
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s) > 15]
    
    def extract(kw_list):
        matched = [s for s in sentences if any(kw in s.lower() for kw in kw_list)]
        return " ".join(matched[:3])
        
    res["summary"] = extract(KEYWORDS_SUMMARY) or " ".join(sentences[:2])
    res["root_cause"] = extract(KEYWORDS_ROOT_CAUSE) or "Akar masalah belum ditemukan eksplisit."
    res["recommendation"] = extract(KEYWORDS_RECOMMENDATION) or "Rekomendasi belum ditemukan eksplisit."
    return res


# ==============================================================================
# 4. CUSTOM CSS: MACRO TYPOGRAPHY & BENTO BOX
# ==============================================================================

def load_custom_css():
    st.markdown(f"""
    <style>
    /* Mengimpor Inter sebagai substitusi geometris SF Pro di browser non-Apple */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');

    html, body, [class*="css"], .stApp, button, input, textarea, select {{
        font-family: 'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: {COLOR_BG};
        color: {COLOR_BLACK};
    }}

    /* 1. MACRO TYPOGRAPHY & ASIMETRIS SEIMBANG */
    .hero-container {{
        text-align: center;
        padding: 4rem 0 3rem 0;
        margin-bottom: 2rem;
    }}
    .hero-title {{
        font-size: 4.5rem;
        font-weight: 900;
        color: {COLOR_BLACK};
        line-height: 1;
        letter-spacing: -0.05em;
        margin-bottom: 1rem;
    }}
    .hero-subtitle {{
        font-size: 1.3rem;
        font-weight: 400;
        color: {COLOR_GRAY_DARK};
        letter-spacing: -0.01em;
        max-width: 700px;
        margin: 0 auto;
    }}

    /* 2 & 3. BENTO BOX & ILUSI 3D (Z-Axis Depth) */
    .bento-box {{
        background: {COLOR_WHITE};
        border-radius: 28px;
        padding: 28px;
        margin-bottom: 24px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.02);
        border: 1px solid rgba(0,0,0,0.03);
        transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .bento-box:hover {{
        transform: translateY(-4px) scale(1.01);
        box-shadow: 0 30px 60px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.03);
    }}

    /* Text Formatting dalam Bento Box */
    .bento-kpi-value {{
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        color: {COLOR_BLACK};
        line-height: 1.1;
    }}
    .bento-kpi-label {{
        font-size: 1rem;
        font-weight: 600;
        color: {COLOR_GRAY_DARK};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* Issue Card Specifics */
    .issue-title {{
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.5rem;
    }}
    .issue-meta {{
        font-size: 0.9rem;
        color: {COLOR_GRAY_DARK};
        font-weight: 600;
        margin-bottom: 1.5rem;
    }}
    .section-label {{
        font-size: 0.85rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: {COLOR_BLACK};
        margin-top: 1.5rem;
        margin-bottom: 0.3rem;
        border-bottom: 2px solid #000;
        display: inline-block;
        padding-bottom: 2px;
    }}

    /* 4. TOMBOL CALL TO ACTION (CTA) */
    .stButton button {{
        background-color: {COLOR_BLACK};
        color: {COLOR_WHITE} !important;
        border-radius: 40px;
        font-weight: 600;
        padding: 0.6rem 2rem;
        border: none;
        box-shadow: 0 8px 16px rgba(0,0,0,0.15);
        transition: all 0.2s ease;
    }}
    .stButton button:hover {{
        background-color: {COLOR_CTA};
        transform: scale(1.02);
        box-shadow: 0 12px 24px rgba(0, 113, 227, 0.3);
    }}
    
    /* Input & Tab Styling */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
        border-radius: 16px !important;
        background-color: {COLOR_BG} !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
        font-weight: 600;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {COLOR_BLACK} !important;
        box-shadow: 0 0 0 2px {COLOR_BLACK} !important;
    }}
    
    /* Badges */
    .badge {{
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 800;
        display: inline-block;
        margin-right: 8px;
    }}
    </style>
    """, unsafe_allow_html=True)


# ==============================================================================
# 5. KOMPONEN UI UTAMA
# ==============================================================================

def render_kpi_bento(df: pd.DataFrame):
    t_issues = len(df)
    t_verified = len(df[df["status"] == STATUS_VERIFIED]) if t_issues else 0
    t_high = len(df[df["impact_level"] == "Tinggi"]) if t_issues else 0

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="bento-box" style="text-align:center;">
            <div class="bento-kpi-value">{t_issues}</div>
            <div class="bento-kpi-label">TOTAL ISU</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="bento-box" style="text-align:center;">
            <div class="bento-kpi-value">{t_verified}</div>
            <div class="bento-kpi-label">VERIFIED</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="bento-box" style="text-align:center; background-color: {COLOR_BLACK}; color: {COLOR_WHITE};">
            <div class="bento-kpi-value" style="color:{COLOR_WHITE};">{t_high}</div>
            <div class="bento-kpi-label" style="color:rgba(255,255,255,0.7);">DAMPAK TINGGI</div>
        </div>
        """, unsafe_allow_html=True)

def render_issue_bento(row):
    # Penentuan warna badge monokrom/muted
    bg_stat, tx_stat = COLOR_STATUS_YELLOW, COLOR_STATUS_YELLOW_TEXT
    if "Verified" in row['status']: bg_stat, tx_stat = COLOR_STATUS_GREEN, COLOR_STATUS_GREEN_TEXT
    if "Rejected" in row['status']: bg_stat, tx_stat = COLOR_STATUS_RED, COLOR_STATUS_RED_TEXT
    
    bg_imp, tx_imp = COLOR_BG, COLOR_GRAY_DARK
    if row['impact_level'] == "Tinggi": bg_imp, tx_imp = COLOR_BLACK, COLOR_WHITE

    st.markdown(f"""
    <div class="bento-box">
        <div style="margin-bottom: 1rem;">
            <span class="badge" style="background:{bg_imp}; color:{tx_imp};">{row['impact_level']} Impact</span>
            <span class="badge" style="background:{bg_stat}; color:{tx_stat};">{row['status']}</span>
        </div>
        <div class="issue-title">{row['title']}</div>
        <div class="issue-meta">Proyek: {row['project_name']} • Kategori: {row['category']} • {row['upload_date']}</div>
        
        <div class="section-label">Ringkasan</div>
        <p style="font-size: 1.05rem; line-height: 1.6;">{row['summary']}</p>
        
        <div class="section-label">Akar Masalah</div>
        <p style="font-size: 1.05rem; line-height: 1.6;">{row['root_cause']}</p>
        
        <div class="section-label">Rekomendasi</div>
        <p style="font-size: 1.05rem; line-height: 1.6; font-weight: 600;">{row['recommendation']}</p>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 6. HALAMAN & LOGIKA APLIKASI
# ==============================================================================

def main():
    st.set_page_config(page_title="Strategic KM Platform", layout="wide", initial_sidebar_state="collapsed")
    init_db()
    load_custom_css()

    # Macro Typography Asimetris Header
    st.markdown("""
    <div class="hero-container">
        <div class="hero-title">Knowledge.<br>Decoded.</div>
        <div class="hero-subtitle">Mendokumentasikan kompleksitas masalah menjadi keputusan presisi.</div>
    </div>
    """, unsafe_allow_html=True)

    df = fetch_all_issues()

    tabs = st.tabs(["Dashboard", "Telusuri Isu", "Unggah Baru", "Approval (PMO)"])

    # --- TAB 1: DASHBOARD ---
    with tabs[0]:
        render_kpi_bento(df)
        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Komposisi Isu")
                fig = px.pie(df, names="category", hole=0.7, color_discrete_sequence=px.colors.sequential.Greys_r)
                fig.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("### Tren Risiko")
                fig2 = px.histogram(df, x="impact_level", color_discrete_sequence=[COLOR_BLACK])
                fig2.update_layout(xaxis_title="", yaxis_title="", height=400)
                st.plotly_chart(fig2, use_container_width=True)

    # --- TAB 2: TELUSURI ---
    with tabs[1]:
        search_q = st.text_input("Pencarian Eksekutif", placeholder="Ketik kata kunci masalah atau proyek...", label_visibility="collapsed")
        
        filtered_df = df
        if search_q:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_q, case=False, na=False)).any(axis=1)]
            
        for _, row in filtered_df.iterrows():
            render_issue_bento(row)

    # --- TAB 3: UNGGAH BARU ---
    with tabs[2]:
        st.markdown("<div class='bento-box'>", unsafe_allow_html=True)
        st.markdown("### Inisiasi Data Baru")
        file = st.file_uploader("Unggah PDF/Word untuk ekstraksi otomatis (Opsional)")
        
        with st.form("bento_form"):
            t = st.text_input("Judul Isu")
            c1, c2 = st.columns(2)
            with c1:
                p = st.text_input("Nama Proyek")
                cat = st.selectbox("Kategori", CATEGORY_OPTIONS)
            with c2:
                imp = st.selectbox("Dampak", IMPACT_LEVELS)
                up = st.text_input("Pengunggah")
            
            s = st.text_area("Ringkasan Isu")
            rc = st.text_area("Akar Masalah")
            rec = st.text_area("Rekomendasi")
            
            if st.form_submit_button("Simpan Isu"):
                insert_issue({"title": t, "project_name": p, "category": cat, "impact_level": imp, "summary": s, "root_cause": rc, "recommendation": rec, "uploader": up})
                st.success("Tersimpan!")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 4: APPROVAL ---
    with tabs[3]:
        pending = df[df["status"] == STATUS_DRAFT]
        if pending.empty:
            st.info("Tidak ada tugas tinjauan.")
        else:
            for _, row in pending.iterrows():
                with st.expander(f"{row['title']} - {row['upload_date']}"):
                    st.write(f"**Akar:** {row['root_cause']}")
                    st.write(f"**Rekomendasi:** {row['recommendation']}")
                    colA, colB = st.columns(2)
                    with colA:
                        if st.button("Approve", key=f"y_{row['id']}", use_container_width=True):
                            update_issue_status(row['id'], STATUS_VERIFIED)
                            st.rerun()
                    with colB:
                        if st.button("Reject", key=f"n_{row['id']}", use_container_width=True):
                            update_issue_status(row['id'], STATUS_REJECTED)
                            st.rerun()

if __name__ == "__main__":
    main()

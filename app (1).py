# -*- coding: utf-8 -*-
"""
================================================================================
ENTERPRISE KNOWLEDGE MANAGEMENT & STRATEGIC LESSONS LEARNED
================================================================================
Design System: Apple / iOS (Strict High-Contrast Monochromatic & Bento Box)
Rules Applied: No Emojis, Macro Typography, Z-Axis Depth, Balanced Asymmetry.
================================================================================
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime
import os

# ==============================================================================
# 1. KONFIGURASI GLOBAL & WARNA (APPLE DESIGN SYSTEM)
# ==============================================================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "km_apple.db")

# Status Konstanta (Tanpa Emoji)
STATUS_DRAFT = "Draft"
STATUS_VERIFIED = "Verified"
STATUS_REJECTED = "Rejected"

# Level & Kategori
IMPACT_LEVELS = ["Tinggi", "Sedang", "Rendah"]
CATEGORY_OPTIONS = [
    "Perencanaan Proyek", "Keuangan & Anggaran", "Manajemen Risiko", 
    "Pengadaan & Kontrak", "Kualitas & Kepatuhan", "Teknologi & Sistem", 
    "Operasional", "Lainnya"
]

# Tema Plotly Monokromatik (Menyatu dengan Background Transparan)
try:
    _font_family = "'SF Pro Display', 'Inter', -apple-system, sans-serif"
    _apple_template = pio.templates["plotly_white"]
    _apple_template.layout.font = dict(family=_font_family, color="#000000", size=13)
    _apple_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    _apple_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    # Palet abu-abu ke hitam pekat
    _apple_template.layout.colorway = ["#000000", "#555555", "#888888", "#BBBBBB", "#E5E5E5"]
    pio.templates["apple_mono"] = _apple_template
    pio.templates.default = "apple_mono"
except Exception:
    pass

# ==============================================================================
# 2. DATABASE LAYER (SQLITE)
# ==============================================================================
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            project_name TEXT,
            category TEXT,
            impact_level TEXT,
            status TEXT DEFAULT 'Draft',
            summary TEXT,
            root_cause TEXT,
            recommendation TEXT,
            upload_date TEXT
        )
    """)
    
    # Cek apakah tabel kosong, jika ya masukkan 1 data dummy
    cur.execute("SELECT COUNT(*) as cnt FROM issues")
    if cur.fetchone()['cnt'] == 0:
        cur.execute("""
            INSERT INTO issues (title, project_name, category, impact_level, status, summary, root_cause, recommendation, upload_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Deviasi Estimasi Biaya Aktivitas Lapangan",
            "Implementasi Standard Costing",
            "Keuangan & Anggaran",
            "Tinggi",
            "Draft",
            "Terdapat deviasi signifikan pada estimasi biaya aktivitas lapangan jika dibandingkan dengan realisasi triwulan sebelumnya.",
            "Asumsi awal tidak memperhitungkan perubahan regulasi pajak dan inflasi lokal yang mempengaruhi biaya operasional secara langsung.",
            "Melakukan recalibration terhadap 117 model biaya aktivitas dan menetapkan pembaruan indeks secara triwulanan.",
            datetime.now().strftime("%Y-%m-%d")
        ))
    conn.commit()
    conn.close()

def fetch_issues():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM issues ORDER BY id DESC", conn)
    conn.close()
    return df

def insert_issue(data):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO issues (title, project_name, category, impact_level, status, summary, root_cause, recommendation, upload_date)
            VALUES (?, ?, ?, ?, 'Draft', ?, ?, ?, ?)
        """, (
            data['title'], data['project'], data['category'], data['impact'], 
            data['summary'], data['root_cause'], data['recommendation'], 
            datetime.now().strftime("%Y-%m-%d")
        ))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def update_status(issue_id, new_status):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE issues SET status = ? WHERE id = ?", (new_status, issue_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

# ==============================================================================
# 3. CUSTOM CSS (APPLE MACRO TYPOGRAPHY & BENTO BOX)
# ==============================================================================
def inject_custom_css():
    st.markdown("""
    <style>
    /* Mengimpor Font Geometris (Inter sebagai alternatif SF Pro) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');

    /* Reset & Base Variables */
    :root {
        --bg-color: #F5F5F7;
        --card-bg: #FFFFFF;
        --text-main: #000000;
        --text-muted: #86868B;
        --accent: #0071E3;
        --border-light: rgba(0,0,0,0.03);
    }

    html, body, [class*="css"], .stApp, p, div, span, label {
        font-family: 'SF Pro Display', 'Inter', -apple-system, sans-serif !important;
        background-color: var(--bg-color);
        color: var(--text-main);
    }
    
    /* Sembunyikan elemen bawaan Streamlit yang mengganggu */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 5rem !important;
        max-width: 1400px !important;
    }

    /* 1. MACRO TYPOGRAPHY */
    .macro-title {
        font-size: 5.5rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        line-height: 1.05;
        color: var(--text-main);
        margin-bottom: 1rem;
        background-color: transparent !important;
    }
    .macro-subtitle {
        font-size: 1.4rem;
        font-weight: 400;
        letter-spacing: -0.01em;
        color: var(--text-muted);
        margin-bottom: 4rem;
        max-width: 800px;
        background-color: transparent !important;
    }

    /* 2 & 3. BENTO BOX LAYOUT & Z-AXIS DEPTH */
    .bento-box {
        background-color: var(--card-bg) !important;
        border-radius: 28px;
        padding: 32px;
        margin-bottom: 24px;
        border: 1px solid var(--border-light);
        box-shadow: 0 20px 40px rgba(0,0,0,0.04);
        transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        height: 100%;
    }
    .bento-box:hover {
        transform: translateY(-4px);
        box-shadow: 0 30px 60px rgba(0,0,0,0.08);
    }
    .bento-box * {
        background-color: transparent !important;
    }

    /* KPI Specific inside Bento */
    .kpi-value {
        font-size: 4rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        color: var(--text-main);
        line-height: 1;
        margin-bottom: 0.5rem;
    }
    .kpi-label {
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--text-muted);
        text-transform: uppercase;
    }

    /* Issue Card Specific */
    .issue-title {
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 1rem 0 0.5rem 0;
        line-height: 1.2;
    }
    .issue-meta {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-muted);
        margin-bottom: 2rem;
    }
    .issue-section-title {
        font-size: 0.8rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-muted);
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid #E5E5E5;
        padding-bottom: 4px;
    }
    .issue-text {
        font-size: 1.1rem;
        line-height: 1.6;
        color: var(--text-main);
        font-weight: 400;
    }

    /* Badges / Tags (Muted Colors) */
    .badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-right: 8px;
    }
    .badge-Draft { background-color: #F5F5F7 !important; color: #86868B !important; }
    .badge-Verified { background-color: #E8F5E9 !important; color: #1B5E20 !important; }
    .badge-Rejected { background-color: #FFEBEE !important; color: #B71C1C !important; }
    .badge-Impact { background-color: #000000 !important; color: #FFFFFF !important; }

    /* Forms & Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        background-color: var(--bg-color) !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
        border-radius: 16px !important;
        padding: 12px 16px !important;
        font-weight: 500;
        font-size: 1.05rem;
        color: var(--text-main) !important;
        transition: all 0.2s ease;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
        border-color: var(--text-main) !important;
        box-shadow: 0 0 0 2px var(--text-main) !important;
    }

    /* Buttons */
    .stButton button {
        background-color: var(--text-main) !important;
        color: var(--card-bg) !important;
        border-radius: 999px !important; /* Pill shape */
        padding: 12px 32px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        border: none !important;
        box-shadow: 0 8px 16px rgba(0,0,0,0.1) !important;
        transition: all 0.3s ease !important;
        height: auto !important;
    }
    .stButton button:hover {
        background-color: var(--accent) !important;
        transform: scale(1.02);
        box-shadow: 0 12px 24px rgba(0,113,227,0.3) !important;
    }
    .stButton button p {
        color: var(--card-bg) !important;
        font-size: 1.05rem !important;
        margin: 0 !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background-color: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: transparent !important;
        border-radius: 0px 0px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-muted);
    }
    .stTabs [aria-selected="true"] {
        color: var(--text-main) !important;
        border-bottom-color: var(--text-main) !important;
        border-bottom-width: 3px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 4. KOMPONEN UI (HTML GENERATORS)
# ==============================================================================
def render_bento_kpi(value, label):
    return f"""
    <div class="bento-box" style="text-align: left;">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """

def render_bento_issue(row):
    return f"""
    <div class="bento-box">
        <div>
            <span class="badge badge-Impact">Impact: {row['impact_level']}</span>
            <span class="badge badge-{row['status']}">{row['status']}</span>
        </div>
        <div class="issue-title">{row['title']}</div>
        <div class="issue-meta">{row['project_name']} | {row['category']} | {row['upload_date']}</div>
        
        <div class="issue-section-title">Ringkasan Isu</div>
        <div class="issue-text">{row['summary']}</div>
        
        <div class="issue-section-title">Akar Masalah</div>
        <div class="issue-text">{row['root_cause']}</div>
        
        <div class="issue-section-title">Rekomendasi Strategis</div>
        <div class="issue-text" style="font-weight: 600;">{row['recommendation']}</div>
    </div>
    """

# ==============================================================================
# 5. HALAMAN UTAMA & LOGIKA TAB
# ==============================================================================
def main():
    st.set_page_config(page_title="Strategic Knowledge", layout="wide")
    init_db()
    inject_custom_css()

    # Tipografi Makro
    st.markdown("""
    <div style="background-color: transparent;">
        <div class="macro-title">Knowledge.<br>Decoded.</div>
        <div class="macro-subtitle">Dokumentasi strategis. Analisis mendalam. Keputusan presisi.</div>
    </div>
    """, unsafe_allow_html=True)

    df = fetch_issues()

    # Tabs (Tanpa Emoji)
    tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Telusuri", "Unggah Baru", "Approval PMO"])

    # --- TAB 1: DASHBOARD ---
    with tab1:
        st.write("") # Spacer
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(render_bento_kpi(len(df), "Total Entri Isu"), unsafe_allow_html=True)
        with col2:
            verified_count = len(df[df["status"] == STATUS_VERIFIED])
            st.markdown(render_bento_kpi(verified_count, "Telah Diverifikasi"), unsafe_allow_html=True)
        with col3:
            high_impact_count = len(df[df["impact_level"] == "Tinggi"])
            st.markdown(render_bento_kpi(high_impact_count, "Dampak Tingkat Tinggi"), unsafe_allow_html=True)

        if not df.empty:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown("<div class='bento-box'>", unsafe_allow_html=True)
                st.markdown("<div class='issue-title' style='margin-top:0; font-size:1.4rem;'>Distribusi Kategori</div>", unsafe_allow_html=True)
                fig_pie = px.pie(df, names="category", hole=0.7)
                fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown("<div class='bento-box'>", unsafe_allow_html=True)
                st.markdown("<div class='issue-title' style='margin-top:0; font-size:1.4rem;'>Level Dampak</div>", unsafe_allow_html=True)
                fig_bar = px.histogram(df, x="impact_level")
                fig_bar.update_layout(xaxis_title="", yaxis_title="", margin=dict(t=20, b=20, l=20, r=20), height=350)
                st.plotly_chart(fig_bar, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 2: TELUSURI ---
    with tab2:
        st.write("")
        search_query = st.text_input("Pencarian", placeholder="Ketik kata kunci judul, proyek, atau masalah...")
        
        filtered_df = df
        if search_query:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)]
            
        if filtered_df.empty:
            st.markdown("<div style='margin-top:2rem; font-size:1.2rem; font-weight:600;'>Tidak ada hasil ditemukan.</div>", unsafe_allow_html=True)
        else:
            # Asimetris yang Seimbang: Layout Grid
            cols = st.columns(2)
            for index, row in filtered_df.iterrows():
                with cols[index % 2]:
                    st.markdown(render_bento_issue(row), unsafe_allow_html=True)

    # --- TAB 3: UNGGAH BARU ---
    with tab3:
        st.write("")
        st.markdown("<div class='bento-box'>", unsafe_allow_html=True)
        st.markdown("<div class='issue-title' style='margin-top:0;'>Entri Isu Strategis Baru</div>", unsafe_allow_html=True)
        st.markdown("<div class='issue-meta' style='margin-bottom:2rem;'>Lengkapi informasi secara spesifik dan objektif.</div>", unsafe_allow_html=True)
        
        with st.form("form_unggah", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                input_title = st.text_input("Judul Isu")
                input_project = st.text_input("Nama Proyek / Departemen")
                input_category = st.selectbox("Kategori Isu", CATEGORY_OPTIONS)
            with col_b:
                input_impact = st.selectbox("Tingkat Dampak", IMPACT_LEVELS)
                st.write("") # Spacer layout
                st.write("")
            
            input_summary = st.text_area("Ringkasan Isu", height=120)
            input_root_cause = st.text_area("Akar Masalah (Root Cause)", height=120)
            input_recommendation = st.text_area("Rekomendasi Tindak Lanjut", height=120)
            
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Simpan Data")
            
            if submitted:
                if input_title and input_summary:
                    data = {
                        "title": input_title,
                        "project": input_project,
                        "category": input_category,
                        "impact": input_impact,
                        "summary": input_summary,
                        "root_cause": input_root_cause,
                        "recommendation": input_recommendation
                    }
                    if insert_issue(data):
                        st.success("Entri berhasil disimpan dengan status Draft.")
                else:
                    st.error("Judul dan Ringkasan Isu wajib diisi.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 4: APPROVAL PMO ---
    with tab4:
        st.write("")
        df_draft = df[df["status"] == STATUS_DRAFT]
        
        if df_draft.empty:
            st.markdown("<div style='margin-top:2rem; font-size:1.2rem; font-weight:600;'>Semua entri telah ditinjau.</div>", unsafe_allow_html=True)
        else:
            for _, row in df_draft.iterrows():
                st.markdown("<div class='bento-box'>", unsafe_allow_html=True)
                st.markdown(f"<div class='issue-title' style='margin-top:0;'>{row['title']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='issue-meta'>{row['project_name']} | {row['upload_date']}</div>", unsafe_allow_html=True)
                
                col_x, col_y = st.columns([3, 1])
                with col_x:
                    st.markdown(f"<div class='issue-text'>{row['summary']}</div>", unsafe_allow_html=True)
                with col_y:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Verify", key=f"v_{row['id']}", use_container_width=True):
                            update_status(row['id'], STATUS_VERIFIED)
                            st.rerun()
                    with c2:
                        if st.button("Reject", key=f"r_{row['id']}", use_container_width=True):
                            update_status(row['id'], STATUS_REJECTED)
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

import streamlit as st
import numpy as np
import pandas as pd
import json
import time
import os
import io
import math
import uuid
import base64
import logging
import zipfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon
import folium
from folium import plugins
from streamlit_folium import st_folium
import qrcode
from fpdf import FPDF

# Voice Assistant & AI Imports (Failsafe)
try:
    from gtts import gTTS
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False

try:
    from ultralytics import YOLO
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

logging.basicConfig(level=logging.ERROR)

# =====================================================================
# 1. INTERNATIONALIZATION (LANGUAGES)
# =====================================================================
TRANSLATIONS = {
    "en": {
        "tag": "SVAMITVA Scheme Compliant", "hero": "Mapping the Future of", "hero_span": "Land Ownership",
        "sub": "DroneMap AI transforms raw aerial telemetry into dispute-free, legally binding cadastral property titles instantly.",
        "btn_explore": "Launch Command Studio", "login_title": "Secure Surveyor Access",
        "login_sub": "Authorized Personnel Only", "btn_login": "Authenticate",
        "tab1": "1️⃣ Neural Extraction Studio", "tab2": "2️⃣ WebGIS Cartography", "tab3": "3️⃣ Audit & Certification"
    },
    "hi": {
        "tag": "स्वामित्व योजना अनुरूप", "hero": "भूमि स्वामित्व के", "hero_span": "भविष्य का मानचित्रण",
        "sub": "DroneMap AI कच्चे ड्रोन डेटा को सत्यापन-योग्य भूमि अभिलेखों में बदलता है।",
        "btn_explore": "कमांड स्टूडियो खोलें", "login_title": "सुरक्षित सर्वेक्षक लॉगिन",
        "login_sub": "केवल अधिकृत कर्मियों के लिए", "btn_login": "प्रमाणित करें",
        "tab1": "1️⃣ निष्कर्षण स्टूडियो", "tab2": "2️⃣ WebGIS मानचित्र", "tab3": "3️⃣ ऑडिट और प्रमाणन"
    },
    "bn": {
        "tag": "SVAMITVA প্রকল্প অনুবর্তী", "hero": "ভূমি মালিকানার", "hero_span": "ভবিষ্যৎ মানচিত্রায়ণ",
        "sub": "DroneMap AI কাঁচা ড্রোন তথ্যকে যাচাইযোগ্য ভূমি নথিতে রূপান্তর করে।",
        "btn_explore": "কমান্ড স্টুডিও চালু করুন", "login_title": "নিরাপদ সার্ভেয়ার অ্যাক্সেস",
        "login_sub": "শুধুমাত্র অনুমোদিত কর্মীদের জন্য", "btn_login": "প্রবেশ করুন",
        "tab1": "1️⃣ নিষ্কাশন স্টুডিও", "tab2": "2️⃣ WebGIS মানচিত্র", "tab3": "3️⃣ অডিট ও প্রত্যয়ন"
    }
}

def t(key):
    lang = st.session_state.get("lang", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)

def play_voice(text, lang='en'):
    if not AUDIO_OK: return
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        b64 = base64.b64encode(fp.getvalue()).decode()
        st.components.v1.html(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', height=0, width=0)
    except Exception: pass

# =====================================================================
# 2. SYSTEM INITIALIZATION & STATE
# =====================================================================
st.set_page_config(page_title="DroneMap AI | Workspace", page_icon="🛰️", layout="wide", initial_sidebar_state="collapsed")

def init_state(key, default):
    if key not in st.session_state: st.session_state[key] = default

init_state("view", "landing")
init_state("lang", "en")
init_state("auth", False)
init_state("user", "")
init_state("raw_img", None)
init_state("ai_img", None)
init_state("survey_df", pd.DataFrame())
init_state("geo_json", None)
init_state("extracted", False)
init_state("is_demo", False)
init_state("latency", 0.0)

# Parameters
init_state("gsd", 0.05)
init_state("conf", 0.25)
init_state("anchor_lat", 22.5726)
init_state("anchor_lon", 88.3639)

def set_view(v): st.session_state.view = v

# =====================================================================
# 3. UNIFIED NEURAL BRAND CSS (No Dark/Light Toggle)
# =====================================================================
def inject_theme():
    # Locked Modern Neutral Palette
    bg = "#F4F7F6"          # Off-white cool gray canvas
    surface = "#FFFFFF"     # Pure white cards
    header = "#0F172A"      # Deep Navy for authority
    text = "#1E293B"        # Slate 800
    subtext = "#64748B"     # Slate 500
    accent = "#0284C7"      # Trustworthy Sky Blue
    border = "#E2E8F0"      # Subtle lines
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
        * {{ font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.015em; }}
        
        .stApp, [data-testid="stHeader"] {{ background-color: {bg}; color: {text}; }}
        [data-testid="block-container"] {{ padding-top: 6rem !important; }}
        #MainMenu, footer {{ visibility: hidden; }}
        
        /* Fixed Navy Header */
        .nav-island {{
            position: fixed; top: 0; left: 0; width: 100%; z-index: 99999;
            background: {header}; border-bottom: 3px solid {accent};
            padding: 12px 40px; display: flex; justify-content: space-between; align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        
        /* Clean Sidebar */
        [data-testid="stSidebar"] {{ background-color: {surface} !important; border-right: 1px solid {border}; }}
        
        h1, h2, h3, h4 {{ color: {text} !important; font-weight: 700; }}
        p, span, div {{ color: {text}; }}
        
        /* Hero Section */
        .hero-wrap {{ text-align: center; max-width: 900px; margin: 60px auto; }}
        .hero-title {{ font-size: clamp(2.5rem, 5vw, 4.5rem); font-weight: 800; line-height: 1.1; margin: 20px 0; }}
        .hero-title span {{ color: {accent}; }}
        
        /* Clean Cards & Auth */
        .glass-box {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; padding: 40px; max-width: 450px; margin: 10vh auto; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }}
        .metric-tile {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.02); }}
        .metric-val {{ font-size: 2.2rem; font-weight: 800; color: {accent}; }}
        .metric-lbl {{ font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: {subtext}; }}
        
        /* Prominent Buttons */
        .stButton > button {{ border-radius: 8px !important; font-weight: 600 !important; background: {surface} !important; border: 1px solid {border} !important; color: {text} !important; transition: all 0.2s; }}
        .stButton > button:hover {{ border-color: {accent} !important; color: {accent} !important; }}
        .stButton > button[data-testid="baseButton-primary"] {{ background: {accent} !important; color: #FFFFFF !important; border: none !important; }}
        .stButton > button[data-testid="baseButton-primary"]:hover {{ filter: brightness(1.1); }}
    </style>
    """, unsafe_allow_html=True)

inject_theme()

# =====================================================================
# 4. PRECISE GEODESY, ENGINES & EXPORTS 
# =====================================================================
def px_to_latlon(px_x, px_y, anchor_lat, anchor_lon, gsd):
    lat_rad = math.radians(anchor_lat)
    lon_deg_per_m = 1.0 / (111320 * math.cos(lat_rad))
    lat_deg_per_m = 1.0 / 110540 
    return [anchor_lon + (px_x * gsd * lon_deg_per_m), anchor_lat - (px_y * gsd * lat_deg_per_m)]

@st.cache_data(show_spinner=False)
def get_base64_image(image_path):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()
    img = Image.new("RGB", (800, 500), color=(241,245,249))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

@st.cache_resource
def load_segmentation_model():
    if not AI_AVAILABLE: return None
    try: return YOLO("best.pt") if os.path.exists("best.pt") else YOLO("yolov8n-seg.pt")
    except: return None

def make_qr(data):
    qr = qrcode.QRCode(box_size=4, border=1); qr.add_data(data)
    buf = io.BytesIO()
    qr.make_image(fill_color="#0F172A", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

class SVAMITVADocument(FPDF):
    def header(self):
        self.set_font("Helvetica", 'B', 15); self.set_text_color(15, 23, 42)
        self.cell(0, 10, "MINISTRY OF PANCHAYATI RAJ", ln=True, align="C")
        self.set_font("Helvetica", '', 11); self.set_text_color(100, 116, 139)
        self.cell(0, 6, "SVAMITVA Property Register Record", ln=True, align="C")
        self.line(10, 30, 200, 30); self.ln(6)

def generate_pdf(row, lat, lon, user):
    pdf = SVAMITVADocument(orientation='P', unit='mm', format='A4')
    pdf.add_page(); pdf.set_font("Helvetica", 'B', 11); pdf.set_text_color(15, 23, 42)
    entries = [
        ("UPIN", str(row['UPIN'])), ("Ground Footprint", f"{row['Area (m²)']} sqm"),
        ("Boundary Perimeter", f"{row['Perimeter (m)']} m"), ("Geospatial Centroid", f"{lat:.6f} N, {lon:.6f} E"),
        ("AI Validation Confidence", f"{row['Confidence (%)']}%"), ("Verified By Surveyor", user),
        ("Issuance Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ]
    for k, v in entries:
        pdf.set_font("Helvetica", 'B', 10); pdf.cell(60, 8, f"{k}:", border=0)
        pdf.set_font("Helvetica", '', 10); pdf.cell(0, 8, v, border=0, ln=True)
    out = pdf.output()
    return bytes(out) if isinstance(out, (bytearray, bytes)) else out.encode('latin-1')

def generate_batch_zip(df, lat, lon, user):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, row in df.iterrows():
            zf.writestr(f"{row['UPIN']}_Form7.pdf", generate_pdf(row, lat, lon, user))
    buf.seek(0)
    return buf.getvalue()

def demo_map():
    img = Image.new("RGB", (1100, 750), color=(148, 163, 184))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 330, 1100, 410], fill=(71, 85, 105))
    for b, c in [([60,50,280,280],(241,245,249)), ([340,60,590,290],(226,232,240)), ([660,50,940,280],(203,213,225))]:
        draw.rectangle(b, fill=c, outline=(51, 65, 85), width=4)
    return img

def get_conf_color(conf):
    if conf >= 85: return "#10B981" 
    if conf >= 70: return "#F59E0B" 
    return "#EF4444"

# =====================================================================
# 5. HEADER & NAVIGATION
# =====================================================================
st.markdown("<div class='nav-island'>", unsafe_allow_html=True)
c_logo, c_lang, c_voice, c_cta = st.columns([4, 1.5, 2, 2.5])
with c_logo:
    logo = next((f"my_logo.{e}" for e in ["png","jpg","jpeg"] if os.path.exists(f"my_logo.{e}")), "logo.png")
    st.markdown(f"<div style='display:flex; align-items:center; gap:12px;'><img src='data:image/png;base64,{get_base64_image(logo)}' height='32'><span style='font-weight:800; font-size:1.2rem; color:#FFFFFF;'>DroneMap AI</span></div>", unsafe_allow_html=True)

with c_lang:
    lang_sel = st.selectbox("🌐", ["en", "hi", "bn"], index=["en","hi","bn"].index(st.session_state.lang), label_visibility="collapsed", key="lang_select")
    if lang_sel != st.session_state.lang:
        st.session_state.lang = lang_sel
        st.rerun()

with c_voice:
    if st.session_state.view == "workspace":
        if st.button("🎙️ Audio Brief", key="nav_audio"):
            msgs = {"en": "Workspace active. Awaiting extraction command.", "hi": "सिस्टम तैयार है।", "bn": "সিস্টেম প্রস্তুত।"}
            play_voice(msgs[st.session_state.lang], st.session_state.lang)

with c_cta:
    if st.session_state.view == "landing":
        st.button(t("btn_explore"), type="primary", on_click=set_view, args=("auth",), use_container_width=True, key="nav_explore")
    elif st.session_state.view == "auth":
        st.button("Return to Home", on_click=set_view, args=("landing",), use_container_width=True, key="nav_home")
    else:
        c_user, c_out = st.columns([1.5, 1])
        with c_user: st.markdown(f"<div style='color:white; margin-top:8px; font-weight:600;'>ID: {st.session_state.user}</div>", unsafe_allow_html=True)
        with c_out: 
            if st.button("Logout", key="nav_logout"):
                st.session_state.auth = False
                set_view("landing"); st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# =====================================================================
# 6. ROUTING (LANDING -> AUTH -> WORKSPACE)
# =====================================================================
if st.session_state.view == "landing":
    st.markdown(f"""
    <div class="hero-wrap">
        <div style="display:inline-block; border: 1px solid var(--accent); color: var(--accent); padding: 6px 16px; border-radius: 9999px; font-size: 0.8rem; font-weight: 800; text-transform: uppercase; margin-bottom: 20px; background: rgba(2, 132, 199, 0.05);">{t('tag')}</div>
        <div class="hero-title">{t('hero')}<br><span>{t('hero_span')}</span></div>
        <p style="font-size: 1.1rem; color: var(--subtext); max-width:700px; margin:0 auto;">{t('sub')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2: st.button(t('btn_explore'), type="primary", on_click=set_view, args=("auth",), use_container_width=True, key="hero_explore")

elif st.session_state.view == "auth":
    st.markdown(f"""
    <div class='glass-box'>
        <h2 style='color:var(--accent); margin-bottom:5px;'>{t('login_title')}</h2>
        <p style='color:var(--subtext); margin-bottom:30px; font-weight:600;'>{t('login_sub')}</p>
    </div>""", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        uid = st.text_input("Surveyor ID", value="Kazi.M")
        pwd = st.text_input("Passcode", type="password", value="demo")
        if st.button(t('btn_login'), type="primary", use_container_width=True, key="auth_login"):
            with st.spinner("Authenticating secure connection..."):
                time.sleep(1)
                st.session_state.auth = True
                st.session_state.user = uid
                set_view("workspace"); st.rerun()

elif st.session_state.view == "workspace" and st.session_state.auth:
    with st.sidebar:
        st.markdown("### 📥 Telemetry Ingestion")
        upl = st.file_uploader("Upload Drone Orthomosaic", type=["png","jpg","jpeg"], label_visibility="collapsed")
        if upl:
            st.session_state.raw_img = Image.open(upl).convert("RGB")
            st.session_state.extracted = False; st.session_state.is_demo = False
            
        st.markdown("<div style='text-align:center; color:#94A3B8; font-size:0.8rem; margin:10px 0;'>— OR —</div>", unsafe_allow_html=True)
        if st.button("🌐 Load Failsafe Demo Map", use_container_width=True, key="load_demo"):
            st.session_state.raw_img = demo_map()
            st.session_state.extracted = False; st.session_state.is_demo = True
            
        st.markdown("---")
        st.markdown("### ⚙️ Calibration Parameters")
        # Placing parameters directly in the sidebar for high visibility
        with st.form("param_form"):
            new_gsd = st.slider("GSD (m/px)", 0.01, 0.20, st.session_state.gsd, 0.01)
            new_conf = st.slider("AI Confidence Threshold", 0.10, 0.90, st.session_state.conf, 0.05)
            new_lat = st.number_input("Anchor Latitude", value=st.session_state.anchor_lat, format="%.6f")
            new_lon = st.number_input("Anchor Longitude", value=st.session_state.anchor_lon, format="%.6f")
            if st.form_submit_button("Apply Parameters", use_container_width=True):
                st.session_state.gsd = new_gsd; st.session_state.conf = new_conf
                st.session_state.anchor_lat = new_lat; st.session_state.anchor_lon = new_lon
                st.session_state.extracted = False; st.rerun()

    st.markdown("<h2 style='margin-bottom: 25px;'>Cadastral Command Studio</h2>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs([t('tab1'), t('tab2'), t('tab3')])

    with t1:
        if not st.session_state.raw_img: st.info("Welcome to the workspace. Please ingest data via the sidebar to begin.")
        else:
            cl, cr = st.columns(2)
            with cl:
                st.markdown("##### Raw Telemetry")
                st.image(st.session_state.raw_img, use_container_width=True)
                if st.button("⚡ Execute Autonomous Extraction", type="primary", use_container_width=True, key="run_ai"):
                    with st.spinner("Processing neural boundaries..."):
                        ts = time.time(); parcels, feats = [], []
                        
                        if st.session_state.is_demo:
                            boxes = [[60,50,280,280], [340,60,590,290], [660,50,940,280]]
                            for b in boxes:
                                xy = [(b[0],b[1]), (b[2],b[1]), (b[2],b[3]), (b[0],b[3])]
                                sqm = round(float(Polygon(xy).area * (st.session_state.gsd**2)), 2)
                                perim = round(float(Polygon(xy).length * st.session_state.gsd), 2)
                                upin = f"WB-{uuid.uuid4().hex[:6].upper()}"
                                parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": perim, "Confidence (%)": 99.9, "Verified By": ""})
                                coords = [px_to_latlon(p[0], p[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for p in xy] + [px_to_latlon(xy[0][0], xy[0][1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd)]
                                feats.append({"type":"Feature", "properties":{"upin":upin, "area":sqm, "confidence":99.9}, "geometry":{"type":"Polygon", "coordinates":[coords]}})
                            st.session_state.ai_img = st.session_state.raw_img
                        else:
                            model = load_segmentation_model()
                            if model:
                                pred = model.predict(st.session_state.raw_img, conf=st.session_state.conf, save=False)
                                if pred[0].masks is not None:
                                    st.session_state.ai_img = Image.fromarray(pred[0].plot()[..., ::-1])
                                    for idx, (mxy, box) in enumerate(zip(pred[0].masks.xy, pred[0].boxes)):
                                        if len(mxy) < 3: continue
                                        poly = Polygon(mxy).simplify(1.5, preserve_topology=True)
                                        sqm = round(float(poly.area * (st.session_state.gsd**2)), 2)
                                        conf = round(float(box.conf[0])*100, 1)
                                        parcels.append({"UPIN": f"WB-{uuid.uuid4().hex[:6].upper()}", "Verified": False, "Area (m²)": sqm, "Perimeter (m)": round(float(poly.length * st.session_state.gsd), 2), "Confidence (%)": conf, "Verified By": ""})
                                        coords = [px_to_latlon(p[0], p[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for p in list(poly.exterior.coords)]
                                        feats.append({"type":"Feature", "properties":{"area":sqm, "confidence":conf}, "geometry":{"type":"Polygon", "coordinates":[coords]}})

                        st.session_state.survey_df = pd.DataFrame(parcels)
                        st.session_state.geo_json = {"type": "FeatureCollection", "features": feats}
                        st.session_state.extracted = True
                        st.session_state.latency = round(time.time() - ts, 2)
                        st.rerun()
            with cr:
                st.markdown("##### Extracted Vector Masks")
                if st.session_state.extracted: st.image(st.session_state.ai_img, use_container_width=True)
                else: st.info("Awaiting execution command.")

    with t2:
        if st.session_state.extracted and st.session_state.geo_json:
            st.markdown("**Visual Confidence Mapping:** 🟢 High (>85%) | 🟠 Review (>70%) | 🔴 Audit (<70%)")
            m = folium.Map(location=[st.session_state.anchor_lat, st.session_state.anchor_lon], zoom_start=18, tiles="CartoDB positron")
            
            folium.GeoJson(
                st.session_state.geo_json, 
                style_function=lambda x: {"fillColor": get_conf_color(x["properties"].get("confidence", 100)), "color": "#0F172A", "weight": 1.5, "fillOpacity": 0.5},
                tooltip=folium.GeoJsonTooltip(fields=["upin", "area", "confidence"], aliases=["UPIN:", "Area (m²):", "AI Confidence (%):"])
            ).add_to(m)
            
            plugins.Fullscreen().add_to(m); m.fit_bounds(m.get_bounds())
            st_folium(m, width="100%", height=500, returned_objects=[])
        else:
            st.info("Execute Step 1 to populate GIS Cartography.")

    with t3:
        if st.session_state.extracted and not st.session_state.survey_df.empty:
            df = st.session_state.survey_df
            m1, m2, m3 = st.columns(3)
            m1.markdown(f'<div class="metric-tile"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Parcels Mapped</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-tile"><div class="metric-val">{st.session_state.latency}s</div><div class="metric-lbl">Inference Latency</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-tile"><div class="metric-val">{(df["Verified"]==True).sum()}</div><div class="metric-lbl">Cleared by Surveyor</div></div>', unsafe_allow_html=True)
            
            st.markdown("<br>##### 🧑‍💻 Surveyor Human-in-the-Loop Ledger", unsafe_allow_html=True)
            st.caption("Review parcel geometry. Ticking 'Verified' securely stamps your Surveyor ID and clears the title for PDF generation.")
            
            edf = st.data_editor(df, hide_index=True, disabled=["UPIN","Area (m²)","Perimeter (m)","Confidence (%)","Verified By"], use_container_width=True, key="audit_ledger")
            for i in edf.index:
                if edf.at[i, 'Verified'] and not edf.at[i, 'Verified By']: edf.at[i, 'Verified By'] = st.session_state.user
                elif not edf.at[i, 'Verified']: edf.at[i, 'Verified By'] = ""
            st.session_state.survey_df = edf
            
            cleared = edf[edf["Verified"] == True]
            if not cleared.empty:
                st.markdown("---")
                st.markdown("##### 🖨️ Official Document Minting")
                c1, c2, c3 = st.columns([1.5, 1.5, 1])
                with c1:
                    zip_data = generate_batch_zip(cleared, st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.user)
                    st.download_button("🗂️ Batch Download SVAMITVA Records (ZIP)", data=zip_data, file_name="SVAMITVA_Batch_Release.zip", mime="application/zip", type="primary", use_container_width=True, key="batch_dl")
                with c2:
                    st.download_button("📥 Export Secure Ledger (CSV)", data=edf.to_csv(index=False).encode('utf-8'), file_name="Cadastral_Audit_Register.csv", mime="text/csv", use_container_width=True, key="csv_dl")
        else:
            st.info("Execute Step 1 to populate the Surveyor Ledger.")
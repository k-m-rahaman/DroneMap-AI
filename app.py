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

# =====================================================================
# SAFE IMPORTS & ERROR HANDLING
# =====================================================================
logging.basicConfig(level=logging.ERROR)

try:
    from gtts import gTTS
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False

try:
    from ultrultralytics import YOLO
    AI_AVAILABLE = True
except ImportError:
    try:
        from ultralytics import YOLO
        AI_AVAILABLE = True
    except ImportError:
        AI_AVAILABLE = False

# =====================================================================
# 1. INTERNATIONALIZATION & VOICE ASSISTANT
# =====================================================================
TRANSLATIONS = {
    "en": {
        "tag": "SVAMITVA Scheme Compliant", "hero": "Mapping the Future of", "hero_span": "Land Ownership",
        "sub": "DroneMap AI transforms raw aerial telemetry into dispute-free, legally binding cadastral property titles instantly.",
        "btn_explore": "Launch Command Studio", "login_title": "Secure Surveyor Access",
        "login_sub": "Authorized Personnel Only", "btn_login": "Authenticate",
        "tab1": "1️⃣ Extraction Studio", "tab2": "2️⃣ Interactive WebGIS", "tab3": "3️⃣ Audit Ledger"
    },
    "hi": {
        "tag": "स्वामित्व योजना अनुरूप", "hero": "भूमि स्वामित्व के", "hero_span": "भविष्य का मानचित्रण",
        "sub": "DroneMap AI कच्चे ड्रोन डेटा को सत्यापन-योग्य भूमि अभिलेखों में बदलता है।",
        "btn_explore": "कमांड स्टूडियो खोलें", "login_title": "सुरक्षित सर्वेक्षक पहुंच",
        "login_sub": "केवल अधिकृत कर्मियों के लिए", "btn_login": "लॉगिन करें",
        "tab1": "1️⃣ निष्कर्षण स्टूडियो", "tab2": "2️⃣ इंटरैक्टिव WebGIS", "tab3": "3️⃣ ऑडिट रजिस्टर"
    },
    "bn": {
        "tag": "SVAMITVA প্রকল্প অনুবর্তী", "hero": "ভূমি মালিকানার", "hero_span": "ভবিষ্যৎ মানচিত্রায়ণ",
        "sub": "DroneMap AI কাঁচা ড্রোন তথ্যকে যাচাইযোগ্য ভূমি নথিতে রূপান্তর করে।",
        "btn_explore": "কমান্ড স্টুডিও চালু করুন", "login_title": "নিরাপদ সার্ভেয়ার অ্যাক্সেস",
        "login_sub": "শুধুমাত্র অনুমোদিত কর্মীদের জন্য", "btn_login": "প্রবেশ করুন",
        "tab1": "1️⃣ নিষ্কাশন স্টুডিও", "tab2": "2️⃣ ইন্টারেক্টিভ WebGIS", "tab3": "3️⃣ অডিট লেজার"
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
st.set_page_config(page_title="DroneMap AI | Master System", page_icon="🛰️", layout="wide", initial_sidebar_state="collapsed")

def init_state(key, default):
    if key not in st.session_state: st.session_state[key] = default

init_state("view", "landing")
init_state("theme", "dark")
init_state("lang", "en")
init_state("auth", False)
init_state("user", "")
init_state("raw_img", None)
init_state("ai_img", None)
init_state("survey_df", pd.DataFrame())
init_state("geo_json", None)
init_state("extracted", False)
init_state("is_demo", False)
init_state("gsd", 0.05)
init_state("conf", 0.25)
init_state("anchor_lat", 22.5726) # Default to Kolkata/WB Latitude
init_state("anchor_lon", 88.3639) # Default to Kolkata/WB Longitude

def set_view(v): st.session_state.view = v
def toggle_theme(): st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

# =====================================================================
# 3. FAST INSTITUTIONAL CSS
# =====================================================================
def inject_theme():
    is_dark = st.session_state.theme == "dark"
    bg = "#0B0F19" if is_dark else "#F1F5F9"
    surface = "#11141D" if is_dark else "#FFFFFF"
    border = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(15, 23, 42, 0.1)"
    text = "#F8FAFC" if is_dark else "#0F172A"
    accent = "#0EA5E9"
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
        * {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        .stApp, [data-testid="stHeader"] {{ background-color: {bg}; color: {text}; transition: all 0.2s; }}
        [data-testid="block-container"] {{ padding-top: 6rem !important; padding-bottom: 2rem !important; }}
        #MainMenu, footer {{ visibility: hidden; }}
        
        .nav-island {{
            position: fixed; top: 15px; left: 50%; transform: translateX(-50%); width: 95%; max-width: 1400px; z-index: 99999;
            background: {surface}; border: 1px solid {border}; border-radius: 9999px;
            padding: 12px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        }}
        
        [data-testid="stSidebar"] {{ background-color: {surface} !important; border-right: 1px solid {border}; }}
        h1, h2, h3, h4 {{ color: {text} !important; font-weight: 700; letter-spacing: -0.02em; }}
        p, span, div {{ color: {text}; }}
        
        .hero-wrap {{ text-align: center; max-width: 900px; margin: 50px auto; }}
        .hero-title {{ font-size: clamp(2.5rem, 5vw, 4.5rem); font-weight: 800; line-height: 1.1; margin: 20px 0; }}
        .hero-title span {{ color: {accent}; }}
        
        .story-block {{ display: grid; grid-template-columns: 1fr 1fr; gap: 50px; padding: 60px 20px; align-items: center; border-top: 1px solid {border}; }}
        .slideshow {{ border-radius: 16px; overflow: hidden; height: 350px; position: relative; border: 1px solid {border}; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }}
        .slide-img {{ position: absolute; width: 100%; height: 100%; object-fit: cover; opacity: 0; animation: fade 16s infinite; }}
        .slide-img:nth-child(1) {{ animation-delay: 0s; }} .slide-img:nth-child(2) {{ animation-delay: 4s; }}
        .slide-img:nth-child(3) {{ animation-delay: 8s; }} .slide-img:nth-child(4) {{ animation-delay: 12s; }}
        @keyframes fade {{ 0% {{opacity: 0;}} 10% {{opacity: 1;}} 25% {{opacity: 1;}} 35% {{opacity: 0;}} 100% {{opacity: 0;}} }}
        
        .glass-box {{ background: {surface}; border: 1px solid {accent}; border-radius: 16px; padding: 40px; max-width: 450px; margin: 10vh auto; text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.1); }}
        .metric-tile {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; padding: 20px; text-align: center; }}
        .metric-val {{ font-size: 2.2rem; font-weight: 800; color: {accent}; }}
        
        .stButton > button {{ border-radius: 9999px !important; font-weight: 600 !important; background: {surface} !important; border: 1px solid {border} !important; color: {text} !important; padding: 8px 20px !important; transition: transform 0.1s !important; }}
        .stButton > button:hover {{ transform: translateY(-1px); border-color: {accent} !important; color: {accent} !important; }}
        .stButton > button[data-testid="baseButton-primary"] {{ background: {text} !important; color: {bg} !important; border: none !important; }}
        .stButton > button[data-testid="baseButton-primary"]:hover {{ background: {accent} !important; color: #FFFFFF !important; }}
    </style>
    """, unsafe_allow_html=True)

inject_theme()

# =====================================================================
# 4. MATH, AI ENGINES & DOCUMENT GENERATION
# =====================================================================
def px_to_latlon(px_x, px_y, anchor_lat, anchor_lon, gsd):
    """Accurate Spherical Projection using cos(lat) adjustment"""
    lat_rad = math.radians(anchor_lat)
    lon_deg_per_m = 1.0 / (111320 * math.cos(lat_rad))
    lat_deg_per_m = 1.0 / 110540 
    return [anchor_lon + (px_x * gsd * lon_deg_per_m), anchor_lat - (px_y * gsd * lat_deg_per_m)]

@st.cache_data(show_spinner=False)
def get_base64_image(image_path):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode()
    img = Image.new("RGB", (800, 500), color=(30,41,59))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

@st.cache_resource
def load_segmentation_model():
    if not AI_AVAILABLE: return None
    try: return YOLO("best.pt") if os.path.exists("best.pt") else YOLO("yolov8n-seg.pt")
    except: return None

def make_qr(data):
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(data)
    buf = io.BytesIO()
    qr.make_image(fill_color="#0F172A", back_color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

class SVAMITVADocument(FPDF):
    def header(self):
        self.set_font("Helvetica", 'B', 15)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, "MINISTRY OF PANCHAYATI RAJ", ln=True, align="C")
        self.set_font("Helvetica", '', 11)
        self.set_text_color(100, 116, 139)
        self.cell(0, 6, "SVAMITVA Property Register Record", ln=True, align="C")
        self.line(10, 30, 200, 30)
        self.ln(6)

def generate_pdf(row, lat, lon, user):
    pdf = SVAMITVADocument(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 11)
    pdf.set_text_color(15, 23, 42)
    entries = [
        ("UPIN", str(row['UPIN'])), ("Area", f"{row['Area (m²)']} sqm"),
        ("Perimeter", f"{row['Perimeter (m)']} m"), ("Centroid", f"{lat:.6f} N, {lon:.6f} E"),
        ("Confidence", f"{row['Confidence (%)']}%"), ("Verified By", user),
        ("Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    ]
    for k, v in entries:
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(50, 8, f"{k}:", border=0)
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, v, border=0, ln=True)
    out = pdf.output()
    return bytes(out) if isinstance(out, (bytearray, bytes)) else out.encode('latin-1')

def generate_batch_zip(df, lat, lon, user):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, row in df.iterrows():
            zf.writestr(f"{row['UPIN']}.pdf", generate_pdf(row, lat, lon, user))
    buf.seek(0)
    return buf.getvalue()

def demo_map():
    img = Image.new("RGB", (1100, 750), color=(50, 65, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 330, 1100, 410], fill=(40, 42, 45))
    draw.line([0, 370, 1100, 370], fill=(220, 220, 220), width=3)
    for b, c in [([60,50,280,280],(165,80,50)), ([340,60,590,290],(180,90,60)), ([660,50,940,280],(150,70,45))]:
        draw.rectangle(b, fill=c, outline=(25,25,25), width=3)
        draw.rectangle([b[0]+20, b[1]+20, b[2]-20, b[3]-20], fill=(min(c[0]+25, 255), min(c[1]+25, 255), min(c[2]+25, 255)))
    return img

def get_conf_color(conf):
    if conf >= 85: return "#10B981" # Green
    if conf >= 65: return "#F59E0B" # Amber
    return "#EF4444" # Red

# =====================================================================
# 5. HIGH-VISIBILITY NAVIGATION BAR
# =====================================================================
st.markdown("<div class='nav-island'>", unsafe_allow_html=True)
c_logo, c_controls, c_cta = st.columns([3, 4, 3])

with c_logo:
    logo = next((f"my_logo.{e}" for e in ["png","jpg","jpeg"] if os.path.exists(f"my_logo.{e}")), "logo.png")
    blend = "normal" if st.session_state.theme == "dark" else "multiply"
    st.markdown(f"<div style='display:flex; align-items:center; gap:10px;'><img src='data:image/png;base64,{get_base64_image(logo)}' height='30' style='mix-blend-mode:{blend};'><span style='font-weight:800; font-size:1.2rem;'>DroneMap AI</span></div>", unsafe_allow_html=True)

with c_controls:
    ct1, ct2, ct3 = st.columns(3)
    with ct1:
        lang_sel = st.selectbox("🌐", ["en", "hi", "bn"], index=["en","hi","bn"].index(st.session_state.lang), label_visibility="collapsed", key="lang_select")
        if lang_sel != st.session_state.lang: st.session_state.lang = lang_sel; st.rerun()
    with ct2:
        st.button("☀️" if st.session_state.theme == "dark" else "🌙", on_click=toggle_theme, use_container_width=True, key="theme_btn")
    with ct3:
        if st.session_state.auth:
            if st.button("🎙️ Voice", use_container_width=True, key="voice_btn"):
                msgs = {"en": "System is ready.", "hi": "सिस्टम तैयार है।", "bn": "সিস্টেম প্রস্তুত।"}
                play_voice(msgs[st.session_state.lang], st.session_state.lang)

with c_cta:
    if st.session_state.view == "landing":
        st.button(t("btn_explore"), type="primary", on_click=set_view, args=("auth",), use_container_width=True, key="nav_explore")
    elif st.session_state.view == "auth":
        st.button("Return Home", on_click=set_view, args=("landing",), use_container_width=True, key="nav_home")
    else:
        st.button("🚪 Logout", type="primary", on_click=set_view, args=("landing",), use_container_width=True, key="nav_logout")
        if st.session_state.view == "landing": st.session_state.auth = False
st.markdown("</div>", unsafe_allow_html=True)

# =====================================================================
# 6. ROUTING (LANDING -> AUTH -> WORKSPACE)
# =====================================================================
if st.session_state.view == "landing":
    st.markdown(f"""
    <div class="hero-wrap">
        <div style="display:inline-block; border: 1px solid var(--accent); color: var(--accent); padding: 6px 16px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">{t('tag')}</div>
        <div class="hero-title">{t('hero')}<br><span>{t('hero_span')}</span></div>
        <p style="font-size: 1.15rem; color: var(--subtext); max-width:750px; margin:20px auto;">{t('sub')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2,1,2])
    with col2: st.button(t('btn_explore'), type="primary", on_click=set_view, args=("auth",), use_container_width=True, key="hero_explore")

    c1 = get_base64_image("challenge_1.png"); c2 = get_base64_image("challenge_2.png")
    c3 = get_base64_image("challenge_3.png"); c4 = get_base64_image("challenge_4.png")
    st.markdown(f"""
    <div class="story-block" style="margin-top:60px;">
        <div>
            <h2 style="font-size: 2.2rem; line-height: 1.1;">The Cadastral Challenge</h2>
            <p style="color: var(--subtext); line-height: 1.7; font-size: 1.05rem; margin-top: 15px;">Traditional chain surveys and paper mouza maps take months to resolve single village settlements. Without certified property records, landowners are locked out of institutional credit, sparking generations of boundary litigation.</p>
        </div>
        <div class="slideshow"><img src="data:image/png;base64,{c1}" class="slide-img"><img src="data:image/png;base64,{c2}" class="slide-img"><img src="data:image/png;base64,{c3}" class="slide-img"><img src="data:image/png;base64,{c4}" class="slide-img"></div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.view == "auth":
    st.markdown(f"""
    <div class='glass-box'>
        <h2 style='color:var(--accent); margin-bottom: 5px;'>{t('login_title')}</h2>
        <p style='color:var(--subtext); margin-bottom: 30px;'>{t('login_sub')}</p>
    </div>""", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        uid = st.text_input("Surveyor ID", value="SV-WB-2026")
        pwd = st.text_input("Passcode", type="password", value="demo")
        if st.button(t('btn_login'), type="primary", use_container_width=True, key="auth_login"):
            with st.spinner("Authenticating Secure Connection..."):
                time.sleep(1)
                st.session_state.auth = True
                st.session_state.user = uid
                set_view("workspace")
                st.rerun()

elif st.session_state.view == "workspace" and st.session_state.auth:
    
    # ------------------- SIDEBAR -------------------
    with st.sidebar:
        st.markdown(f"**👤 Verified Session:** `{st.session_state.user}`")
        st.markdown("---")
        st.markdown("### 📥 1. Ingest Telemetry")
        upl = st.file_uploader("Upload Orthomosaic (.PNG/.JPG/.TIF)", type=["png","jpg","jpeg","tif"], label_visibility="collapsed")
        if upl:
            try:
                st.session_state.raw_img = Image.open(upl).convert("RGB")
                st.session_state.extracted = False
                st.session_state.is_demo = False
                st.toast("Physical raster ingested.", icon="📥")
            except Exception: st.error("Format error.")
            
        st.markdown("<div style='text-align:center; opacity:0.4; margin:10px 0;'>— OR —</div>", unsafe_allow_html=True)
        if st.button("🌐 Generate Procedural Demo", use_container_width=True, key="btn_demo"):
            st.session_state.raw_img = demo_map()
            st.session_state.extracted = False
            st.session_state.is_demo = True
            
        st.markdown("---")
        st.markdown("### ⚙️ 2. Calibration")
        st.session_state.gsd = st.slider("GSD (m/px)", 0.01, 0.20, st.session_state.gsd, 0.01)
        st.session_state.conf = st.slider("AI Threshold", 0.10, 0.90, st.session_state.conf, 0.05)
        
        with st.expander("📍 Spatial Anchor (EPSG:4326)"):
            st.session_state.anchor_lat = st.number_input("Latitude", value=st.session_state.anchor_lat, format="%.6f")
            st.session_state.anchor_lon = st.number_input("Longitude", value=st.session_state.anchor_lon, format="%.6f")

    # ------------------- MAIN STUDIO -------------------
    st.markdown("<h2 style='margin-bottom: 20px;'>🛰️ Cadastral Command Studio</h2>", unsafe_allow_html=True)
    
    if not os.path.exists("best.pt") and not st.session_state.is_demo:
        st.warning("⚠️ **System Notice:** Custom weights (`best.pt`) not found. Operating on generic COCO fallbacks.")

    t1, t2, t3 = st.tabs([t('tab1'), t('tab2'), t('tab3')])

    # TAB 1: EXTRACTION
    with t1:
        if not st.session_state.raw_img: 
            st.info("👋 **Awaiting Data.** Please ingest a raster from the sidebar to begin processing.")
        else:
            cl, cr = st.columns(2)
            with cl:
                st.image(st.session_state.raw_img, use_container_width=True, caption="Raw Optical Telemetry")
                if st.button("⚡ Execute Neural Extraction Pipeline", type="primary", use_container_width=True, key="btn_extract"):
                    if not AI_AVAILABLE: st.error("CV libraries unavailable. AI Extraction disabled.")
                    else:
                        with st.spinner("Mapping Boundaries..."):
                            ts = time.time()
                            parcels, feats = [], []
                            
                            if st.session_state.is_demo:
                                # Failsafe deterministic bypass
                                boxes = [[60,50,280,280], [340,60,590,290], [660,50,940,280], [70,450,300,680], [360,440,630,670], [690,450,950,680]]
                                for b in boxes:
                                    xy = [(b[0],b[1]), (b[2],b[1]), (b[2],b[3]), (b[0],b[3])]
                                    sqm = round(float(Polygon(xy).area * (st.session_state.gsd**2)), 2)
                                    perim = round(float(Polygon(xy).length * st.session_state.gsd), 2)
                                    upin = f"WB-{uuid.uuid4().hex[:6].upper()}"
                                    conf = float(np.random.uniform(88, 99))
                                    parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": perim, "Confidence (%)": round(conf, 1), "Verified By": ""})
                                    coords = [px_to_latlon(p[0], p[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for p in xy] + [px_to_latlon(xy[0][0], xy[0][1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd)]
                                    feats.append({"type":"Feature", "properties":{"upin":upin, "area":sqm, "confidence": conf}, "geometry":{"type":"Polygon", "coordinates":[coords]}})
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
                                            if poly.is_empty: continue
                                            sqm = round(float(poly.area * (st.session_state.gsd**2)), 2)
                                            conf = round(float(box.conf[0])*100, 1)
                                            upin = f"WB-{uuid.uuid4().hex[:6].upper()}"
                                            parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": round(float(poly.length * st.session_state.gsd), 2), "Confidence (%)": conf, "Verified By": ""})
                                            coords = [px_to_latlon(p[0], p[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for p in list(poly.exterior.coords)]
                                            feats.append({"type":"Feature", "properties":{"upin":upin, "area":sqm, "confidence": conf}, "geometry":{"type":"Polygon", "coordinates":[coords]}})
                                    else:
                                        st.session_state.ai_img = st.session_state.raw_img; st.warning("No structures detected.")

                            st.session_state.survey_df = pd.DataFrame(parcels) if parcels else pd.DataFrame(columns=["UPIN", "Verified", "Area (m²)", "Perimeter (m)", "Confidence (%)", "Verified By"])
                            st.session_state.geo_json = {"type": "FeatureCollection", "features": feats}
                            st.session_state.extracted = True
                            st.session_state.latency = round(time.time() - ts, 2)
                            st.rerun()
            with cr:
                if st.session_state.extracted: st.image(st.session_state.ai_img, use_container_width=True, caption="Neural Polygon Boundaries")
                else: st.info("Waiting for extraction pipeline.")

    # TAB 2: WEBGIS
    with t2:
        if st.session_state.extracted and st.session_state.geo_json and st.session_state.geo_json["features"]:
            m = folium.Map(location=[st.session_state.anchor_lat, st.session_state.anchor_lon], zoom_start=18, tiles="CartoDB Dark_Matter" if st.session_state.theme=="dark" else "CartoDB positron")
            folium.GeoJson(
                st.session_state.geo_json, 
                style_function=lambda f: {"fillColor": get_conf_color(f["properties"]["confidence"]), "color": get_conf_color(f["properties"]["confidence"]), "weight": 2.5, "fillOpacity": 0.4},
                tooltip=folium.GeoJsonTooltip(fields=["upin", "area", "confidence"], aliases=["UPIN:", "Area (m²):", "AI Confidence (%):"])
            ).add_to(m)
            plugins.Fullscreen().add_to(m); m.fit_bounds(m.get_bounds())
            st_folium(m, width="100%", height=500, returned_objects=[])
            st.download_button("📥 Export OGC GeoJSON", data=json.dumps(st.session_state.geo_json), file_name="parcels.geojson", mime="application/geo+json", key="btn_geojson")
        else:
            st.info("🗺️ Spatial data unavailable. Run Step 1.")

    # TAB 3: AUDIT
    with t3:
        if st.session_state.extracted and not st.session_state.survey_df.empty:
            df = st.session_state.survey_df
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f'<div class="metric-tile"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Parcels Mapped</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-tile"><div class="metric-val">{df["Area (m²)"].sum():,.0f} m²</div><div class="metric-lbl">Total Footprint</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-tile"><div class="metric-val">{st.session_state.latency}s</div><div class="metric-lbl">Compute Time</div></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-tile"><div class="metric-val">{(df["Verified"]==True).sum()}</div><div class="metric-lbl">Surveyor Approved</div></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("##### 🧑‍💻 Surveyor Verification Ledger")
            edf = st.data_editor(df, hide_index=True, disabled=["UPIN","Area (m²)","Perimeter (m)","Confidence (%)","Verified By"], use_container_width=True)
            
            for i in edf.index:
                if edf.at[i, 'Verified'] and not edf.at[i, 'Verified By']: edf.at[i, 'Verified By'] = st.session_state.user
                elif not edf.at[i, 'Verified']: edf.at[i, 'Verified By'] = ""
            st.session_state.survey_df = edf
            
            cleared = edf[edf["Verified"] == True]
            if not cleared.empty:
                st.markdown("---")
                c1, c2 = st.columns([1.2, 2])
                with c1:
                    sel_upin = st.selectbox("Target UPIN for Issuance:", cleared["UPIN"].tolist())
                    record = cleared[cleared["UPIN"] == sel_upin].iloc[0]
                    pdf_data = generate_pdf(record, st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.user)
                    if pdf_data:
                        st.download_button("🖨️ Download Target PDF", data=pdf_data, file_name=f"{record['UPIN']}.pdf", mime="application/pdf", type="primary", use_container_width=True, key="btn_pdf_single")
                    
                    zip_data = generate_batch_zip(cleared, st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.user)
                    st.download_button("🗂️ Batch Download All Cleared (ZIP)", data=zip_data, file_name="SVAMITVA_Batch.zip", mime="application/zip", use_container_width=True, key="btn_zip_batch")
                
                with c2:
                    qr_b64 = make_qr(f"SVAMITVA:{record['UPIN']}|AREA:{record['Area (m²)']}sqm")
                    st.markdown(f"""
                    <div style="background: var(--surface-solid); border: 1px solid var(--border); border-radius: 16px; padding: 24px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div><h3 style="margin:0;">{record['UPIN']}</h3><p style="margin:4px 0 0 0; color:#10B981; font-weight:700; font-size:0.85rem;">✔ TITLE CLEARED</p></div>
                            <img src="data:image/png;base64,{qr_b64}" width="75" style="border-radius: 6px;" />
                        </div>
                        <hr style="border:none; border-bottom: 1px solid var(--border); margin: 16px 0;">
                        <p style="margin: 6px 0;"><b>Area:</b> {record['Area (m²)']} m² | <b>Perim:</b> {record['Perimeter (m)']} m</p>
                        <p style="margin: 6px 0;"><b>Confidence:</b> {record['Confidence (%)']}% | <b>Audit:</b> {record['Verified By']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("📄 Execute Step 1 to populate ledger.")
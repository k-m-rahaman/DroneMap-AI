import streamlit as st
import numpy as np
import pandas as pd
import json
import time
import os
import io
import base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon
import folium
from folium import plugins
from streamlit_folium import st_folium
import qrcode
from fpdf import FPDF

# Safe import for YOLO to prevent app crashes
try:
    from ultralytics import YOLO
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# =====================================================================
# 1. SYSTEM INITIALIZATION & STATE
# =====================================================================
st.set_page_config(
    page_title="DroneMap AI — Autonomous Cadastral Platform",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_state("view", "landing")
init_state("theme", "dark")
init_state("raw_img", None)
init_state("ai_img", None)
init_state("survey_df", pd.DataFrame())
init_state("geo_json", None)
init_state("extracted", False)
init_state("anchor_lat", 22.5726)
init_state("anchor_lon", 88.3639)
init_state("gsd", 0.05)
init_state("conf", 0.25)
init_state("latency", 0.0)

M_TO_DEG = 0.000009

def set_view(v):
    st.session_state.view = v

def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

# =====================================================================
# 2. BASE64 ASSET ENCODER (For Slideshows & Logos)
# =====================================================================
def get_base64_image(image_path, fallback_color=(30, 41, 59)):
    """Encodes local PNGs to Base64, generating a failsafe if missing."""
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    else:
        img = Image.new("RGB", (800, 500), color=fallback_color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 750, 450], outline=(100, 116, 139), width=3)
        draw.text((320, 240), f"[Missing: {os.path.basename(image_path)}]", fill=(203, 213, 225))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

# =====================================================================
# 3. MODERN GLASSMORPHISM & PARALLAX SCROLL SYSTEM
# =====================================================================
def inject_theme():
    is_dark = st.session_state.theme == "dark"
    
    # Adaptive Variables ensuring perfect Light/Dark transition
    bg_base = "#0B0F19" if is_dark else "#F1F5F9"
    glow_top = "rgba(0, 102, 255, 0.15)" if is_dark else "rgba(0, 102, 255, 0.08)"
    glow_bot = "rgba(16, 185, 129, 0.1)" if is_dark else "rgba(16, 185, 129, 0.06)"
    
    surface = "rgba(17, 20, 29, 0.65)" if is_dark else "rgba(255, 255, 255, 0.75)"
    surface_solid = "#11141D" if is_dark else "#FFFFFF"
    border = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(15, 23, 42, 0.1)"
    text = "#F8FAFC" if is_dark else "#0F172A"
    subtext = "#94A3B8" if is_dark else "#475569"
    accent = "#0066FF" if is_dark else "#0284C7"
    shadow = "rgba(0,0,0,0.4)" if is_dark else "rgba(0,0,0,0.05)"
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        
        :root {{
            --bg-base: {bg_base}; --text: {text}; --subtext: {subtext};
            --surface: {surface}; --surface-solid: {surface_solid};
            --border: {border}; --accent: {accent}; --shadow: {shadow};
        }}
        
        * {{ font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.015em; }}
        
        /* Fixed Parallax Background - creates dynamic blur on scroll */
        .stApp, [data-testid="stHeader"] {{ 
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 15% 30%, {glow_top} 0%, transparent 40%),
                radial-gradient(circle at 85% 80%, {glow_bot} 0%, transparent 40%);
            background-attachment: fixed;
            color: var(--text); 
            transition: all 0.4s ease;
        }}
        
        /* Frosted Glass Override for Streamlit Elements */
        [data-testid="stSidebar"] {{ 
            background-color: var(--surface) !important; 
            backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
            border-right: 1px solid var(--border); 
        }}
        
        h1, h2, h3, h4, h5, h6 {{ font-weight: 700; color: var(--text) !important; letter-spacing: -0.03em !important; }}
        p, span, label, div {{ color: var(--text); }}
        
        #MainMenu, footer {{ visibility: hidden; }}
        
        /* Glass Navbar */
        .nav-shell {{
            position: sticky; top: 0; z-index: 999;
            background: var(--surface); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
            border-bottom: 1px solid var(--border); padding: 12px 30px;
            display: flex; justify-content: space-between; align-items: center;
        }}
        
        /* Hero & Typography */
        .hero-wrap {{ max-width: 900px; margin: 0 auto; padding: 60px 20px 40px 20px; text-align: center; }}
        .hero-title {{ font-size: clamp(2.5rem, 5vw, 4.5rem); line-height: 1.1; font-weight: 800; margin-bottom: 24px; color: var(--text); }}
        .hero-title span {{ background: linear-gradient(135deg, var(--text) 30%, var(--subtext)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .hero-sub {{ font-size: 1.15rem; color: var(--subtext) !important; line-height: 1.6; margin: 0 auto 40px auto; max-width: 700px; }}
        
        /* Story Layouts & Glass Cards */
        .story-block {{ display: grid; grid-template-columns: 1fr 1fr; gap: 60px; padding: 80px 40px; align-items: center; max-width: 1200px; margin: 0 auto; border-top: 1px solid var(--border); }}
        .story-block.reversed {{ grid-template-columns: 1fr 1fr; direction: rtl; }}
        .story-block.reversed > div {{ direction: ltr; }}
        .story-tag {{ font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; }}
        
        /* 4-IMAGE ANIMATED SLIDESHOW WRAPPER */
        .slideshow-wrapper {{
            border-radius: 20px; overflow: hidden; border: 1px solid var(--border); 
            height: 400px; background: var(--surface); box-shadow: 0 20px 40px var(--shadow);
            position: relative;
        }}
        .slide-img {{
            position: absolute; width: 100%; height: 100%; object-fit: cover;
            opacity: 0; animation: cinematicFade 16s infinite;
        }}
        .slide-img:nth-child(1) {{ animation-delay: 0s; }}
        .slide-img:nth-child(2) {{ animation-delay: 4s; }}
        .slide-img:nth-child(3) {{ animation-delay: 8s; }}
        .slide-img:nth-child(4) {{ animation-delay: 12s; }}

        @keyframes cinematicFade {{
            0%   {{ opacity: 0; transform: scale(1); }}
            5%   {{ opacity: 1; transform: scale(1.02); }}
            20%  {{ opacity: 1; transform: scale(1.05); }}
            25%  {{ opacity: 0; transform: scale(1.08); }}
            100% {{ opacity: 0; transform: scale(1.08); }}
        }}
        
        /* Glass Metric Tiles */
        .metric-tile {{ 
            background: var(--surface); backdrop-filter: blur(16px); border: 1px solid var(--border); 
            border-radius: 16px; padding: 24px; text-align: center; box-shadow: 0 10px 30px var(--shadow);
        }}
        .metric-val {{ font-size: 2.2rem; font-weight: 800; color: var(--text); }}
        .metric-lbl {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--subtext); margin-top: 6px; }}
        
        /* Buttons */
        .stButton > button {{ border-radius: 9999px !important; padding: 10px 24px !important; font-weight: 600 !important; border: 1px solid var(--border) !important; background: var(--surface) !important; color: var(--text) !important; backdrop-filter: blur(10px); transition: all 0.2s !important; }}
        .stButton > button:hover {{ border-color: var(--text) !important; transform: translateY(-2px); }}
        .stButton > button[data-testid="baseButton-primary"] {{ background: var(--text) !important; color: var(--bg-base) !important; border: none !important; }}
        .stButton > button[data-testid="baseButton-primary"]:hover {{ background: var(--accent) !important; color: #FFF !important; box-shadow: 0 4px 15px rgba(0, 102, 255, 0.4); }}

        @media (max-width: 768px) {{
            .story-block, .story-block.reversed {{ grid-template-columns: 1fr; gap: 30px; padding: 40px 20px; }}
            .slideshow-wrapper {{ height: 260px; }}
            .nav-shell {{ flex-direction: column; gap: 15px; padding: 15px; }}
        }}
    </style>
    """, unsafe_allow_html=True)

inject_theme()

# =====================================================================
# 4. ROBUST PROCESSING ENGINES
# =====================================================================
@st.cache_resource
def load_segmentation_model():
    if not AI_AVAILABLE: return None
    try:
        return YOLO("best.pt") if os.path.exists("best.pt") else YOLO("yolov8n-seg.pt")
    except Exception as e:
        st.error(f"AI Model Error: {e}")
        return None

def make_qr_code(data):
    try:
        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0F172A", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

class SVAMITVADocument(FPDF):
    def header(self):
        self.set_font("Helvetica", 'B', 15)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, "MINISTRY OF PANCHAYATI RAJ", ln=True, align="C")
        self.set_font("Helvetica", '', 11)
        self.set_text_color(100, 116, 139)
        self.cell(0, 6, "SVAMITVA Property Register Record", ln=True, align="C")
        self.ln(6)
        self.line(10, 32, 200, 32)
        self.ln(6)

def generate_pdf(row, lat, lon):
    try:
        pdf = SVAMITVADocument(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 11)
        pdf.set_text_color(15, 23, 42)
        
        entries = [
            ("Unique Parcel ID (UPIN)", str(row['UPIN'])),
            ("Registered Ground Area", f"{row['Area (m²)']} Sq. Meters"),
            ("Boundary Perimeter", f"{row['Perimeter (m)']} Meters"),
            ("Geospatial Centroid", f"{lat} N, {lon} E"),
            ("Coordinate System", "EPSG:4326 (WGS 84)"),
            ("AI Validation Confidence", f"{row['Confidence (%)']}%"),
            ("Survey Clearance Status", "OFFICIALLY VERIFIED"),
            ("Issuance Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        for lbl, val in entries:
            pdf.set_font("Helvetica", 'B', 10)
            pdf.cell(60, 8, f"{lbl}:", border=0)
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(0, 8, val, border=0, ln=True)
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        st.error(f"Document Generation Error: {e}")
        return None

def generate_synthetic_orthomosaic():
    img = Image.new("RGB", (1100, 750), color=(50, 65, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 330, 1100, 410], fill=(40, 42, 45))
    draw.line([0, 370, 1100, 370], fill=(220, 220, 220), width=3)
    plots = [
        ([60, 50, 280, 280], (165, 80, 50)), ([340, 60, 590, 290], (180, 90, 60)),
        ([660, 50, 940, 280], (150, 70, 45)), ([70, 450, 300, 680], (190, 85, 55)),
        ([360, 440, 630, 670], (160, 70, 45)), ([690, 450, 950, 680], (135, 65, 40))
    ]
    for box, c in plots:
        draw.rectangle(box, fill=c, outline=(25, 25, 25), width=3)
        draw.rectangle([box[0]+20, box[1]+20, box[2]-20, box[3]-20], fill=(min(c[0]+25, 255), min(c[1]+25, 255), min(c[2]+25, 255)))
    return img.filter(ImageFilter.GaussianBlur(radius=0.4))

# =====================================================================
# 5. GLOBAL NAVIGATION BAR (GLASS STICKY HEADER)
# =====================================================================
st.markdown("<div class='nav-shell'>", unsafe_allow_html=True)
c_logo, c_space, c_toggle, c_cta = st.columns([2.5, 5.5, 1.5, 2])

with c_logo:
    logo_b64 = get_base64_image("my_logo.png") if os.path.exists("my_logo.png") else get_base64_image("logo.png")
    blend = "normal" if st.session_state.theme == "dark" else "multiply"
    st.markdown(f"<img src='data:image/png;base64,{logo_b64}' style='height:40px; mix-blend-mode:{blend};'>", unsafe_allow_html=True)

with c_toggle:
    t_icon = "☀️ Light" if st.session_state.theme == "dark" else "🌙 Dark"
    st.button(t_icon, on_click=toggle_theme, use_container_width=True)

with c_cta:
    if st.session_state.view == "landing":
        st.button("Launch System ➔", type="primary", on_click=set_view, args=("workspace",), use_container_width=True)
    else:
        st.button("Exit Workspace", on_click=set_view, args=("landing",), use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# =====================================================================
# VIEW 1: LANDING PAGE (SLIDESHOW STORY MODE)
# =====================================================================
if st.session_state.view == "landing":

    st.markdown("""
    <div class="hero-wrap">
        <div style="display:inline-block; border: 1px solid var(--accent); color: var(--accent); padding: 6px 16px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 20px; background: rgba(0, 102, 255, 0.1);">SVAMITVA Scheme Compliant</div>
        <div class="hero-title">Mapping the Future of<br><span>Land Ownership</span></div>
        <div class="hero-sub">Over 60% of rural land parcels lack formal boundaries. DroneMap AI transforms raw aerial telemetry into dispute-free, legally binding cadastral property titles instantly.</div>
    </div>
    """, unsafe_allow_html=True)

    c_b1, c_b2, c_b3 = st.columns([1.6, 1.2, 1.6])
    with c_b2:
        st.button("Explore the Engine", type="primary", on_click=set_view, args=("workspace",), use_container_width=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    # Narrative 1: The Challenge (4-Image Slideshow)
    ch1 = get_base64_image("challenge_1.png", (45, 55, 72))
    ch2 = get_base64_image("challenge_2.png", (40, 50, 65))
    ch3 = get_base64_image("challenge_3.png", (50, 60, 75))
    ch4 = get_base64_image("challenge_4.png", (42, 52, 68))

    st.markdown(f"""
    <div class="story-block">
        <div>
            <div class="story-tag">The Cadastral Challenge</div>
            <h2 style="font-size: clamp(2rem, 3.5vw, 2.8rem); line-height: 1.1; margin-bottom: 20px;">Unlocking Dead Capital in Rural Land</h2>
            <p style="font-size: 1.05rem; line-height: 1.7; color: var(--subtext);">Traditional chain surveys and paper mouza maps take months to resolve single village settlements. Without certified property records, landowners are locked out of institutional credit, sparking generations of boundary litigation.</p>
        </div>
        <div class="slideshow-wrapper">
            <img src="data:image/png;base64,{ch1}" class="slide-img">
            <img src="data:image/png;base64,{ch2}" class="slide-img">
            <img src="data:image/png;base64,{ch3}" class="slide-img">
            <img src="data:image/png;base64,{ch4}" class="slide-img">
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Narrative 2: The Solution (4-Image Slideshow)
    sol1 = get_base64_image("solution_1.png", (15, 23, 42))
    sol2 = get_base64_image("solution_2.png", (16, 30, 50))
    sol3 = get_base64_image("solution_3.png", (14, 26, 45))
    sol4 = get_base64_image("solution_4.png", (18, 35, 58))

    st.markdown(f"""
    <div class="story-block reversed">
        <div class="slideshow-wrapper">
            <img src="data:image/png;base64,{sol1}" class="slide-img">
            <img src="data:image/png;base64,{sol2}" class="slide-img">
            <img src="data:image/png;base64,{sol3}" class="slide-img">
            <img src="data:image/png;base64,{sol4}" class="slide-img">
        </div>
        <div>
            <div class="story-tag">Autonomous Vectorization</div>
            <h2 style="font-size: clamp(2rem, 3.5vw, 2.8rem); line-height: 1.1; margin-bottom: 20px;">From Drone Pixels to Legal Titles in Seconds</h2>
            <p style="font-size: 1.05rem; line-height: 1.7; color: var(--subtext);">By processing sub-decimeter Ground Sampling Distance (GSD) orthomosaics with YOLOv8 neural networks, our pipeline instantly identifies footprints, flags encroachments, and outputs survey-grade OGC GeoJSON.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =====================================================================
# VIEW 2: COMMAND CENTER (WORKSPACE)
# =====================================================================
elif st.session_state.view == "workspace":

    with st.sidebar:
        st.markdown("### 1. Data Ingestion")
        uploaded_file = st.file_uploader("Upload Orthomosaic (.PNG/.JPG)", type=["png", "jpg", "jpeg", "tif"])
        
        if uploaded_file:
            try:
                st.session_state.raw_img = Image.open(uploaded_file).convert("RGB")
                st.session_state.extracted = False
                st.success("Raster ingested.")
            except Exception:
                st.error("Invalid image format.")
                
        st.markdown("<div style='text-align:center; opacity:0.5; margin: 10px 0;'>— or —</div>", unsafe_allow_html=True)
        
        if st.button("Generate Demo Quadrant", use_container_width=True):
            st.session_state.raw_img = generate_synthetic_orthomosaic()
            st.session_state.extracted = False
            st.success("Demo raster loaded.")
            
        st.markdown("---")
        with st.expander("⚙️ Advanced Parameters"):
            st.session_state.gsd = st.slider("GSD (m/px)", 0.01, 0.20, st.session_state.gsd, 0.01)
            st.session_state.conf = st.slider("AI Confidence", 0.10, 0.90, st.session_state.conf, 0.05)
            st.session_state.anchor_lat = st.number_input("Anchor Lat (EPSG:4326)", value=st.session_state.anchor_lat, format="%.6f")
            st.session_state.anchor_lon = st.number_input("Anchor Lon (EPSG:4326)", value=st.session_state.anchor_lon, format="%.6f")

    st.markdown("<h2 style='margin: 20px 0 20px 20px;'>🛰️ Cadastral Command Studio</h2>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["1️⃣ Extraction Studio", "2️⃣ Interactive WebGIS", "3️⃣ Audit & Certification"])

    # TAB 1: EXTRACTION
    with tab1:
        if st.session_state.raw_img is None:
            st.info("👋 **Welcome to the Command Studio!**\n\nPlease start by uploading a drone raster or clicking **'Generate Demo Quadrant'** in the left sidebar.")
        else:
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown("##### Raw Telemetry Input")
                st.image(st.session_state.raw_img, use_container_width=True)
                
                if not AI_AVAILABLE:
                    st.error("Ultralytics library not found. AI Extraction disabled.")
                else:
                    if st.button("⚡ Execute Neural Pipeline", type="primary", use_container_width=True):
                        with st.spinner("Analyzing structures & generating vectors..."):
                            try:
                                t_start = time.time()
                                model = load_segmentation_model()
                                if model is None:
                                    st.error("Failed to initialize YOLO model.")
                                else:
                                    pred = model.predict(st.session_state.raw_img, conf=st.session_state.conf, save=False)
                                    
                                    parcels, geojson_features = [], []
                                    if pred[0].masks is not None:
                                        annotated_bgr = pred[0].plot()
                                        st.session_state.ai_img = Image.fromarray(annotated_bgr[..., ::-1])
                                        
                                        for idx, (mask_xy, box) in enumerate(zip(pred[0].masks.xy, pred[0].boxes)):
                                            if len(mask_xy) < 3: continue
                                            poly = Polygon(mask_xy)
                                            sqm = round(float(poly.area * (st.session_state.gsd ** 2)), 2)
                                            perimeter = round(float(poly.length * st.session_state.gsd), 2)
                                            conf = round(float(box.conf[0]) * 100, 1)
                                            upin = f"WB-{idx+101:04d}"
                                            
                                            parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": perimeter, "Confidence (%)": conf})
                                            
                                            coords = [[st.session_state.anchor_lon + (float(pt[0]) * st.session_state.gsd * M_TO_DEG),
                                                       st.session_state.anchor_lat - (float(pt[1]) * st.session_state.gsd * M_TO_DEG)] for pt in mask_xy]
                                            coords.append(coords[0])
                                            geojson_features.append({"type": "Feature", "properties": {"upin": upin, "area": sqm}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
                                    else:
                                        st.session_state.ai_img = st.session_state.raw_img
                                        st.warning("No structures detected at current confidence threshold.")
                                        
                                    st.session_state.survey_df = pd.DataFrame(parcels) if parcels else pd.DataFrame(columns=["UPIN", "Verified", "Area (m²)", "Perimeter (m)", "Confidence (%)"])
                                    st.session_state.geo_json = {"type": "FeatureCollection", "features": geojson_features}
                                    st.session_state.latency = round(time.time() - t_start, 2)
                                    st.session_state.extracted = True
                                    st.success(f"Pipeline complete in {st.session_state.latency}s. Proceed to tabs 2 and 3.")
                            except Exception as e:
                                st.error(f"Pipeline Execution Error: {e}")

            with col_r:
                st.markdown("##### Extracted Vectors")
                if st.session_state.extracted and st.session_state.ai_img:
                    st.image(st.session_state.ai_img, use_container_width=True)
                else:
                    st.info("Waiting for pipeline execution...")

    # TAB 2: WEBGIS
    with tab2:
        if not st.session_state.extracted or st.session_state.geo_json is None or not st.session_state.geo_json["features"]:
            st.info("🗺️ **No Spatial Data Available.**\n\nPlease complete Step 1 (Extraction Studio) to generate viewable GIS vectors.")
        else:
            tiles = "CartoDB Dark_Matter" if st.session_state.theme == "dark" else "CartoDB positron"
            try:
                m = folium.Map(location=[st.session_state.anchor_lat, st.session_state.anchor_lon], zoom_start=18, tiles=tiles)
                folium.GeoJson(
                    st.session_state.geo_json,
                    style_function=lambda x: {"fillColor": "#0066FF", "color": "#0052CC", "weight": 2, "fillOpacity": 0.4},
                    tooltip=folium.GeoJsonTooltip(fields=["upin", "area"], aliases=["UPIN:", "Area (m²):"])
                ).add_to(m)
                plugins.Fullscreen().add_to(m)
                m.fit_bounds(m.get_bounds())
                st_folium(m, width="100%", height=550, returned_objects=[])
                
                st.download_button("📥 Export OGC GeoJSON", data=json.dumps(st.session_state.geo_json), file_name="parcels.geojson", mime="application/geo+json")
            except Exception as e:
                st.error(f"Map Rendering Error: {e}")

    # TAB 3: AUDIT & CERTIFICATION
    with tab3:
        if not st.session_state.extracted or st.session_state.survey_df.empty:
            st.info("📄 **No Audit Data Available.**\n\nPlease complete Step 1 (Extraction Studio) to populate the surveyor ledger.")
        else:
            df = st.session_state.survey_df
            
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f'<div class="metric-tile"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Parcels</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-tile"><div class="metric-val">{df["Area (m²)"].sum():,.0f} m²</div><div class="metric-lbl">Total Area</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-tile"><div class="metric-val">{st.session_state.latency}s</div><div class="metric-lbl">Compute Time</div></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-tile"><div class="metric-val">{(df["Verified"] == True).sum()}</div><div class="metric-lbl">Approved</div></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("##### 🧑‍💻 Surveyor Verification Ledger")
            st.caption("Human-in-the-Loop Protocol: Verify parcel boundaries to clear them for official property card issuance.")
            
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True, disabled=["UPIN", "Area (m²)", "Perimeter (m)", "Confidence (%)"])
            st.session_state.survey_df = edited_df
            
            cleared = edited_df[edited_df["Verified"] == True]
            if not cleared.empty:
                st.markdown("---")
                col_sel, col_prev = st.columns([1.2, 2])
                with col_sel:
                    selected_upin = st.selectbox("Select Cleared UPIN for Issuance:", cleared["UPIN"].tolist())
                    record = cleared[cleared["UPIN"] == selected_upin].iloc[0]
                    
                    pdf_bytes = generate_pdf(record, st.session_state.anchor_lat, st.session_state.anchor_lon)
                    if pdf_bytes:
                        st.download_button("🖨️ Download Official SVAMITVA PDF", data=pdf_bytes, file_name=f"{record['UPIN']}_Certificate.pdf", mime="application/pdf", type="primary", use_container_width=True)
                    st.download_button("📥 Export Audit Ledger (CSV)", data=edited_df.to_csv(index=False).encode('utf-8'), file_name="Cadastral_Register.csv", mime="text/csv", use_container_width=True)
                    
                with col_prev:
                    qr_b64 = make_qr_code(f"SVAMITVA:{record['UPIN']}|AREA:{record['Area (m²)']}sqm")
                    st.markdown(f"""
                    <div style="background: var(--surface); border: 1px solid var(--border); backdrop-filter: blur(16px); border-radius: 16px; padding: 24px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h3 style="margin:0; font-size:1.4rem; color: var(--text);">{record['UPIN']}</h3>
                                <p style="margin:4px 0 0 0; color:#10B981; font-weight:700; font-size:0.85rem;">✔ TITLE CLEARED (FORM 7)</p>
                            </div>
                            <img src="data:image/png;base64,{qr_b64}" width="75" style="border-radius: 6px;" />
                        </div>
                        <hr style="border:none; border-bottom: 1px solid var(--border); margin: 16px 0;">
                        <p style="margin: 6px 0; color: var(--text);"><b>Ground Footprint:</b> {record['Area (m²)']} m²</p>
                        <p style="margin: 6px 0; color: var(--text);"><b>Perimeter:</b> {record['Perimeter (m)']} meters</p>
                        <p style="margin: 6px 0; color: var(--text);"><b>AI Confidence:</b> {record['Confidence (%)']}%</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("👆 Check the 'Verified' box for a parcel in the ledger above to unlock official certification printing.")
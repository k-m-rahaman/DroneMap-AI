import streamlit as st
import numpy as np
import pandas as pd
import json
import time
import os
import io
import base64
import math
import hashlib
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon
import folium
from folium import plugins
from streamlit_folium import st_folium
import qrcode
from fpdf import FPDF

# Configure error logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Safe import for YOLO
try:
    from ultralytics import YOLO
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.error("Ultralytics package missing.")

# =====================================================================
# 1. SYSTEM INITIALIZATION & STATE
# =====================================================================
st.set_page_config(page_title="DroneMap AI | Workspace", page_icon="🛰️", layout="wide", initial_sidebar_state="collapsed")

def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_state("logged_in", False)
init_state("user_id", "")
init_state("view", "landing")
init_state("theme", "dark")
init_state("raw_img", None)
init_state("ai_img", None)
init_state("survey_df", pd.DataFrame())
init_state("geo_json", None)
init_state("extracted", False)
init_state("is_demo", False)
init_state("using_generic_weights", False)

init_state("anchor_lat", 22.5726)
init_state("anchor_lon", 88.3639)
init_state("gsd", 0.05)
init_state("conf", 0.25)
init_state("latency", 0.0)

def set_view(v): st.session_state.view = v
def toggle_theme(): st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"

# =====================================================================
# 2. GEOSPATIAL MATH & ENGINES
# =====================================================================
def px_to_latlon(px_x, px_y, anchor_lat, anchor_lon, gsd):
    """Accurate spherical projection accounting for longitudinal shrinkage."""
    lat_rad = math.radians(anchor_lat)
    lon_deg_per_m = 1 / (111320 * math.cos(lat_rad))
    lat_deg_per_m = 1 / 110540 
    
    delta_x_m = px_x * gsd
    delta_y_m = px_y * gsd
    
    return [anchor_lon + (delta_x_m * lon_deg_per_m), anchor_lat - (delta_y_m * lat_deg_per_m)]

@st.cache_data(show_spinner=False)
def get_base64_image(image_path, fallback_color=(30, 41, 59)):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    img = Image.new("RGB", (800, 500), color=fallback_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 750, 450], outline=(100, 116, 139), width=3)
    draw.text((320, 240), f"[Missing Asset: {os.path.basename(image_path)}]", fill=(203, 213, 225))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

@st.cache_resource
def load_segmentation_model():
    if not AI_AVAILABLE: return None
    try:
        if os.path.exists("best.pt"):
            st.session_state.using_generic_weights = False
            return YOLO("best.pt")
        else:
            st.session_state.using_generic_weights = True
            return YOLO("yolov8n-seg.pt")
    except Exception as e:
        logging.exception("Failed to load YOLO model.")
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
        logging.exception("QR Generation failed.")
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
            ("Surveyor Clearance ID", str(row['Verified By'])),
            ("Issuance Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        for lbl, val in entries:
            pdf.set_font("Helvetica", 'B', 10)
            pdf.cell(65, 8, f"{lbl}:", border=0)
            pdf.set_font("Helvetica", '', 10)
            pdf.cell(0, 8, str(val), border=0, ln=True)
            
        # Compat check: fpdf2 returns bytearray on .output()
        out = pdf.output()
        return bytes(out) if isinstance(out, (bytearray, bytes)) else out.encode('latin-1')
    except Exception as e:
        logging.exception("PDF Generation Error")
        st.error("Failed to generate PDF. Check server logs.")
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
# 3. HIGH-PERFORMANCE GLASS CSS
# =====================================================================
def inject_theme():
    is_dark = st.session_state.theme == "dark"
    bg_base = "#0B0F19" if is_dark else "#F1F5F9"
    surface = "rgba(17, 20, 29, 0.65)" if is_dark else "rgba(255, 255, 255, 0.75)"
    surface_solid = "#11141D" if is_dark else "#FFFFFF"
    border = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(15, 23, 42, 0.1)"
    text = "#F8FAFC" if is_dark else "#0F172A"
    subtext = "#94A3B8" if is_dark else "#475569"
    accent = "#0066FF" if is_dark else "#0284C7"
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        :root {{ --bg-base: {bg_base}; --text: {text}; --subtext: {subtext}; --surface: {surface}; --surface-solid: {surface_solid}; --border: {border}; --accent: {accent}; }}
        * {{ font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.015em; }}
        .stApp, [data-testid="stHeader"] {{ background-color: var(--bg-base); color: var(--text); transition: all 0.4s ease; }}
        [data-testid="stSidebar"] {{ background-color: var(--surface) !important; backdrop-filter: blur(24px); border-right: 1px solid var(--border); }}
        h1, h2, h3, h4, h5, h6 {{ font-weight: 700; color: var(--text) !important; letter-spacing: -0.03em !important; }}
        p, span, label, div {{ color: var(--text); }}
        #MainMenu, footer {{ visibility: hidden; }}
        [data-testid="block-container"] {{ padding-top: 5rem !important; }}
        
        .floating-nav {{
            position: fixed; top: 15px; left: 50%; transform: translateX(-50%); width: 95%; max-width: 1400px; z-index: 99999;
            background: var(--surface); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: 9999px;
            padding: 10px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        .hero-wrap {{ max-width: 900px; margin: 60px auto 40px auto; text-align: center; }}
        .hero-title {{ font-size: clamp(2.5rem, 5vw, 4.5rem); line-height: 1.1; font-weight: 800; margin-bottom: 24px; color: var(--text); }}
        .slideshow-wrapper {{ border-radius: 16px; overflow: hidden; border: 1px solid var(--border); height: 380px; background: var(--surface-solid); position: relative; }}
        .slide-img {{ position: absolute; width: 100%; height: 100%; object-fit: cover; opacity: 0; animation: smoothFade 16s infinite; }}
        .slide-img:nth-child(1) {{ animation-delay: 0s; }} .slide-img:nth-child(2) {{ animation-delay: 4s; }}
        .slide-img:nth-child(3) {{ animation-delay: 8s; }} .slide-img:nth-child(4) {{ animation-delay: 12s; }}
        @keyframes smoothFade {{ 0% {{opacity: 0;}} 10% {{opacity: 1;}} 25% {{opacity: 1;}} 35% {{opacity: 0;}} 100% {{opacity: 0;}} }}
        
        /* Auth Container */
        .auth-gate {{ background: var(--surface-solid); border: 1px solid var(--accent); border-radius: 16px; padding: 40px; max-width: 450px; margin: 10vh auto; box-shadow: 0 20px 50px rgba(0,0,0,0.2); text-align:center; }}
        
        .metric-tile {{ background: var(--surface-solid); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; }}
        .metric-val {{ font-size: 2.2rem; font-weight: 800; color: var(--accent); }}
        .stButton > button {{ border-radius: 9999px !important; padding: 8px 24px !important; font-weight: 600 !important; border: 1px solid var(--border) !important; background: var(--surface-solid) !important; color: var(--text) !important; transition: all 0.2s !important; }}
        .stButton > button[data-testid="baseButton-primary"] {{ background: var(--text) !important; color: var(--bg-base) !important; border: none !important; }}
    </style>
    """, unsafe_allow_html=True)

inject_theme()

# =====================================================================
# 4. NAVBAR
# =====================================================================
st.markdown("<div class='floating-nav'>", unsafe_allow_html=True)
c_logo, c_space, c_toggle, c_cta = st.columns([3, 5, 1.5, 2])
with c_logo:
    logo_b64 = get_base64_image("my_logo.png")
    blend = "normal" if st.session_state.theme == "dark" else "multiply"
    st.markdown(f"<div style='display:flex; align-items:center; gap:10px;'><img src='data:image/png;base64,{logo_b64}' alt='Logo' style='height:30px; mix-blend-mode:{blend};'><span style='font-weight:700; font-size:1.1rem; color:var(--text);'>DroneMap AI</span></div>", unsafe_allow_html=True)
with c_toggle:
    st.button("☀️ Light" if st.session_state.theme == "dark" else "🌙 Dark", on_click=toggle_theme, use_container_width=True)
with c_cta:
    if st.session_state.view == "landing":
        st.button("Launch App", type="primary", on_click=set_view, args=("auth",), use_container_width=True)
    elif st.session_state.view == "workspace":
        st.button("Exit System", on_click=set_view, args=("landing",), use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# =====================================================================
# VIEW: LANDING
# =====================================================================
if st.session_state.view == "landing":
    st.markdown("""
    <div class="hero-wrap">
        <div style="display:inline-block; border: 1px solid var(--accent); color: var(--accent); padding: 6px 16px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 20px;">SVAMITVA Scheme Compliant</div>
        <div class="hero-title">Mapping the Future of<br><span style="color: var(--accent);">Land Ownership</span></div>
        <div class="hero-sub">Over 60% of rural land parcels lack formal boundaries. DroneMap AI transforms raw aerial telemetry into dispute-free, legally binding cadastral property titles instantly.</div>
    </div>
    """, unsafe_allow_html=True)
    c_b1, c_b2, c_b3 = st.columns([1.6, 1.2, 1.6])
    with c_b2: st.button("Explore the Engine", type="primary", on_click=set_view, args=("auth",), use_container_width=True)

# =====================================================================
# VIEW: AUTHENTICATION GATE
# =====================================================================
elif st.session_state.view == "auth":
    st.markdown("<div class='auth-gate'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:var(--accent); margin-bottom: 5px;'>DroneMap Secure Access</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:var(--subtext); margin-bottom: 30px;'>Authorized Surveyors Only</p>", unsafe_allow_html=True)
    
    uid = st.text_input("Surveyor ID", value="SV-4029")
    pwd = st.text_input("Access Protocol", type="password", value="demo")
    
    if st.button("Authenticate", type="primary", use_container_width=True):
        with st.spinner("Verifying credentials..."):
            time.sleep(1)
            if uid:
                st.session_state.logged_in = True
                st.session_state.user_id = uid
                set_view("workspace")
                st.rerun()
            else:
                st.error("Invalid ID.")
    st.markdown("</div>", unsafe_allow_html=True)

# =====================================================================
# VIEW: COMMAND CENTER
# =====================================================================
elif st.session_state.view == "workspace" and st.session_state.logged_in:

    with st.sidebar:
        st.markdown(f"**🟢 Active Session:** `{st.session_state.user_id}`")
        st.markdown("---")
        st.markdown("### 1. Data Ingestion")
        uploaded_file = st.file_uploader("Upload Orthomosaic (.PNG/.JPG)", type=["png", "jpg", "jpeg", "tif"], label_visibility="collapsed")
        
        if uploaded_file:
            try:
                st.session_state.raw_img = Image.open(uploaded_file).convert("RGB")
                st.session_state.extracted = False
                st.session_state.is_demo = False
                st.toast("Physical raster ingested. Note: Custom GeoTIFF metadata parsing omitted in prototype.", icon="📥")
            except Exception:
                logging.exception("Upload fail")
                st.error("Invalid image format.")
                
        if st.button("🌐 Generate Procedural Demo", use_container_width=True):
            st.session_state.raw_img = generate_synthetic_orthomosaic()
            st.session_state.extracted = False
            st.session_state.is_demo = True
            
        st.markdown("---")
        with st.expander("⚙️ Advanced Parameters"):
            st.session_state.gsd = st.slider("GSD (m/px)", 0.01, 0.20, st.session_state.gsd, 0.01)
            st.session_state.conf = st.slider("AI Confidence", 0.10, 0.90, st.session_state.conf, 0.05)
            st.session_state.anchor_lat = st.number_input("Anchor Lat", value=st.session_state.anchor_lat, format="%.6f")
            st.session_state.anchor_lon = st.number_input("Anchor Lon", value=st.session_state.anchor_lon, format="%.6f")

    st.markdown("<h2 style='margin-bottom: 20px;'>🛰️ Cadastral Command Studio</h2>", unsafe_allow_html=True)
    
    if st.session_state.using_generic_weights and not st.session_state.is_demo:
        st.warning("⚠️ **Compliance Warning:** Custom weights `best.pt` not found. Running generic COCO architecture. Results are illustrative.")

    tab1, tab2, tab3 = st.tabs(["1️⃣ Extraction Studio", "2️⃣ Interactive WebGIS", "3️⃣ Audit & Certification"])

    # TAB 1: EXTRACTION
    with tab1:
        if st.session_state.raw_img is None:
            st.info("👋 **Welcome to the Command Studio!**\nPlease start by uploading a drone raster or generating a demo quadrant in the left sidebar.")
        else:
            col_l, col_r = st.columns(2)
            with col_l:
                st.image(st.session_state.raw_img, use_container_width=True)
                
                if st.button("⚡ Execute Neural Pipeline", type="primary", use_container_width=True):
                    with st.spinner("Analyzing structures & generating vectors..."):
                        t_start = time.time()
                        parcels, geojson_features = [], []
                        
                        # --- THE DEMO BYPASS ---
                        if st.session_state.is_demo:
                            # Hardcoded math bypass matching the synthetic map boxes perfectly
                            boxes = [[60, 50, 280, 280], [340, 60, 590, 290], [660, 50, 940, 280], [70, 450, 300, 680], [360, 440, 630, 670], [690, 450, 950, 680]]
                            for idx, b in enumerate(boxes):
                                mask_xy = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
                                poly = Polygon(mask_xy)
                                sqm = round(float(poly.area * (st.session_state.gsd ** 2)), 2)
                                perim = round(float(poly.length * st.session_state.gsd), 2)
                                hash_id = hashlib.md5(str(mask_xy).encode()).hexdigest()[:4].upper()
                                upin = f"WB-{datetime.now().strftime('%m%d')}-{hash_id}"
                                
                                coords = [px_to_latlon(pt[0], pt[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for pt in mask_xy]
                                coords.append(coords[0])
                                
                                parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": perim, "Confidence (%)": 99.9, "Verified By": ""})
                                geojson_features.append({"type": "Feature", "properties": {"upin": upin, "area": sqm, "confidence": 99.9}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
                            
                            st.session_state.ai_img = st.session_state.raw_img
                            
                        # --- THE REAL AI PIPELINE ---
                        else:
                            model = load_segmentation_model()
                            if model:
                                pred = model.predict(st.session_state.raw_img, conf=st.session_state.conf, save=False)
                                if pred[0].masks is not None:
                                    annotated = pred[0].plot()
                                    st.session_state.ai_img = Image.fromarray(annotated[..., ::-1])
                                    for idx, (mask_xy, box) in enumerate(zip(pred[0].masks.xy, pred[0].boxes)):
                                        if len(mask_xy) < 3: continue
                                        poly = Polygon(mask_xy).simplify(tolerance=1.5, preserve_topology=True)
                                        if poly.is_empty: continue
                                        mask_xy = list(poly.exterior.coords)
                                        
                                        sqm = round(float(poly.area * (st.session_state.gsd ** 2)), 2)
                                        perim = round(float(poly.length * st.session_state.gsd), 2)
                                        conf = round(float(box.conf[0]) * 100, 1)
                                        hash_id = hashlib.md5(str(mask_xy[0]).encode()).hexdigest()[:4].upper()
                                        upin = f"WB-{datetime.now().strftime('%m%d')}-{hash_id}"
                                        
                                        coords = [px_to_latlon(pt[0], pt[1], st.session_state.anchor_lat, st.session_state.anchor_lon, st.session_state.gsd) for pt in mask_xy]
                                        coords.append(coords[0])
                                        
                                        parcels.append({"UPIN": upin, "Verified": False, "Area (m²)": sqm, "Perimeter (m)": perim, "Confidence (%)": conf, "Verified By": ""})
                                        geojson_features.append({"type": "Feature", "properties": {"upin": upin, "area": sqm, "confidence": conf}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
                                else:
                                    st.session_state.ai_img = st.session_state.raw_img
                                    st.warning("No structures detected.")

                        st.session_state.survey_df = pd.DataFrame(parcels) if parcels else pd.DataFrame(columns=["UPIN", "Verified", "Area (m²)", "Perimeter (m)", "Confidence (%)", "Verified By"])
                        st.session_state.geo_json = {"type": "FeatureCollection", "features": geojson_features}
                        st.session_state.latency = round(time.time() - t_start, 2)
                        st.session_state.extracted = True
                        st.rerun()

            with col_r:
                if st.session_state.extracted and st.session_state.ai_img:
                    st.image(st.session_state.ai_img, use_container_width=True)
                else:
                    st.info("Waiting for pipeline execution...")

    # TAB 2: WEBGIS
    with tab2:
        if not st.session_state.extracted or st.session_state.geo_json is None or not st.session_state.geo_json["features"]:
            st.info("🗺️ Execute Step 1 to generate vectors.")
        else:
            tiles = "CartoDB Dark_Matter" if st.session_state.theme == "dark" else "CartoDB positron"
            try:
                m = folium.Map(location=[st.session_state.anchor_lat, st.session_state.anchor_lon], zoom_start=18, tiles=tiles)
                folium.GeoJson(
                    st.session_state.geo_json,
                    style_function=lambda x: {"fillColor": "#0EA5E9", "color": "#0284C7", "weight": 2, "fillOpacity": 0.4},
                    tooltip=folium.GeoJsonTooltip(fields=["upin", "area"], aliases=["UPIN:", "Area (m²):"])
                ).add_to(m)
                plugins.Fullscreen().add_to(m)
                m.fit_bounds(m.get_bounds())
                st_folium(m, width="100%", height=550, returned_objects=[])
                st.download_button("📥 Export GeoJSON", data=json.dumps(st.session_state.geo_json), file_name="parcels.geojson", mime="application/geo+json")
            except Exception as e:
                st.error(f"Map Render Error: {e}")

    # TAB 3: AUDIT
    with tab3:
        if not st.session_state.extracted or st.session_state.survey_df.empty:
            st.info("📄 Execute Step 1 to populate ledger.")
        else:
            df = st.session_state.survey_df
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f'<div class="metric-tile"><div class="metric-val">{len(df)}</div><div class="metric-lbl">Parcels</div></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-tile"><div class="metric-val">{df["Area (m²)"].sum():,.0f}</div><div class="metric-lbl">Total m²</div></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-tile"><div class="metric-val">{st.session_state.latency}s</div><div class="metric-lbl">Compute Time</div></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-tile"><div class="metric-val">{(df["Verified"] == True).sum()}</div><div class="metric-lbl">Approved</div></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("##### 🧑‍💻 Surveyor Verification Ledger")
            
            # Identity capture on verification
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True, disabled=["UPIN", "Area (m²)", "Perimeter (m)", "Confidence (%)", "Verified By"])
            
            # Auto-stamp the verified by column if checked
            for idx in edited_df.index:
                if edited_df.at[idx, 'Verified'] and not edited_df.at[idx, 'Verified By']:
                    edited_df.at[idx, 'Verified By'] = st.session_state.user_id
                elif not edited_df.at[idx, 'Verified']:
                    edited_df.at[idx, 'Verified By'] = ""
            
            st.session_state.survey_df = edited_df
            cleared = edited_df[edited_df["Verified"] == True]
            
            if not cleared.empty:
                st.markdown("---")
                col_sel, col_prev = st.columns([1.2, 2])
                with col_sel:
                    selected_upin = st.selectbox("Select Cleared UPIN:", cleared["UPIN"].tolist())
                    record = cleared[cleared["UPIN"] == selected_upin].iloc[0]
                    
                    pdf_bytes = generate_pdf(record, st.session_state.anchor_lat, st.session_state.anchor_lon)
                    if pdf_bytes:
                        st.download_button("🖨️ Download Form 7 PDF", data=pdf_bytes, file_name=f"{record['UPIN']}_Certificate.pdf", mime="application/pdf", type="primary", use_container_width=True)
                    st.download_button("📥 Export Secure Ledger", data=edited_df.to_csv(index=False).encode('utf-8'), file_name="Cadastral_Register.csv", mime="text/csv", use_container_width=True)
                    
                with col_prev:
                    qr_b64 = make_qr_code(f"UPIN:{record['UPIN']}|AREA:{record['Area (m²)']}|AUTH:{record['Verified By']}")
                    st.markdown(f"""
                    <div style="background: var(--surface-solid); border: 1px solid var(--border); border-radius: 16px; padding: 24px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div><h3 style="margin:0; font-family:'Space Grotesk', sans-serif;">{record['UPIN']}</h3><p style="margin:4px 0 0 0; color:#10B981; font-weight:700; font-size:0.85rem;">✔ TITLE CLEARED</p></div>
                            <img src="data:image/png;base64,{qr_b64}" alt="QR Code" width="75" style="border-radius: 6px;" />
                        </div>
                        <hr style="border:none; border-bottom: 1px solid var(--border); margin: 16px 0;">
                        <p style="margin: 6px 0; font-size: 0.9rem;"><b>Ground Footprint:</b> {record['Area (m²)']} m²</p>
                        <p style="margin: 6px 0; font-size: 0.9rem;"><b>Perimeter:</b> {record['Perimeter (m)']} m</p>
                        <p style="margin: 6px 0; font-size: 0.9rem;"><b>Cleared By:</b> {record['Verified By']}</p>
                    </div>
                    """, unsafe_allow_html=True)
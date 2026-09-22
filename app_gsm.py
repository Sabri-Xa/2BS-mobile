import json
import requests
import base64
import os
import streamlit as st
import streamlit.components.v1 as components

# Configuration pour un affichage optimal sur téléphone
st.set_page_config(page_title="2BS Transport Mobile", layout="centered", initial_sidebar_state="collapsed")

# --- CORRECTIF GLOBAL DE LA TAILLE DE POLICE (ENCORE PLUS GRAND) ---
st.markdown("""
<style>
    /* Force une police géante et ultra-lisible partout sur le téléphone */
    html, body, [class*="css"] {
        font-size: 22px !important;
    }
    .stMarkdown p, .stMarkdown li, span, label {
        font-size: 22px !important;
    }
    .stButton>button {
        width: 100%;
        height: 60px;
        font-weight: bold;
        font-size: 24px !important;
    }
    input, select, .st-bh, .st-bb {
        font-size: 22px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SCRIPT JAVASCRIPT POUR LE SWIPE (GLISSER DROITE/GAUCHE) ---
# Ce script détecte les mouvements du doigt sur l'écran du téléphone
swipe_js = """
<script>
    const doc = window.parent.document;
    let touchstartX = 0;
    let touchstartY = 0;
    let touchendX = 0;
    let touchendY = 0;

    function checkDirection() {
        const thresholdX = 60; // Distance minimum pour considérer que c'est un swipe horizontal
        const diffX = touchendX - touchstartX;
        const diffY = touchendY - touchstartY;

        // On s'assure que c'est un mouvement horizontal et pas un défilement vers le bas
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > thresholdX) {
            if (diffX < 0) {
                // Swipe vers la gauche (Onglet suivant)
                switchTab(1);
            } else {
                // Swipe vers la droite (Onglet précédent)
                switchTab(-1);
            }
        }
    }

    function switchTab(direction) {
        const tabs = Array.from(doc.querySelectorAll('button[role="tab"]'));
        if (tabs.length === 0) return;
        
        let activeIndex = tabs.findIndex(tab => tab.getAttribute('aria-selected') === 'true');
        if (activeIndex === -1) return;
        
        let newIndex = activeIndex + direction;
        if (newIndex >= 0 && newIndex < tabs.length) {
            tabs[newIndex].click();
        }
    }

    doc.addEventListener('touchstart', e => {
        touchstartX = e.changedTouches[0].screenX;
        touchstartY = e.changedTouches[0].screenY;
    }, {passive: true});

    doc.addEventListener('touchend', e => {
        touchendX = e.changedTouches[0].screenX;
        touchendY = e.changedTouches[0].screenY;
        checkDirection();
    }, {passive: true});
</script>
"""
components.html(swipe_js, height=0, width=0)

# --- GESTION DE LA CLÉ API SÉCURISÉE ---
try:
    ORS_API_KEY = st.secrets["ORS_API_KEY"]
except:
    ORS_API_KEY = ""

# --- GESTION DE LA SAUVEGARDE AUTOMATIQUE ---
CONFIG_FILE = "config_mobile.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "prix_diesel": 1.65, 
        "prix_adblue": 0.80, 
        "saisie_ttc": True,
        "leasing_mensuel": 0.0, 
        "assurance_mensuel": 0.0,
        "abo_mensuel": 0.0,
        "marge_pourcent": 20
    }

config = load_config()

def save_config(new_config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_config, f)

# --- FOND D'ÉCRAN ---
def set_background(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: linear-gradient(rgba(255, 255, 255, 0.93), rgba(255, 255, 255, 0.93)), url("data:image/jpeg;base64,{encoded_string}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

set_background("Logo 2BS.jpg")

st.markdown("<h2 style='text-align: center; font-size: 30px;'>🚛 2BS Transport</h2>", unsafe_allow_html=True)

# Initialisation mémoire
if "distance_km" not in st.session_state: st.session_state.distance_km = 0.0
if "h_val" not in st.session_state: st.session_state.h_val = 0
if "m_val" not in st.session_state: st.session_state.m_val = 0
if "destinations" not in st.session_state: st.session_state.destinations = [""]
if "segments" not in st.session_state: st.session_state.segments = []
if "points_valides" not in st.session_state: st.session_state.points_valides = []

def geocoder(adresse):
    adresse = adresse.strip()
    if not adresse: return None, None
    try:
        url = "https://photon.komoot.io/api/"
        params = {"q": adresse, "limit": 1, "lang": "fr"}
        headers = {"User-Agent": "2BSTransportApp/1.0"}
        rep = requests.get(url, params=params, headers=headers, timeout=5)
        if rep.status_code == 200:
            data = rep.json()
            if data and "features" in data and len(data["features"]) > 0:
                coords = data["features"][0]["geometry"]["coordinates"]
                return float(coords[0]), float(coords[1])
    except: pass
    return None, None

def calculer_route(depart, liste_arrivees):
    try:
        lon1, lat1 = geocoder(depart)
        if not lon1 or not lat1: return None, None, ["Départ introuvable."], [], []
        
        pts = [{"nom": depart, "lon": lon1, "lat": lat1}]
        errs = []
        for d in liste_arrivees:
            if not d.strip(): continue
            lon_d, lat_d = geocoder(d)
            if lon_d and lat_d: pts.append({"nom": d, "lon": lon_d, "lat": lat_d})
            else: errs.append(d)
                
        if len(pts) < 2: return None, None, errs + ["Pas assez d'étapes."], [], []
        
        coords_str = ";".join([f"{p['lon']},{p['lat']}" for p in pts])
        try:
            rep_trip = requests.get(f"http://router.project-osrm.org/trip/v1/driving/{coords_str}?source=first&roundtrip=true", timeout=10)
            if rep_trip.status_code == 200 and rep_trip.json().get("code") == "Ok":
                wps = rep_trip.json()["waypoints"]
                order = [0] * len(pts)
                for i, wp in enumerate(wps): order[wp["waypoint_index"]] = i
                pts = [pts[i] for i in order]
        except: pass

        pts.append({"nom": depart + " (Retour)", "lon": lon1, "lat": lat1})
        
        tot_dist, tot_dur = 0.0, 0.0
        segs = []
        palette = ['#FF0000', '#0000FF', '#228B22', '#FF8C00']

        headers = {
            'Authorization': ORS_API_KEY,
            'Content-Type': 'application/json'
        }

        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            
            url_ors = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
            # Forçage des instructions en français !
            body = {
                "coordinates": [[p1['lon'], p1['lat']], [p2['lon'], p2['lat']]],
                "language": "fr",
                "instructions": True
            }
            
            rep = requests.post(url_ors, json=body, headers=headers, timeout=10)
            if rep.status_code == 200:
                data = rep.json()
                summary = data["features"][0]["properties"]["summary"]
                dist = summary["distance"] / 1000.0
                dur = summary["duration"] / 3600.0
                coords = data["features"][0]["geometry"]["coordinates"]
                
                steps_list = []
                try:
                    ors_segments = data["features"][0]["properties"].get("segments", [])
                    for seg_item in ors_segments:
                        for step in seg_item.get("steps", []):
                            instr = step.get("instruction", "").strip()
                            if instr:
                                steps_list.append({
                                    "instruction": instr,
                                    "dist": step.get("distance", 0) / 1000.0
                                })
                except:
                    pass
                
                # Sécurité si l'API ne renvoie aucune instruction
                if not steps_list:
                    steps_list.append({"instruction": "Suivre la route principale", "dist": dist})

                tot_dist += dist
                tot_dur += dur
                segs.append({
                    "depart": p1["nom"], "arrivee": p2["nom"],
                    "dist": dist, "dur": dur, "couleur": palette[i % len(palette)],
                    "coords": coords, "steps": steps_list
                })
            else:
                return None, None, ["Erreur avec la clé API ou le serveur ORS."], [], []
                
        return round(tot_dist, 1), tot_dur, errs, segs, pts
    except Exception as e: return None, None, [str(e)], [], []

def generer_gpx(segments):
    gpx = '<?xml version="1.0" encoding="UTF-8"?>\n'
    gpx += '<gpx version="1.1" creator="2BS Transport" xmlns="http://www.topografix.com/GPX/1/1">\n'
    gpx += '  <trk>\n    <name>Tournee Camion 2BS</name>\n    <trkseg>\n'
    for seg in segments:
        for pt in seg["coords"]:
            gpx += f'      <trkpt lat="{pt[1]}" lon="{pt[0]}"></trkpt>\n'
    gpx += '    </trkseg>\n  </trk>\n'
    gpx += '</gpx>'
    return gpx


# --- INTERFACE EN ONGLETS ---
tab1, tab2, tab3 = st.tabs(["📍 Tournée", "💰 Devis & PRK", "🚀 Navigation"])

with tab1:
    ville_depart = st.text_input("Départ / Dépôt", "Sint-Pieters-Leeuw")
    
    updated_destinations = []
    for i, dest in enumerate(st.session_state.destinations):
        col_input, col_del = st.columns([5, 1])
        val = col_input.text_input(f"Étape {i+1}", value=dest, key=f"dest_{i}")
        updated_destinations.append(val)
        if len(st.session_state.destinations) > 1:
            if col_del.button("❌", key=f"del_{i}"):
                st.session_state.destinations.pop(i)
                st.rerun()
                
    st.session_state.destinations = updated_destinations
    if st.button("➕ Ajouter un client"):
        st.session_state.destinations.append("")
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔍 Calculer & Optimiser", type="primary"):
        if not ORS_API_KEY:
            st.error("⚠️ La clé API OpenRouteService manque dans les paramètres secrets !")
        else:
            with st.spinner("Calcul itinéraire camion en cours..."):
                dist_calc, temps_calc, errs, segs, pts = calculer_route(ville_depart, st.session_state.destinations)
                if dist_calc is not None:
                    st.session_state.distance_km = dist_calc
                    st.session_state.h_val = int(temps_calc)
                    st.session_state.m_val = int(round((temps_calc - int(temps_calc)) * 60))
                    st.session_state.segments = segs
                    st.session_state.points_valides = pts
                    st.success(f"✅ OK : {dist_calc} km | {st.session_state.h_val}h{st.session_state.m_val:02d}")
                else:
                    st.error(f"Erreur de calcul : {', '.join(errs)}")

with tab2:
    saisie_ttc = st.checkbox("Prix Carburant TTC à la pompe ?", value=config.get("saisie_ttc", True))
    col_d, col_a = st.columns(2)
    prix_diesel_input = col_d.number_input("Diesel (€/L)", value=config.get("prix_diesel", 1.65), step=0.01)
    prix_adblue_input = col_a.number_input("AdBlue (€/L)", value=config.get("prix_adblue", 0.80), step=0.01)
    
    prix_diesel_htva = prix_diesel_input / 1.21 if saisie_ttc else prix_diesel_input
    prix_adblue_htva = prix_adblue_input / 1.21 if saisie_ttc else prix_adblue_input

    type_camion = st.selectbox("Véhicule", ["CE (Tracteur Mercedes)", "C (Porteur)"])
    norme_euro = st.selectbox("Norme EURO", ["Euro 6", "Euro 5"])
    
    with st.expander("Frais Fixes Mensuels"):
        leasing_mensuel = st.number_input("Leasing Mensuel", value=config.get("leasing_mensuel", 0.0), step=100.0)
        assurance_mensuel = st.number_input("Assurances", value=config.get("assurance_mensuel", 0.0), step=50.0)
        frais_divers = st.number_input("Frais divers", value=config.get("abo_mensuel", 0.0), step=50.0)

    marge_pourcent = st.number_input("Marge souhaitée (%)", min_value=0, max_value=100, value=int(config.get("marge_pourcent", 20)), step=1)
    
    current_config = {
        "prix_diesel": prix_diesel_input, "prix_adblue": prix_adblue_input, "saisie_ttc": saisie_ttc,
        "leasing_mensuel": leasing_mensuel, "assurance_mensuel": assurance_mensuel, "abo_mensuel": frais_divers,
        "marge_pourcent": marge_pourcent
    }
    if current_config != config: save_config(current_config)

    # --- CALCUL ---
    dist = st.session_state.distance_km
    heures = st.session_state.h_val + (st.session_state.m_val / 60.0)
    
    conso_100 = 32.0 if "CE" in type_camion else 22.0
    peage_km = 0.17 if norme_euro == "Euro 6" else 0.20
    
    c_carburant = (dist / 100) * conso_100 * prix_diesel_htva
    c_adblue = (dist / 100) * (conso_100 * 0.05) * prix_adblue_htva
    c_usure = dist * 0.12
    c_viapass = dist * peage_km
    c_chauffeur = heures * 45.0
    
    c_fixes = heures * ((leasing_mensuel + assurance_mensuel + frais_divers) / 160.0)
    
    prk_total = c_carburant + c_adblue + c_usure + c_viapass + c_chauffeur + c_fixes
    facture_htva = prk_total * (1 + (marge_pourcent/100))
    
    st.markdown("---")
    st.success(f"**💰 À FACTURER : {facture_htva:.2f} € HTVA**")
    
    col1, col2 = st.columns(2)
    col1.metric("PRK course", f"{prk_total:.2f} €")
    col2.metric("Marge Nette", f"{facture_htva - prk_total:.2f} €")

    with st.expander("📊 Détail du calcul PRK"):
        st.markdown(f"• **Carburant :** {c_carburant:.2f} €")
        st.markdown(f"• **AdBlue :** {c_adblue:.2f} €")
        st.markdown(f"• **Usure/Pneus :** {c_usure:.2f} €")
        st.markdown(f"• **Péage :** {c_viapass:.2f} €")
        st.markdown(f"• **Chauffeur :** {c_chauffeur:.2f} €")
        st.markdown(f"• **Frais Fixes :** {c_fixes:.2f} €")

with tab3:
    if not st.session_state.segments:
        st.info("⚠️ Veuillez d'abord calculer une tournée.")
    else:
        gpx_data = generer_gpx(st.session_state.segments)
        st.download_button(
            label="📥 TÉLÉCHARGER LE PARCOURS (.gpx)",
            data=gpx_data,
            file_name="Tournee_Camion_2BS.gpx",
            mime="application/gpx+xml",
            type="primary"
        )
        
        st.markdown("---")
        for i, seg in enumerate(st.session_state.segments):
            dur_h = int(seg.get('dur', 0))
            dur_m = int(round((seg.get('dur', 0) - dur_h) * 60))
            dur_str = f"{dur_h}h{dur_m:02d}" if dur_h > 0 else f"{dur_m} min"
            
            st.markdown(
                f"""
                <div style='padding: 16px; background: white; color: black; border-radius: 12px; border-left: 12px solid {seg['couleur']}; margin-bottom: 16px; box-shadow: 0px 4px 8px rgba(0,0,0,0.2);'>
                    <div style='font-weight: bold; margin-bottom: 6px;'>Étape {i+1}</div>
                    <div style='margin-bottom: 4px;'><b>Départ:</b> {seg['depart']}</div>
                    <div style='margin-bottom: 6px;'><b>Arrivée:</b> {seg['arrivee']}</div>
                    <div style='font-weight: bold; color: #004085; margin-top: 8px;'>
                        🛣️ {seg['dist']:.1f} km &nbsp;|&nbsp; ⏱️ {dur_str}
                    </div>
                </div>
                """, unsafe_allow_html=True
            )
            
            if seg.get("steps"):
                with st.expander(f"🔍 Détail route (Étape {i+1})"):
                    for step in seg["steps"]:
                        st.markdown(
                            f"""<div style='color: black; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;'>
                                🔹 {step['instruction']} <b style='color: #333;'>({step['dist']:.1f} km)</b>
                            </div>""", 
                            unsafe_allow_html=True
                        )

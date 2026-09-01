import math
import folium
import streamlit as st
from streamlit_folium import st_folium

# ------------------------------------------------------------------------------
# 1. ІМПОРТ З БАЗИ ДАНИХ ТА ЗАХИСТ ВІД ВІДСУТНІХ ЗМІННИХ
# ------------------------------------------------------------------------------
import data_tables

TABLE_G_T1 = getattr(data_tables, "TABLE_G_T1", {})
TABLE_K_T1 = getattr(data_tables, "TABLE_K_T1", {})
G_t2 = getattr(data_tables, "G_t2", {})
K_t2 = getattr(data_tables, "K_t2", {})
KM_OPTIONS = getattr(
    data_tables,
    "KM_OPTIONS",
    {
        "Відкрита місцевість (Км = 1.0)": 1.0,
        "Міська забудова / ліс (Км = 0.5)": 0.5,
    },
)

# ------------------------------------------------------------------------------
# 2. ІНІЦІАЛІЗАЦІЯ SESSION STATE ТА СИНХРОНІЗАЦІЯ КООРДИНАТ
# ------------------------------------------------------------------------------
if "lat" not in st.session_state:
    st.session_state["lat"] = 50.4501
if "lon" not in st.session_state:
    st.session_state["lon"] = 30.5234

if "input_lat" not in st.session_state:
    st.session_state["input_lat"] = st.session_state["lat"]
if "input_lon" not in st.session_state:
    st.session_state["input_lon"] = st.session_state["lon"]

def update_from_input():
    """Колбек при ручному введенні в number_input."""
    st.session_state["lat"] = round(st.session_state["input_lat"], 4)
    st.session_state["lon"] = round(st.session_state["input_lon"], 4)

# ------------------------------------------------------------------------------
# 3. РОЗРАХУНКОВІ ФУНКЦІЇ
# ------------------------------------------------------------------------------

def interpolate_1d(val, points):
    if not points or not isinstance(points, dict):
        return 1.0
    try:
        sorted_keys = sorted([float(k) for k in points.keys()])
    except (ValueError, TypeError):
        return 1.0

    if not sorted_keys:
        return 1.0

    val = float(val)
    if val <= sorted_keys[0]:
        return float(points.get(sorted_keys[0], points.get(str(sorted_keys[0]), 1.0)))
    if val >= sorted_keys[-1]:
        return float(points.get(sorted_keys[-1], points.get(str(sorted_keys[-1]), 1.0)))

    for i in range(len(sorted_keys) - 1):
        x0, x1 = sorted_keys[i], sorted_keys[i + 1]
        if x0 <= val <= x1:
            y0 = float(points.get(x0, points.get(str(x0), 1.0)))
            y1 = float(points.get(x1, points.get(str(x1), 1.0)))
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (val - x0) / (x1 - x0)
            
    return 1.0


def get_base_depth(substance, vert_st, q, wind_v):
    if substance not in TABLE_G_T1:
        return 0.0
    sub_data = TABLE_G_T1[substance]

    if vert_st not in sub_data:
        vert_st = list(sub_data.keys())[0]
    st_data = sub_data[vert_st]

    q_map = {float(k): k for k in st_data.keys()}
    q_keys = sorted(q_map.keys())

    if not q_keys:
        return 0.0

    q_target_val = q_keys[0]
    for q_k in q_keys:
        if q >= q_k:
            q_target_val = q_k
        else:
            break

    q_target_key = q_map[q_target_val]
    v_dict = st_data[q_target_key]

    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())

    if not v_keys:
        return 0.0

    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break

    v_target_key = v_map[v_target_val]
    return float(v_dict[v_target_key])


def get_base_depth_gt2(substance, vert_st, q, wind_v):
    if not G_t2 or substance not in G_t2:
        return 0.0

    sub_data = G_t2[substance]

    q_map = {float(k): k for k in sub_data.keys()}
    q_keys = sorted(q_map.keys())

    if not q_keys:
        return 0.0

    q_target_val = q_keys[0]
    for q_k in q_keys:
        if q >= q_k:
            q_target_val = q_k
        else:
            break

    q_target_key = q_map[q_target_val]

    if vert_st not in sub_data[q_target_key]:
        return 0.0

    v_dict = sub_data[q_target_key][vert_st]

    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())

    if not v_keys:
        return 0.0

    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break

    v_target_key = v_map[v_target_val]
    return float(v_dict[v_target_key])


def calculate_zone(substance, vert_st, q, wind_v, temp, is_closed, km_val):
    g1_base = get_base_depth(substance, vert_st, q, wind_v)
    kt1 = 1.0
    if TABLE_K_T1 and substance in TABLE_K_T1 and TABLE_K_T1[substance]:
        kt1 = interpolate_1d(temp, TABLE_K_T1[substance])

    g1 = g1_base * kt1 * km_val

    gt2_base = get_base_depth_gt2(substance, vert_st, q, wind_v)
    kt2 = 1.0
    if K_t2 and substance in K_t2 and K_t2[substance]:
        kt2 = interpolate_1d(temp, K_t2[substance])

    kk_val = 0.5 if is_closed else 1.0
    g2 = gt2_base * kt2 * kk_val * km_val

    r_a = 0.5
    g_total = max(g1, g2) + r_a

    if vert_st == "Інверсія":
        phi = 40.0
    elif vert_st == "Ізотермія":
        phi = 50.0
    else:
        phi = 70.0

    # Розрахунок площі зони можливого хімічного забруднення S (км²)
    s_area = 8.72e-4 * (g_total ** 2) * phi

    return g_total, g1, g2, phi, kt1, kt2, s_area


def create_sector_geojson(lat, lon, radius_km, wind_deg, phi_deg):
    r_m = radius_km * 1000.0
    cloud_vector_deg = (270.0 - wind_deg) % 360.0

    if phi_deg >= 360.0:
        points = []
        num_pts = 60
        for i in range(num_pts + 1):
            angle = math.radians(i * (360.0 / num_pts))
            d_lat = (r_m * math.sin(angle)) / 111111.0
            d_lon = (r_m * math.cos(angle)) / (
                111111.0 * math.cos(math.radians(lat))
            )
            points.append([lat + d_lat, lon + d_lon])
        return points

    half_phi = phi_deg / 2.0
    start_angle = cloud_vector_deg - half_phi
    end_angle = cloud_vector_deg + half_phi

    points = [[lat, lon]]
    num_pts = 30
    for i in range(num_pts + 1):
        ang_deg = start_angle + i * (end_angle - start_angle) / num_pts
        ang_rad = math.radians(ang_deg)
        
        d_lon = (r_m * math.cos(ang_rad)) / (111111.0 * math.cos(math.radians(lat)))
        d_lat = (r_m * math.sin(ang_rad)) / 111111.0
        
        points.append([lat + d_lat, lon + d_lon])
        
    points.append([lat, lon])
    return points


def get_wind_widget_html(wind_deg, wind_v):
    wind_kmh = wind_v * 3.6
    arrow_rotation = float(wind_deg) % 360.0

    return f"""
    <div style="
        position: fixed; 
        bottom: 30px; 
        left: 20px; 
        z-index: 9999; 
        background-color: #1e1e1e; 
        border: 2px solid #ffcc00; 
        border-radius: 12px; 
        padding: 10px 14px; 
        width: 110px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
        font-family: Arial, sans-serif;
        color: #ffffff;
        text-align: center;
    ">
        <div style="
            font-size: 26px; 
            line-height: 1; 
            margin-bottom: 4px;
            display: inline-block;
            transform: rotate({arrow_rotation}deg);
            color: #ffcc00;
        ">↓</div>
        <div style="font-size: 18px; font-weight: bold; color: #ffcc00; margin-bottom: 6px;">
            {int(wind_deg)}°
        </div>
        <div style="border-top: 1px dashed #ffcc00; margin-bottom: 6px;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #ffcc00; font-weight: bold; margin-bottom: 2px;">
            <span>м/с:</span>
            <span style="color: #ffffff;">{wind_v:.1f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #ffcc00; font-weight: bold;">
            <span>км/г:</span>
            <span style="color: #ffffff;">{wind_kmh:.1f}</span>
        </div>
    </div>
    """

# ------------------------------------------------------------------------------
# 4. ІНТЕРФЕЙС STREAMLIT
# ------------------------------------------------------------------------------

st.set_page_config(layout="wide", page_title="Прогноз хімічної аварії")

st.title("🧪 Аварійний прогноз масштабів хімічної аварії")

col_params, col_map = st.columns([1, 2])

with col_params:
    st.subheader("⚙️ Вхідні дані хімічної аварії")

    all_substances = sorted(list(set(list(TABLE_G_T1.keys()) + list(G_t2.keys()))))
    if not all_substances:
        all_substances = ["Аміак"]
        
    substance = st.selectbox("Назва НХР", all_substances)

    q_val = st.number_input(
        "Кількість НХР, т", min_value=0.1, max_value=10000.0, value=10.0, step=1.0
    )
    vert_st = st.selectbox(
        "Стійкість атмосфери", ["Інверсія", "Ізотермія", "Конвекція"]
    )

    if vert_st == "Ізотермія":
        wind_options = [1.0, 2.0, 3.0, 4.0, 10.0]
    else:
        wind_options = [1.0, 2.0, 3.0, 4.0]

    default_wind_index = 1 if 2.0 in wind_options else 0
    wind_v = st.selectbox(
        "Швидкість вітру, м/с",
        wind_options,
        index=default_wind_index,
        format_func=lambda x: f"{int(x) if float(x).is_integer() else x} м/с",
    )

    wind_deg = st.slider(
        "Напрямок вітру (звідки дме)", 
        0, 360, 90, 
        help="90° — Східний, 180° — Південний, 270° — Західний, 0°/360° — Північний"
    )
    temp = st.slider("Температура повітря, °C", -20, 30, 20)

    km_label = st.selectbox("Коефіцієнт місцевості (Км)", list(KM_OPTIONS.keys()))
    km_val = KM_OPTIONS[km_label]

    is_closed = st.checkbox("Закрита ємність / піддон", value=False)

    # --------------------------------------------------------------------------
    # ВВЕДЕННЯ КООРДИНАТ (ДВОСТОРОННЯ СИНХРОНІЗАЦІЯ)
    # --------------------------------------------------------------------------
    st.subheader("📍 Координати об'єкта")

    st.session_state["input_lat"] = st.session_state["lat"]
    st.session_state["input_lon"] = st.session_state["lon"]

    lat_val = st.number_input(
        "Широта (Lat)", 
        value=st.session_state["input_lat"], 
        format="%.4f", 
        key="input_lat",
        on_change=update_from_input
    )
    lon_val = st.number_input(
        "Довгота (Lon)", 
        value=st.session_state["input_lon"], 
        format="%.4f", 
        key="input_lon",
        on_change=update_from_input
    )

    # --------------------------------------------------------------------------
    # РОЗРАХУНОК ПРОГНОЗУ
    # --------------------------------------------------------------------------
    g_res, g1_res, g2_res, phi_res, kt1_res, kt2_res, s_res = calculate_zone(
        substance, vert_st, q_val, wind_v, temp, is_closed, km_val
    )

    # 1. Додано площу до блоку результатів розрахунку
    st.subheader("📊 Результати розрахунку")
    st.info(
        f"**Глибина зони хімічного забруднення (Г): {g_res:.2f} км**\n\n"
        f"**Площа зони забруднення (S): {s_res:.2f} км²**\n\n"
        f"• Первинна хмара (Г₁): **{g1_res:.2f} км** (Kₜ₁ = {kt1_res:.2f})\n\n"
        f"• Вторинна хмара (Г₂): **{g2_res:.2f} км** (Kₜ₂ = {kt2_res:.2f})\n\n"
        f"• Радіус осередку аварії (Rₐ): **0.50 км**\n\n"
        f"• Кут сектора ураження (Ф): **{phi_res}°**"
    )

    # Експорт у HTML
    st.subheader("💾 Збереження карти")
    
    m_export = folium.Map(location=[st.session_state["lat"], st.session_state["lon"]], zoom_start=11, tiles="OpenStreetMap")
    
    folium.Circle(
        location=[st.session_state["lat"], st.session_state["lon"]],
        radius=500,
        color="darkorange",
        fill=True,
        fill_color="orange",
        fill_opacity=0.8,
        popup=f"Осередок: {substance}, R_A = 0.5 км",
    ).add_to(m_export)

    sector_coords = create_sector_geojson(st.session_state["lat"], st.session_state["lon"], g_res, wind_deg, phi_res)

    folium.Polygon(
        locations=sector_coords,
        color="black",
        fill=True,
        fill_color="orange",
        fill_opacity=0.35,
        weight=2,
        popup=f"Глибина: {g_res:.2f} км, Площа: {s_res:.2f} км² (Ф = {phi_res}°)",
    ).add_to(m_export)

    folium.Marker(
        [st.session_state["lat"], st.session_state["lon"]],
        popup="Джерело аварії",
        icon=folium.Icon(color="red", icon="warning-sign")
    ).add_to(m_export)

    m_export.get_root().html.add_child(folium.Element(get_wind_widget_html(wind_deg, wind_v)))

    html_bytes = m_export._repr_html_().encode("utf-8")
    st.download_button(
        label="📥 Завантажити карту (.html)",
        data=html_bytes,
        file_name="карта_хімічного_забруднення.html",
        mime="text/html"
    )

with col_map:
    # 2. Додано площу до верхнього блоку над картою
    st.markdown(
        f"""
    <div style="background-color: #f0f2f6; padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 5px solid #ff4b4b; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <h4 style="margin: 0; color: #1f2937;">Глибина зони (Г): 
        <span style="color: #d97706; font-size: 1.1em;">{g_res:.2f} км</span></h4>
        <h4 style="margin: 0; color: #1f2937;">Площа зони (S): 
        <span style="color: #d97706; font-size: 1.1em;">{s_res:.2f} км²</span></h4>
    </div>
    """,
        unsafe_allow_html=True,
    )

    current_lat = st.session_state["lat"]
    current_lon = st.session_state["lon"]

    m_display = folium.Map(location=[current_lat, current_lon], zoom_start=11, tiles="OpenStreetMap")

    folium.Circle(
        location=[current_lat, current_lon],
        radius=500,
        color="darkorange",
        fill=True,
        fill_color="orange",
        fill_opacity=0.8,
        popup=f"Осередок: {substance}, R_A = 0.5 км",
    ).add_to(m_display)

    folium.Polygon(
        locations=sector_coords,
        color="black",
        fill=True,
        fill_color="orange",
        fill_opacity=0.35,
        weight=2,
        popup=f"Глибина: {g_res:.2f} км, Площа: {s_res:.2f} км² (Ф = {phi_res}°)",
    ).add_to(m_display)

    folium.Marker(
        [current_lat, current_lon],
        popup="Джерело аварії",
        icon=folium.Icon(color="red", icon="warning-sign")
    ).add_to(m_display)

    m_display.get_root().html.add_child(folium.Element(get_wind_widget_html(wind_deg, wind_v)))

    map_data = st_folium(m_display, width="100%", height=530, key="folium_map_display")

    if map_data and map_data.get("last_clicked"):
        click_lat = round(map_data["last_clicked"]["lat"], 4)
        click_lon = round(map_data["last_clicked"]["lng"], 4)
        
        if click_lat != st.session_state["lat"] or click_lon != st.session_state["lon"]:
            st.session_state["lat"] = click_lat
            st.session_state["lon"] = click_lon
            st.rerun()

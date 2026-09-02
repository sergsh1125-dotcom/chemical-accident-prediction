import math
import folium
import streamlit as st
from streamlit_folium import st_folium

# ------------------------------------------------------------------------------
# 1. ІМПОРТ З БАЗИ ДАНИХ ТА ЗАХИСТ ВІД ВІДСУТНІХ ЗМІННИХ
# ------------------------------------------------------------------------------
import data_tables

import data_tables

TABLE_G_T1 = getattr(data_tables, "TABLE_G_T1", {})
TABLE_K_T1 = getattr(data_tables, "TABLE_K_T1", {})
G_t2 = getattr(data_tables, "G_t2", {})
K_t2 = getattr(data_tables, "K_t2", {})
TABLE_K_K = getattr(data_tables, "TABLE_K_K", {})
KP_OPTIONS = getattr(data_tables, "KP_OPTIONS", {})
TABLE_K_M = getattr(data_tables, "TABLE_K_M", {})
# 2. ІНІЦІАЛІЗАЦІЯ SESSION STATE
# ------------------------------------------------------------------------------
if "lat" not in st.session_state:
    st.session_state["lat"] = 50.4501
if "lon" not in st.session_state:
    st.session_state["lon"] = 30.5234

if "input_lat" not in st.session_state:
    st.session_state["input_lat"] = st.session_state["lat"]
if "input_lon" not in st.session_state:
    st.session_state["input_lon"] = st.session_state["lon"]

# Словник для збереження нанесеного тексту
if "user_texts" not in st.session_state:
    st.session_state["user_texts"] = []

def update_from_input():
    st.session_state["lat"] = round(st.session_state["input_lat"], 4)
    st.session_state["lon"] = round(st.session_state["input_lon"], 4)

# ------------------------------------------------------------------------------
# РОЗРАХУНКОВІ ФУНКЦІЇ
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

def get_base_depth_with_q(substance, vert_st, q, wind_v):
    """Повертає (г1_base, q_table) для первинної хмари"""
    if substance not in TABLE_G_T1:
        return 0.0, 1.0
    sub_data = TABLE_G_T1[substance]
    if vert_st not in sub_data:
        vert_st = list(sub_data.keys())[0]
    st_data = sub_data[vert_st]
    q_map = {float(k): k for k in st_data.keys()}
    q_keys = sorted(q_map.keys())
    if not q_keys:
        return 0.0, 1.0
    
    # Пошук найближчого табличного значення Qт (за найменшою абсолютною різницею)
    q_target_val = min(q_keys, key=lambda x: abs(x - q))
    q_target_key = q_map[q_target_val]
    
    v_dict = st_data[q_target_key]
    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())
    if not v_keys:
        return 0.0, q_target_val
    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break
    v_target_key = v_map[v_target_val]
    return float(v_dict[v_target_key]), float(q_target_val)

def get_base_depth_gt2_with_q(substance, vert_st, q, wind_v):
    """Повертає (г2_base, q_table) для вторинної хмари"""
    if not G_t2 or substance not in G_t2:
        return 0.0, 1.0
    sub_data = G_t2[substance]
    q_map = {float(k): k for k in sub_data.keys()}
    q_keys = sorted(q_map.keys())
    if not q_keys:
        return 0.0, 1.0
    
    # Пошук найближчого табличного значення Qт (за найменшою абсолютною різницею)
    q_target_val = min(q_keys, key=lambda x: abs(x - q))
    q_target_key = q_map[q_target_val]
    
    if vert_st not in sub_data[q_target_key]:
        return 0.0, q_target_val
    v_dict = sub_data[q_target_key][vert_st]
    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())
    if not v_keys:
        return 0.0, q_target_val
    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break
    v_target_key = v_map[v_target_val]
    return float(v_dict[v_target_key]), float(q_target_val)

def get_kk_factor(q_user, q_table, vert_st):
    """Обчислює відношення Qз/Qт та знаходить Кк за масивом TABLE_K_K"""
    if q_table <= 0:
        return 1.0
    ratio = q_user / q_table
    if TABLE_K_K and vert_st in TABLE_K_K:
        return interpolate_1d(ratio, TABLE_K_K[vert_st])
    return 1.0
def get_km_factor(kp_val, vert_st):
    """Визначає коефіцієнт Km на основі Kp та вертикальної стійкості атмосфери"""
    if TABLE_K_M and vert_st in TABLE_K_M:
        return interpolate_1d(kp_val, TABLE_K_M[vert_st])
    return 1.0
def calculate_zone(substance, vert_st, q, wind_v, temp, is_closed, km_val):
    # 1. Первинна хмара
    g1_base, q1_table = get_base_depth_with_q(substance, vert_st, q, wind_v)
    kt1 = 1.0
    if TABLE_K_T1 and substance in TABLE_K_T1 and TABLE_K_T1[substance]:
        kt1 = interpolate_1d(temp, TABLE_K_T1[substance])
    kk1 = get_kk_factor(q, q1_table, vert_st)
    
    # Формула Г1
    g1 = g1_base * kt1 * kk1 * km_val

    # 2. Вторинна хмара
    gt2_base, q2_table = get_base_depth_gt2_with_q(substance, vert_st, q, wind_v)
    kt2 = 1.0
    if K_t2 and substance in K_t2 and K_t2[substance]:
        kt2 = interpolate_1d(temp, K_t2[substance])
    kk2 = get_kk_factor(q, q2_table, vert_st)
    
    # Коефіцієнт піддону (Кп)
    kp_val = 0.5 if is_closed else 1.0
    
    # Формула Г2
    g2 = gt2_base * kt2 * kk2 * kp_val * km_val

    # 3. Підсумкова глибина та площа
    r_a = 0.5
    g_total = max(g1, g2) + r_a
    
    if vert_st == "Інверсія":
        phi = 40.0
    elif vert_st == "Ізотермія":
        phi = 50.0
    else:
        phi = 70.0
        
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
            d_lon = (r_m * math.cos(angle)) / (111111.0 * math.cos(math.radians(lat)))
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
    <div style="position: fixed; bottom: 30px; left: 20px; z-index: 9999; background-color: #0e0f12; border: 1.5px solid #ffd700; border-radius: 8px; padding: 10px 14px; width: 110px; box-shadow: 0px 4px 10px rgba(0,0,0,0.8); font-family: Arial, sans-serif; color: #ffd700; text-align: center;">
        <div style="font-size: 26px; line-height: 1; margin-bottom: 4px; display: inline-block; transform: rotate({arrow_rotation}deg); color: #ffd700;">↓</div>
        <div style="font-size: 18px; font-weight: bold; color: #ffd700; margin-bottom: 6px;">{int(wind_deg)}°</div>
        <div style="border-top: 1px dashed #ffd700; margin-bottom: 6px;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #ffd700; font-weight: bold; margin-bottom: 2px;"><span>м/с:</span><span style="color: #ffffff;">{wind_v:.1f}</span></div>
        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #ffd700; font-weight: bold;"><span>км/г:</span><span style="color: #ffffff;">{wind_kmh:.1f}</span></div>
    </div>
    """

def setup_map_base(m):
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="супутникова карта", overlay=False, control=True
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap", name="OpenStreetMap", overlay=False, control=True
    ).add_to(m)
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

# ------------------------------------------------------------------------------
# 4. ІНТЕРФЕЙС STREAMLIT СТИЛІЗОВАНИЙ ПІД ПЛАТФОРМУ ХБРЯ
# ------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Прогноз хімічної аварії")

# CSS-СТИЛІЗАЦІЯ ПІД ДИЗАЙН ПЛАТФОРМИ ХБРЯ
st.markdown("""
<style>
    /* Приховуємо стандартні елементи Streamlit */
    #MainMenu {visibility: hidden;} 
    header {visibility: hidden;} 
    footer {visibility: hidden;} 
    .stAppHeader {display: none;}

    /* Загальний темний фон додатка */
    .stApp {
        background-color: #0e0f12;
        color: #ffd700;
    }

    /* Стиль для збільшеної назви застосунку (+2 пункти) */
    .app-title {
        color: #ffd700 !important;
        font-size: 2.2rem !important;
        font-weight: bold;
        margin-bottom: 1.5rem;
    }

    /* Усі тексти, заголовки, підписи — ЖОВТІ */
    h1, h2, h3, h4, h5, h6, label, p, span, div, .stMarkdown {
        color: #ffd700 !important;
    }

    /* Стилізація рамок для контейнерів, форм та блоків */
    [data-testid="stForm"], [data-testid="stMetric"], .stAlert {
        border: 1.5px solid #ffd700 !important;
        border-radius: 6px !important;
        background-color: #14161d !important;
    }

    /* Поля введення з золотою окантовкою */
    div[data-baseweb="select"] > div, 
    div[data-baseweb="input"] > div, 
    div[data-baseweb="base-input"] {
        border: 1px solid #ffd700 !important;
        background-color: #1a1d24 !important;
        color: #ffd700 !important;
        border-radius: 4px !important;
    }

    /* Текст усередині полів введення */
    input, select, textarea {
        color: #ffd700 !important;
        background-color: #1a1d24 !important;
    }

    /* КНОПКИ (Жовта кнопка, Чорний текст) */
    div.stButton > button, button[kind="secondaryFormSubmit"] {
        background-color: #ffcc00 !important;
        border: 1px solid #ffd700 !important;
        border-radius: 5px !important;
        transition: 0.2s;
    }

    div.stButton > button p, button[kind="secondaryFormSubmit"] p {
        color: #000000 !important;
        font-weight: bold !important;
        font-size: 17px !important;
    }

    div.stButton > button:hover, button[kind="secondaryFormSubmit"]:hover {
        background-color: #e6b800 !important;
        box-shadow: 0px 0px 8px #ffd700;
    }

    div[data-testid="stDownloadButton"] > button {
        background-color: #ffcc00 !important;
        border: 1px solid #ffd700 !important;
    }
    div[data-testid="stDownloadButton"] > button p {
        color: #000000 !important;
        font-weight: bold !important;
        font-size: 15px !important;
    }

    span[data-baseweb="checkbox"] > div {
        border-color: #ffd700 !important;
    }

    hr {
        border-color: #ffd700 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-title">Аварійне прогнозування масштабів хімічної аварії</div>', unsafe_allow_html=True)

col_params, col_map = st.columns([1, 2])

with col_params:
    st.subheader("Вхідна інформація")
    all_substances = sorted(list(set(list(TABLE_G_T1.keys()) + list(G_t2.keys()))))
    if not all_substances: all_substances = ["Аміак"]

    with st.form(key="calc_form"):
        substance = st.selectbox("Назва речовини", all_substances)
        q_val = st.number_input("Кількість речовини, т", min_value=0.1, max_value=10000.0, value=10.0, step=1.0)
        vert_st = st.selectbox("Стійкість атмосфери", ["Інверсія", "Ізотермія", "Конвекція"])
        wind_options = [1.0, 2.0, 3.0, 4.0, 10.0] if vert_st == "Ізотермія" else [1.0, 2.0, 3.0, 4.0]
        default_wind_index = 1 if 2.0 in wind_options else 0
        wind_v = st.selectbox("Швидкість вітру, м/с", wind_options, index=default_wind_index, format_func=lambda x: f"{int(x) if float(x).is_integer() else x} м/с")
        wind_deg = st.slider("Напрямок вітру", 0, 360, 90)
        temp = st.slider("Температура повітря, °C", -20, 30, 20)
        
        # ЗАМІНА Km НА ВИБІР КАРТИ МІСЦЕВОСТІ (Kp)
        kp_label = st.selectbox("Характеристика місцевості / ландшафту (Кр)", list(KP_OPTIONS.keys()))
        kp_val = KP_OPTIONS[kp_label]
        
        is_closed = st.checkbox("Наявність піддону або обвалування", value=False)
        submit_btn = st.form_submit_button("РОЗРАХУВАТИ", use_container_width=True)

    st.subheader("Координати ХНО")
    
    st.session_state["input_lat"] = st.session_state["lat"]
    st.session_state["input_lon"] = st.session_state["lon"]

    lat_val = st.number_input("Широта (Lat)", value=st.session_state["input_lat"], format="%.4f", key="input_lat", on_change=update_from_input)
    lon_val = st.number_input("Довгота (Lon)", value=st.session_state["input_lon"], format="%.4f", key="input_lon", on_change=update_from_input)

    allow_click_move = st.checkbox(
        "🖱️ Увімкніть нанесення координат ХНО кліком", 
        value=False, 
        help="Вимкніть цю функцію перед нанесенням тексту на карту."
    )

    # ОБЧИСЛЕННЯ Кm ІЗ Кp ТА ВЕРТИКАЛЬНОЇ СТІЙКОСТІ
    km_val = get_km_factor(kp_val, vert_st)

    g1_base, q1_t = get_base_depth_with_q(substance, vert_st, q_val, wind_v)
    gt2_base, q2_t = get_base_depth_gt2_with_q(substance, vert_st, q_val, wind_v)
    kt1_res = interpolate_1d(temp, TABLE_K_T1.get(substance, {})) if (TABLE_K_T1 and substance in TABLE_K_T1) else 1.0
    kt2_res = interpolate_1d(temp, K_t2.get(substance, {})) if (K_t2 and substance in K_t2) else 1.0
    kk1_res = get_kk_factor(q_val, q1_t, vert_st)
    kk2_res = get_kk_factor(q_val, q2_t, vert_st)
    kp_poddon = 0.5 if is_closed else 1.0

    g1_res = g1_base * kt1_res * kk1_res * km_val
    g2_res = gt2_base * kt2_res * kk2_res * kp_poddon * km_val
    r_a = 0.5
    g_res = max(g1_res, g2_res) + r_a

    if vert_st == "Інверсія": phi_res = 40.0
    elif vert_st == "Ізотермія": phi_res = 50.0
    else: phi_res = 70.0

    s_res = 8.72e-4 * (g_res ** 2) * phi_res

    st.subheader("Результати аварійного прогнозування")
    with st.container():
        st.markdown("**1. Глибина розповсюдження первинної хмари ($Г_1$):**")
        st.latex(r"Г_1 = Г_{\text{табл1}} \cdot K_{t1} \cdot K_k \cdot K_m")
        st.latex(f"Г_1 = {g1_base:.2f} \\cdot {kt1_res:.2f} \\cdot {kk1_res:.2f} \\cdot {km_val:.2f} = \\mathbf{{{g1_res:.2f}}}\\text{{ км}}")

        st.markdown("---")
        st.markdown("**2. Глибина розповсюдження вторинної хмари ($Г_2$):**")
        st.latex(r"Г_2 = Г_{\text{табл2}} \cdot K_{t2} \cdot K_k \cdot K_п \cdot K_m")
        st.latex(f"Г_2 = {gt2_base:.2f} \\cdot {kt2_res:.2f} \\cdot {kk2_res:.2f} \\cdot {kp_poddon:.2f} \\cdot {km_val:.2f} = \\mathbf{{{g2_res:.2f}}}\\text{{ км}}")

        st.markdown("---")
        st.markdown("**3. Загальна глибина зони забруднення ($Г$):**")
        st.latex(r"Г = \max(Г_1, Г_2) + R_a")
        st.latex(f"Г = \\max({g1_res:.2f}, {g2_res:.2f}) + {r_a:.1f} = \\mathbf{{{g_res:.2f}}}\\text{{ км}}")

        st.markdown("---")
        st.markdown("**4. Площа прогнозованої зони хімічного забруднення ($S$):**")
        st.latex(r"S = 8.72 \cdot 10^{-4} \cdot Г^2 \cdot \phi")
        st.latex(f"S = 8.72 \\cdot 10^{{-4}} \\cdot ({g_res:.2f})^2 \\cdot {phi_res:.0f} = \\mathbf{{{s_res:.2f}}}\\text{{ км}}²")

    # Створення карти для експорту
    m_export = folium.Map(location=[st.session_state["lat"], st.session_state["lon"]], zoom_start=11, tiles=None)
    setup_map_base(m_export)
    
    for txt_data in st.session_state["user_texts"]:
        folium.Marker(
            [txt_data["lat"], txt_data["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="color: #000000; font-weight: bold; font-size: 15px; background: transparent; padding: 0px; border: none; white-space: nowrap;">{txt_data["text"]}</div>'
            )
        ).add_to(m_export)

    folium.Circle(location=[st.session_state["lat"], st.session_state["lon"]], radius=500, color="darkorange", fill=True, fill_color="orange", fill_opacity=0.8).add_to(m_export)
    sector_coords = create_sector_geojson(st.session_state["lat"], st.session_state["lon"], g_res, wind_deg, phi_res)
    folium.Polygon(locations=sector_coords, color="black", fill=True, fill_color="orange", fill_opacity=0.35, weight=2).add_to(m_export)
    m_export.get_root().html.add_child(folium.Element(get_wind_widget_html(wind_deg, wind_v)))
    
    st.download_button(
        label="📥 Завантажити HTML карту",
        data=m_export._repr_html_().encode("utf-8"),
        file_name="карта_забруднення.html",
        mime="text/html"
    )

with col_map:
    st.markdown(
        f"""
    <div style="background-color: #14161d; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; border: 1.5px solid #ffd700; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px; line-height: 1.2;">
        <div style="font-size: 15px; font-weight: bold; color: #ffd700; margin: 0;">
            Глибина прогнозованої зони хімічного забруднення: <span style="color: #ffffff; font-size: 16px;">{g_res:.2f} км</span>
        </div>
        <div style="font-size: 15px; font-weight: bold; color: #ffd700; margin: 0;">
            Площа прогнозованої зони хімічного забруднення: <span style="color: #ffffff; font-size: 16px;">{s_res:.2f} км²</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    current_lat = st.session_state["lat"]
    current_lon = st.session_state["lon"]

    m_display = folium.Map(location=[current_lat, current_lon], zoom_start=11, tiles=None)
    setup_map_base(m_display)
    
    for txt_data in st.session_state["user_texts"]:
        folium.Marker(
            [txt_data["lat"], txt_data["lon"]],
            icon=folium.DivIcon(
                html=f'<div style="color: #000000; font-weight: bold; font-size: 15px; background: transparent; padding: 0px; border: none; white-space: nowrap;">{txt_data["text"]}</div>'
            )
        ).add_to(m_display)
    
    folium.Circle(location=[current_lat, current_lon], radius=500, color="darkorange", fill=True, fill_color="orange", fill_opacity=0.8).add_to(m_display)
    folium.Polygon(locations=sector_coords, color="black", fill=True, fill_color="orange", fill_opacity=0.35, weight=2).add_to(m_display)
    m_display.get_root().html.add_child(folium.Element(get_wind_widget_html(wind_deg, wind_v)))

    map_data = st_folium(m_display, width="100%", height=530, key="main_map")    # --------------------------------------------------------------------------
    # ПАНЕЛЬ НАНЕСЕННЯ ТЕКСТУ
    # --------------------------------------------------------------------------
    st.divider()
    st.subheader("Додавання тексту на карту")
    st.markdown("1. Переконайтесь, що галочка визначення координат кліком вимкнена (у лівому меню).\n2. **Клікніть мишкою** на карті там, де має бути текст.\n3. Введіть текст у поле нижче та натисніть 'Додати'.")
    
    if map_data and map_data.get("last_clicked"):
        c_lat = round(map_data["last_clicked"]["lat"], 4)
        c_lon = round(map_data["last_clicked"]["lng"], 4)
        
        st.success(f"📍 Вибрана точка для тексту: Широта {c_lat}, Довгота {c_lon}")
        
        with st.form(key="text_add_form", clear_on_submit=True):
            col_text, col_btn = st.columns([3, 1])
            with col_text:
                new_text = st.text_input("Введіть текст:", placeholder="Наприклад: хлор - 10 т")
            with col_btn:
                st.write("") 
                st.write("") 
                submitted = st.form_submit_button("➕ Додати")
            
            if submitted and new_text.strip():
                st.session_state["user_texts"].append({
                    "lat": c_lat,
                    "lon": c_lon,
                    "text": new_text.strip()
                })
                st.rerun()

    if st.session_state.get("user_texts"):
        if st.button("Очистити всі нанесені тексти"):
            st.session_state["user_texts"] = []
            st.rerun()

    # Зміна координат осередку, якщо увімкнено чекбокс
    if allow_click_move and map_data and map_data.get("last_clicked"):
        click_lat = round(map_data["last_clicked"]["lat"], 4)
        click_lon = round(map_data["last_clicked"]["lng"], 4)
        
        if click_lat != st.session_state["lat"] or click_lon != st.session_state["lon"]:
            st.session_state["lat"] = click_lat
            st.session_state["lon"] = click_lon
            st.rerun()

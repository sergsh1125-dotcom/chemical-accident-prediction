import math
import folium
import streamlit as st
from streamlit_folium import st_folium

# ------------------------------------------------------------------------------
# 1. ІМПОРТ З БАЗИ ДАНИХ ТА ЗАХИСТ ВІД ВІДСУТНІХ ЗМІННИХ
# ------------------------------------------------------------------------------
import data_tables

# Обов'язкові бази
TABLE_G_T1 = getattr(data_tables, "TABLE_G_T1", {})
TABLE_K_T1 = getattr(data_tables, "TABLE_K_T1", {})

# Допоміжні бази (якщо вони ще не додані в data_tables.py — беруться значення за замовчуванням)
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
# 2. ДОПОМІЖНІ ФУНКЦІЇ ТА РОЗРАХУНКОВА ЛОГІКА
# ------------------------------------------------------------------------------

def interpolate_1d(val, points):
    """Лінійна інтерполяція значень за словником {х: y}."""
    if not points:
        return 1.0
    sorted_keys = sorted(points.keys())
    if val <= sorted_keys[0]:
        return points[sorted_keys[0]]
    if val >= sorted_keys[-1]:
        return points[sorted_keys[-1]]
    for i in range(len(sorted_keys) - 1):
        x0, x1 = sorted_keys[i], sorted_keys[i + 1]
        if x0 <= val <= x1:
            y0, y1 = points[x0], points[x1]
            return y0 + (y1 - y0) * (val - x0) / (x1 - x0)
    return 1.0


def get_base_depth(substance, vert_st, q, wind_v):
    """
    Отримання базової глибини первинної хмари (Г_Т1).
    Працює як з числовими (float/int), так і з рядковими ключами словника.
    """
    if substance not in TABLE_G_T1:
        return 1.0
    sub_data = TABLE_G_T1[substance]

    if vert_st not in sub_data:
        vert_st = list(sub_data.keys())[0]
    st_data = sub_data[vert_st]

    # Створюємо мапу: float_value -> original_key
    q_map = {float(k): k for k in st_data.keys()}
    q_keys = sorted(q_map.keys())

    if not q_keys:
        return 1.0

    q_target_val = q_keys[0]
    for q_k in q_keys:
        if q >= q_k:
            q_target_val = q_k
        else:
            break

    q_target_str = q_map[q_target_val]
    v_dict = st_data[q_target_str]

    # Пошук за швидкістю вітру
    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())

    if not v_keys:
        return 1.0

    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break

    v_target_str = v_map[v_target_val]
    return float(v_dict[v_target_str])


def get_base_depth_gt2(substance, vert_st, q, wind_v):
    """Отримання базової глибини вторинної хмари (Г_Т2) з бази G_t2."""
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

    q_target_str = q_map[q_target_val]

    if vert_st not in sub_data[q_target_str]:
        return 0.0

    v_dict = sub_data[q_target_str][vert_st]

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

    v_target_str = v_map[v_target_val]
    return float(v_dict[v_target_str])


def calculate_zone(substance, vert_st, q, wind_v, temp, is_closed, km_val):
    # --- 1. Первинна хмара (Г1) ---
    g1_base = get_base_depth(substance, vert_st, q, wind_v)
    kt1 = 1.0
    if substance in TABLE_K_T1:
        kt1 = interpolate_1d(temp, TABLE_K_T1[substance])

    g1 = g1_base * kt1 * km_val

    # --- 2. Вторинна хмара (Г2) ---
    gt2_base = get_base_depth_gt2(substance, vert_st, q, wind_v)
    kt2 = 1.0
    if K_t2 and substance in K_t2:
        kt2 = interpolate_1d(temp, K_t2[substance])

    kk_val = 0.5 if is_closed else 1.0  # Коефіцієнт Кк (закрита ємність / піддон)
    g2 = gt2_base * kt2 * kk_val * km_val

    # --- 3. Загальна глибина (Г) ---
    r_a = 0.5  # Радіус джерела аварії (км)
    g_total = max(g1, g2) + r_a

    # --- 4. Кут розповсюдження (Ф) ---
    if vert_st == "Інверсія":
        phi = 40.0
    elif vert_st == "Ізотермія":
        phi = 50.0
    else:  # Конвекція
        phi = 70.0

    return g_total, g1, g2, phi, kt1, kt2


def create_sector_geojson(lat, lon, radius_km, wind_deg, phi_deg):
    r_m = radius_km * 1000.0
    target_deg = (wind_deg + 180.0) % 360.0  # Напрямок, куди дме вітер

    if phi_deg >= 360.0:
        points = []
        num_pts = 60
        for i in range(num_pts + 1):
            angle = math.radians(i * (360.0 / num_pts))
            d_lat = (r_m * math.cos(angle)) / 111111.0
            d_lon = (r_m * math.sin(angle)) / (
                111111.0 * math.cos(math.radians(lat))
            )
            points.append([lat + d_lat, lon + d_lon])
        return points

    half_phi = phi_deg / 2.0
    start_angle = target_deg - half_phi
    end_angle = target_deg + half_phi

    points = [[lat, lon]]
    num_pts = 30
    for i in range(num_pts + 1):
        ang_deg = start_angle + i * (end_angle - start_angle) / num_pts
        ang_rad = math.radians(ang_deg)
        d_lat = (r_m * math.cos(ang_rad)) / 111111.0
        d_lon = (r_m * math.sin(ang_rad)) / (
            111111.0 * math.cos(math.radians(lat))
        )
        points.append([lat + d_lat, lon + d_lon])
    points.append([lat, lon])
    return points


# ------------------------------------------------------------------------------
# 3. ІНТЕРФЕЙС ТА ВІДОБРАЖЕННЯ
# ------------------------------------------------------------------------------

st.set_page_config(layout="wide", page_title="Прогноз хімічної аварії")

st.title("🧪 Аварійний прогноз масштабів хімічної аварії")

col_params, col_map = st.columns([1, 2])

with col_params:
    st.subheader("⚙️ Вхідні дані хімічної аварії")

    substances_list = list(TABLE_G_T1.keys()) if TABLE_G_T1 else ["Аміак"]
    substance = st.selectbox("Назва НХР", substances_list)

    q_val = st.number_input(
        "Кількість НХР, т", min_value=0.1, max_value=10000.0, value=10.0, step=1.0
    )
    vert_st = st.selectbox(
        "Стійкість атмосфери", ["Інверсія", "Ізотермія", "Конвекція"]
    )

    # Формування списку доступних швидкостей вітру
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

    wind_deg = st.slider("Звідки дме вітер (напрямок, градуси)", 0, 360, 90)
    temp = st.slider("Температура повітря, °C", -20, 30, 20)

    km_label = st.selectbox("Коефіцієнт місцевості (Км)", list(KM_OPTIONS.keys()))
    km_val = KM_OPTIONS[km_label]

    is_closed = st.checkbox("Закрита ємність / піддон", value=False)

    st.subheader("📍 Координати хімічно небезпечного об'єкта")
    lat = st.number_input("Широта (Lat)", value=50.4501, format="%.4f")
    lon = st.number_input("Довгота (Lon)", value=30.5234, format="%.4f")

    # Розрахунок результатів
    g_res, g1_res, g2_res, phi_res, kt1_res, kt2_res = calculate_zone(
        substance, vert_st, q_val, wind_v, temp, is_closed, km_val
    )

    st.subheader("📊 Результати розрахунку")
    st.info(
        f"**Глибина зони хімічного забруднення (Г): {g_res:.2f} км**\n\n"
        f"• Первинна хмара (Г₁): **{g1_res:.2f} км** (Kₜ₁ = {kt1_res:.2f})\n\n"
        f"• Вторинна хмара (Г₂): **{g2_res:.2f} км** (Kₜ₂ = {kt2_res:.2f})\n\n"
        f"• Радіус осередку аварії (Rₐ): **0.50 км**\n\n"
        f"• Кут сектора ураження (Ф): **{phi_res}°**"
    )

with col_map:
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="OpenStreetMap")

    # Інформаційна панель на карті
    st.markdown(
        f"""
    <div style="background-color: #f0f2f6; padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 5px solid #ff4b4b;">
        <h4 style="margin: 0; color: #1f2937;">Глибина зони хімічного забруднення (Г): 
        <span style="color: #d97706; font-size: 1.2em;">{g_res:.2f} км</span></h4>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # 1. Радіус джерела аварії (R_a = 0.5 км)
    folium.Circle(
        location=[lat, lon],
        radius=500,
        color="darkorange",
        fill=True,
        fill_color="orange",
        fill_opacity=0.8,
        popup=f"Осередок: {substance}, R_A = 0.5 км",
    ).add_to(m)

    # 2. Зона хімічного забруднення
    sector_coords = create_sector_geojson(lat, lon, g_res, wind_deg, phi_res)

    folium.Polygon(
        locations=sector_coords,
        color="black",
        fill=True,
        fill_color="orange",
        fill_opacity=0.35,
        weight=2,
        popup=f"Глибина зони хімічного забруднення: {g_res:.2f} км (Ф = {phi_res}°)",
    ).add_to(m)

    st_folium(m, width="100%", height=650)

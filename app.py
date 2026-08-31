import math
import folium
import streamlit as st
from streamlit_folium import st_folium

# Налаштування сторінки Streamlit
st.set_page_config(
    layout="wide", page_title="Аварійний прогноз масштабів хімічної аварії"
)

st.markdown(
    """
    <style>
        .block-container {
            padding-right: 1rem;
            padding-left: 1rem;
            max-width: 100%;
        }
    </style>
""",
    unsafe_allow_html=True,
)



# ==============================================================================
# 2. ПОВНА ТАБЛИЧНА МАТРИЦЯ БАЗОВИХ ГЛИБИН Г_Т2 (км) ЗГІДНО З ДОДАТКОМ 2
# ==============================================================================

TABLE_G_T2 = {
    "Аміак": {
        "Інверсія": {1.0: {1.0: 0.04, 2.0: 0.03, 3.0: 0.02, 4.0: 0.01}}
    }
}

# Простий інтерфейс для перевірки карти
m = folium.Map(location=[50.4501, 30.5234], zoom_start=10)
st_folium(m, width="100%", height=500)
TABLE_K_T1 = {
    "Аміак": {-20.0: 0.5, -10.0: 0.7, 0.0: 0.8, 10.0: 0.9, 20.0: 1.0, 30.0: 1.4},
    "Бромоводень": {-20.0: 0.5, -10.0: 0.7, 0.0: 0.8, 10.0: 0.9, 20.0: 1.0, 30.0: 1.2},
    "Бромометан": {-20.0: 0.0, -10.0: 0.0, 0.0: 0.0, 10.0: 0.5, 20.0: 1.0, 30.0: 2.3},
    "Хлор": {-20.0: 0.4, -10.0: 0.6, 0.0: 0.8, 10.0: 0.9, 20.0: 1.0, 30.0: 1.3},
}

# Словник коефіцієнтів місцевості (Км)
KM_OPTIONS = {
    "1.0 — Відкрита місцевість": 1.0,
    "0.5 — Сільська забудова / лісисто-степова": 0.5,
    "0.4 — Міська забудова / ліс": 0.4,
    
}

# Коефіцієнт Kt2 залежно від температури повітря
# Джерело: Додаток 10
K_t2 = {
    "Акролеїн": { "-20": 0.2, "-10": 0.4, "0": 0.4, "10": 0.8, "20": 1.0, "30": 2.2 },
    "Аміак (ізотермічний)": { "-20": 0.6, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.2 },
    "Аміак (під тиском)": { "-20": 0.6, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.1 },
    "Ацетонітрил": { "-20": 0.1, "-10": 0.3, "0": 0.3, "10": 0.8, "20": 1.0, "30": 2.6 },
    "Бромоводень": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Бромометан": { "-20": 0.4, "-10": 0.9, "0": 0.9, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Диметиламін": { "-20": 0.3, "-10": 0.6, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.0 },
    "Миш'яковистий водень": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Оксид азоту": { "-20": 0, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.0 },
    "Оксид етилену": { "-20": 0.3, "-10": 0.4, "0": 0.5, "10": 0.6, "20": 0.7, "30": 0.9 },
    "Оксихлорид фосфору": { "-20": 0.1, "-10": 0.7, "0": 0.7, "10": 0.9, "20": 1.0, "30": 2.6 },
    "Сірководень": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Сірчистий ангідрид (діоксин сірки)": { "-20": 0.6, "-10": 0.7, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.1 },
    "Синильна кислота (ціанистий водень)": { "-20": 0.6, "-10": 0.6, "0": 0.9, "10": 1.0, "20": 1.3, "30": 1.3 },
    "Соляна кислота (хлористий водень)": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Трихлорид фосфору": { "-20": 0.2, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 2.3 },
    "Формальдегід (формалін)": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Фосген": { "-20": 0.8, "-10": 0.3, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.0 },
    "Фтор": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.0 },
    "Фтороводень": { "-20": 0.4, "-10": 0.5, "0": 0.6, "10": 0.7, "20": 0.8, "30": 1.0 },
    "Хлор (ізотермічний)": { "-20": 0.6, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.2 },
    "Хлор (під тиском)": { "-20": 1.0, "-10": 1.0, "0": 1.0, "10": 1.0, "20": 1.0, "30": 1.1 },
    "Хлорпікрін": { "-20": 0.1, "-10": 0.2, "0": 0.3, "10": 0.7, "20": 1.0, "30": 2.9 },
    "Хлорціан": { "-20": 0, "-10": 0.7, "0": 0.8, "10": 0.9, "20": 1.0, "30": 1.0 }
};

import math
import streamlit as st
import folium
from streamlit_folium import st_folium

# ==============================================================================
# 2. ДОПОМІЖНІ ФУНКЦІЕС ТА РОЗРАХУНКОВА ЛОГІКА
# ==============================================================================

def interpolate_1d(val, points):
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

def get_base_depth(substance, vert_st, q, wind_v):
    if substance not in TABLE_G_T1:
        return 1.0
    sub_data = TABLE_G_T1[substance]
    if vert_st not in sub_data:
        vert_st = list(sub_data.keys())[0]
    st_data = sub_data[vert_st]
    
    # Створюємо мапу: float_value -> original_string_key
    q_map = {float(k): k for k in st_data.keys()}
    q_keys = sorted(q_map.keys())
    
    q_target_val = q_keys[0]
    for q_k in q_keys:
        if q >= q_k:
            q_target_val = q_k
        else:
            break
            
    # Отримуємо оригінальний ключ для звернення до словника
    q_target_str = q_map[q_target_val]
    v_dict = st_data[q_target_str]
    
    # Аналогічно для швидкості вітру
    v_map = {float(k): k for k in v_dict.keys()}
    v_keys = sorted(v_map.keys())
    
    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break
            
    v_target_str = v_map[v_target_val]
    return v_dict[v_target_str]


def get_base_depth_gt2(substance, vert_st, q, wind_v):
    """Отримання Г_Т2 з матриці вторинної хмари G_t2"""
    if 'G_t2' not in globals() or substance not in G_t2:
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
    
    v_target_val = v_keys[0]
    for v_k in v_keys:
        if wind_v >= v_k:
            v_target_val = v_k
        else:
            break
            
    v_target_str = v_map[v_target_val]
    return v_dict[v_target_str]
def calculate_zone(substance, vert_st, q, wind_v, temp, is_closed, km_val):
    # --- 1. Обчислення первинної хмари (Г1) ---
    g1_base = get_base_depth(substance, vert_st, q, wind_v)
    kt1 = 1.0
    if substance in TABLE_K_T1:
        kt1 = interpolate_1d(temp, TABLE_K_T1[substance])
        
    g1 = g1_base * kt1 * km_val
    
    # --- 2. Обчислення вторинної хмари (Г2) ---
    gt2_base = get_base_depth_gt2(substance, vert_st, q, wind_v)
    
    kt2 = 1.0
    if 'K_t2' in globals() and substance in K_t2:
        kt2 = interpolate_1d(temp, K_t2[substance])
        
    kk_val = 0.5 if is_closed else 1.0  # Коефіцієнт Кк (закрита ємність / піддон)
    g2 = gt2_base * kt2 * kk_val * km_val
    
    # --- 3. Визначення загальної глибини (Г) ---
    r_a = 0.5  # Радіус джерела / аварії (км)
    g_total = max(g1, g2) + r_a
    
    # --- 4. Кут розповсюдження (Ф) залежно від стійкості повітря ---
    if vert_st == "Інверсія":
        phi = 40.0
    elif vert_st == "Ізотермія":
        phi = 50.0
    else:  # Конвекція
        phi = 70.0
        
    return g_total, g1, g2, phi

def create_sector_geojson(lat, lon, radius_km, wind_deg, phi_deg):
    r_m = radius_km * 1000.0
    target_deg = (wind_deg + 180.0) % 360.0  # Напрямок, куди дме вітер
    
    if phi_deg >= 360.0:
        points = []
        num_pts = 60
        for i in range(num_pts + 1):
            angle = math.radians(i * (360.0 / num_pts))
            d_lat = (r_m * math.cos(angle)) / 111111.0
            d_lon = (r_m * math.sin(angle)) / (111111.0 * math.cos(math.radians(lat)))
            points.append([lat + d_lat, lon + d_lon])
        return [points]

    half_phi = phi_deg / 2.0
    start_angle = target_deg - half_phi
    end_angle = target_deg + half_phi
    
    points = [[lat, lon]]
    num_pts = 30
    for i in range(num_pts + 1):
        ang_deg = start_angle + i * (end_angle - start_angle) / num_pts
        ang_rad = math.radians(ang_deg)
        d_lat = (r_m * math.cos(ang_rad)) / 111111.0
        d_lon = (r_m * math.sin(ang_rad)) / (111111.0 * math.cos(math.radians(lat)))
        points.append([lat + d_lat, lon + d_lon])
    points.append([lat, lon])
    return [points]

# ==============================================================================
# 3. ІНТЕРФЕЙС ТА ВІДОБРАЖЕННЯ
# ==============================================================================

st.title("Аварійний прогноз масштабів хімічної аварії")

col_params, col_map = st.columns([1, 2])

with col_params:
    st.subheader("Вхідні дані хімічної аварії")
    substance = st.selectbox("Назва НХР", list(TABLE_G_T1.keys()))
    q_val = st.number_input("Кількість НХР, т", min_value=0.1, value=10.0, step=1.0)
    vert_st = st.selectbox("Стійкість атмосфери", ["Інверсія", "Ізотермія", "Конвекція"])
    
    # 1. СПОЧАТКУ створюємо змінну wind_v (залежно від vert_st)
    if vert_st == "Ізотермія":
        wind_options = [1.0, 2.0, 3.0, 4.0, 10.0]
    else:
        wind_options = [1.0, 2.0, 3.0, 4.0]
        
    default_wind_index = 1 if 2.0 in wind_options else 0
    wind_v = st.selectbox(
        "Швидкість вітру, м/с", 
        wind_options, 
        index=default_wind_index,
        format_func=lambda x: f"{int(x) if x.is_integer() else x} м/с"
    )
    
    wind_deg = st.slider("Звідки дме вітер (напрямок, градуси)", 0, 360, 90)
    temp = st.slider("Температура повітря, °C", -20, 30, 20)
    
    km_label = st.selectbox("Коефіцієнт місцевості (Км)", list(KM_OPTIONS.keys()))
    km_val = KM_OPTIONS[km_label]
    
    is_closed = st.checkbox("Закрита ємність / піддон", value=False)
    
    st.subheader("Координати хімічно небезпечного об'єкта")
    lat = st.number_input("Широта", value=50.4501, format="%.4f")
    lon = st.number_input("Довгота", value=30.5234, format="%.4f")
    
    # 2. ПОТІМ викликаємо розрахунок, коли змінні вже існують
    g_res, g1_res, g2_res, phi_res = calculate_zone(substance, vert_st, q_val, wind_v, temp, is_closed, km_val)
    
    st.subheader("Результати розрахунку")
    st.info(
        f"**Глибина зони хімічного забруднення (Г): {g_res:.2f} км**\n\n"
        f"• Первинна глибина (Г₁): {g1_res:.2f} км\n\n"
        f"• Вторинна глибина (Г₂): {g2_res:.2f} км\n\n"
        f"• Кут сектора (Ф): {phi_res}°"
    )
with col_map:
    m = folium.Map(location=[lat, lon], zoom_start=11)
    
    # Інформаційна панель на карті
    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 5px solid #ff4b4b;">
        <h4 style="margin: 0; color: #1f2937;">Глибина зони хімічного забруднення (Г): 
        <span style="color: #d97706; font-size: 1.2em;">{g_res:.2f} км</span></h4>
    </div>
    """, unsafe_allow_html=True)
    
    # Позначення джерела витоку (R = 0.5 км)
    folium.Circle(
        location=[lat, lon],
        radius=500,
        color="darkorange",
        fill=True,
        fill_color="orange",
        fill_opacity=0.8,
        popup=f"ХНО ({substance}), R_A = 0.5 км"
    ).add_to(m)
    
    # Побудова та окантовка зони забруднення
    sector_coords = create_sector_geojson(lat, lon, g_res, wind_deg, phi_res)
    
    folium.Polygon(
        locations=sector_coords,
        color="black",
        fill=True,
        fill_color="orange",
        fill_opacity=0.35,
        weight=2,
        popup=f"Глибина зони хімічного забруднення: {g_res:.2f} км"
    ).add_to(m)
    
    st_folium(m, width="100%", height=650)

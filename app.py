import math
import folium
import streamlit as st
from streamlit_folium import st_folium

# ІМПОРТ НОРМАТИВНИХ ТАБЛИЦЬ З ОКРЕМОГО МОДУЛЯ
from data_tables import TABLE_G_T1, TABLE_K_T1

# ------------------------------------------------------------------------------
# 1. НАЛАШТУВАННЯ СТОРІНКИ
# ------------------------------------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Аварійний прогноз масштабів хімічної аварії"
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

# ------------------------------------------------------------------------------
# 2. РОЗРАХУНКОВІ ФУНКЦІЇ (ОБРОБКА ПОМИЛОК ТА ІНТЕРПОЛЯЦІЯ)
# ------------------------------------------------------------------------------
def get_closest_val(val, val_list):
    """Шукає найближчий числовий ключ із доступної сітки параметрів."""
    return min(val_list, key=lambda x: abs(x - val))

def calculate_depth(substance, atmosphere, quantity, wind_speed, temp):
    """
    Безопечно обчислює розрахункову глибину розповсюдження хмари Г (км).
    Захищено від KeyError за допомогою виклику резервних стандартних значень.
    """
    # Перевірка наявності речовини
    subst_data = TABLE_G_T1.get(substance, TABLE_G_T1.get("Аміак"))
    # Перевірка наявності стану атмосфери
    atmos_data = subst_data.get(atmosphere, subst_data.get("Ізотермія"))

    # Пошук найближчих ключів для кількості речовини та швидкості вітру
    qty_key = get_closest_val(quantity, list(atmos_data.keys()))
    wind_key = get_closest_val(wind_speed, list(atmos_data[qty_key].keys()))

    g_t1 = atmos_data[qty_key][wind_key]

    # Температурний коефіцієнт K_t1
    kt1_data = TABLE_K_T1.get(substance, TABLE_K_T1.get("Аміак"))
    temp_key = get_closest_val(temp, list(kt1_data.keys()))
    k_t1 = kt1_data[temp_key]

    return g_t1 * k_t1

def calculate_sector_angle(wind_speed):
    """Визначає кут сектора можливого зараження залежно від швидкості вітру."""
    if wind_speed < 0.5:
        return 360
    elif wind_speed < 1.0:
        return 180
    elif wind_speed < 2.0:
        return 90
    else:
        return 45

def get_destination_point(lat, lon, distance_km, bearing_deg):
    """Обчислює нову географічну точку за відстані та азимутом."""
    r = 6371.0
    bearing = math.radians(bearing_deg)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    dest_lat = math.asin(
        math.sin(lat_rad) * math.cos(distance_km / r)
        + math.cos(lat_rad) * math.sin(distance_km / r) * math.cos(bearing)
    )
    dest_lon = lon_rad + math.atan2(
        math.sin(bearing) * math.sin(distance_km / r) * math.cos(lat_rad),
        math.cos(distance_km / r) - math.sin(lat_rad) * math.sin(dest_lat),
    )
    return math.degrees(dest_lat), math.degrees(dest_lon)

# ------------------------------------------------------------------------------
# 3. ІНТЕРФЕЙС КОРИСТУВАЧА
# ------------------------------------------------------------------------------
st.title("🧪 Аварійний прогноз масштабів хімічного ураження")

with st.sidebar:
    st.header("⚙️ Вхідні параметри")
    
    # Динамічне формування списку речовин на основі ключів бази даних
    substance_list = list(TABLE_G_T1.keys())
    substance = st.selectbox("Небезпечна речовина", substance_list)
    
    quantity = st.number_input("Кількість речовини (тонн)", min_value=0.1, max_value=10000.0, value=10.0, step=1.0)
    atmosphere = st.selectbox("Стан атмосфери", ["Інверсія", "Ізотермія", "Конвекція"])
    wind_speed = st.slider("Швидкість вітру (м/с)", min_value=0.0, max_value=15.0, value=2.0, step=0.5)
    wind_direction = st.slider("Напрямок вітру (азимут, °)", min_value=0, max_value=360, value=45, step=5)
    temperature = st.slider("Температура повітря (°C)", min_value=-20, max_value=30, value=20, step=10)

    st.subheader("📍 Координати джерела аварії")
    lat_input = st.number_input("Широта (Lat)", value=50.4501, format="%.4f")
    lon_input = st.number_input("Довгота (Lon)", value=30.5234, format="%.4f")

# ------------------------------------------------------------------------------
# 4. ОБЧИСЛЕННЯ ТА ВІДОБРАЖЕННЯ МЕТРИК
# ------------------------------------------------------------------------------
g_depth = calculate_depth(substance, atmosphere, quantity, wind_speed, temperature)
sector_angle = calculate_sector_angle(wind_speed)

if sector_angle == 360:
    area_possible = math.pi * (g_depth**2)
else:
    area_possible = 0.5 * 0.0524 * (g_depth**2) * sector_angle

col1, col2, col3 = st.columns(3)
col1.metric("Глибина зони (Г)", f"{g_depth:.2f} км")
col2.metric("Кут сектора ураження", f"{sector_angle}°")
col3.metric("Площа можливого зараження", f"{area_possible:.2f} км²")

# ------------------------------------------------------------------------------
# 5. КАРТОГРАФІЯ (FOLIUM)
# ------------------------------------------------------------------------------
m = folium.Map(location=[lat_input, lon_input], zoom_start=11, tiles="OpenStreetMap")

folium.Marker(
    [lat_input, lon_input],
    popup=f"Осередок: {substance} ({quantity} т)",
    icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
).add_to(m)

if sector_angle == 360:
    folium.Circle(
        location=[lat_input, lon_input],
        radius=g_depth * 1000.0,
        color="crimson",
        fill=True,
        fill_opacity=0.35,
        popup=f"Кругова зона зараження (Г = {g_depth:.2f} км)",
    ).add_to(m)
else:
    polygon_points = [[lat_input, lon_input]]
    start_angle = wind_direction - (sector_angle / 2.0)
    end_angle = wind_direction + (sector_angle / 2.0)

    steps = 30
    for i in range(steps + 1):
        angle = start_angle + (end_angle - start_angle) * i / steps
        pt = get_destination_point(lat_input, lon_input, g_depth, angle)
        polygon_points.append(pt)

    polygon_points.append([lat_input, lon_input])

    folium.Polygon(
        locations=polygon_points,
        color="red",
        fill=True,
        fill_color="crimson",
        fill_opacity=0.35,
        popup=f"Сектор зараження {sector_angle}° (Азимут: {wind_direction}°)",
    ).add_to(m)

st_folium(m, width="100%", height=600)

import math
import folium
from folium.plugins import Draw
from jinja2 import Template
import streamlit as st
from streamlit_folium import st_folium

# ------------------------------------------------------------------------------
# 1. СТВОРЕННЯ НАТИВНОГО КЛАСУ ДЛЯ КНОПКИ "ТЕКСТ" (Працює всередині Streamlit)
# ------------------------------------------------------------------------------
class LeafletTextTool(folium.MacroElement):
    def __init__(self):
        super().__init__()
        self._template = Template("""
            {% macro script(this, kwargs) %}
            (function() {
                var map = {{ this._parent.get_name() }};
                
                var textControl = L.control({position: 'topleft'});
                textControl.onAdd = function (map) {
                    var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    div.innerHTML = '<a href="#" title="Додати текст" style="font-weight: bold; font-size: 16px; line-height: 28px; text-align: center; display: block; width: 30px; height: 30px; background: #ffffff; color: #111111; text-decoration: none;">Т</a>';
                    
                    div.onclick = function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        var text = prompt("Введіть текст для нанесення на карту:");
                        if (text && text.trim() !== "") {
                            map.once('click', function(mapClickEvent) {
                                var textIcon = L.divIcon({
                                    className: 'custom-text-label',
                                    html: '<div style="font-weight: bold; color: #ffffff; text-shadow: 2px 2px 3px #000, -2px -2px 3px #000, 2px -2px 3px #000, -2px 2px 3px #000; font-size: 15px; white-space: nowrap;">' + text + '</div>',
                                    iconSize: [120, 20],
                                    iconAnchor: [10, 10]
                                });
                                L.marker(mapClickEvent.latlng, {icon: textIcon}).addTo(map);
                            });
                        }
                    };
                    return div;
                };
                textControl.addTo(map);
            })();
            {% endmacro %}
        """)

# ------------------------------------------------------------------------------
# 2. НАЛАШТУВАННЯ КАРТИ ТА ІНСТРУМЕНТІВ
# ------------------------------------------------------------------------------
def setup_map_base_and_tools(m):
    # 1. Супутникова карта (перша за замовчуванням)
    satellite = folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="супутникова карта",
        overlay=False,
        control=True
    )
    satellite.add_to(m)

    # 2. OpenStreetMap (без підкладки дефолтної карти)
    osm = folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap contributors",
        name="OpenStreetMap",
        overlay=False,
        control=True
    )
    osm.add_to(m)

    # Додаємо панель керування шарами
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    # 3. Інструменти малювання (Polyline, Polygon, Circle, Rectangle)
    draw = Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": True,
            "circle": True,
            "rectangle": True,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"poly": {"allowIntersection": False}}
    )
    draw.add_to(m)

    # 4. Вбудовуємо кнопку "Текст" безпосередньо в об'єкт Leaflet
    m.add_child(LeafletTextTool())

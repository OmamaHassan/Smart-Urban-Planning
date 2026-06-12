import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely import wkt
import folium
from streamlit_folium import st_folium
import plotly.express as px
import json

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide", page_icon="📍")

# ==============================
# GLOBAL CSS
# ==============================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600;700;800&display=swap');

html, body, [class*="css"], [class*="st-"], button, input, select, textarea {
    font-family: 'Nunito', sans-serif !important;
}

/* KPI cards */
[data-testid="stMetric"] {
    border: 1.5px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 20px;
    background: rgba(128, 128, 128, 0.06);
    text-align: center;
    transition: border-color 0.2s ease;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(46, 204, 113, 0.6);
}

/* Section headers */
.section-title {
    font-weight: 800;
    font-size: 1.3rem;
    margin-top: 0.5rem;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* Chart cards */
.chart-card {
    border: 1.5px solid rgba(128, 128, 128, 0.25);
    border-radius: 14px;
    padding: 14px 16px 4px 16px;
    background: rgba(128, 128, 128, 0.04);
    margin-bottom: 1rem;
}

/* Custom KPI cards (HTML based) */
.kpi-card {
    border: 1.5px solid rgba(128, 128, 128, 0.35);
    border-radius: 12px;
    padding: 18px 12px;
    background: rgba(128, 128, 128, 0.06);
    text-align: center;
    transition: border-color 0.2s ease;
}
.kpi-card:hover {
    border-color: rgba(46, 204, 113, 0.6);
}
.kpi-label {
    font-size: 0.85rem;
    font-weight: 600;
    opacity: 0.7;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.7rem;
    font-weight: 800;
    white-space: nowrap;
    overflow-x: auto;
}

/* Insight cards */
.insight-card {
    border: 1.5px solid rgba(128, 128, 128, 0.25);
    border-radius: 14px;
    padding: 18px 22px;
    margin-bottom: 1rem;
    background: rgba(128, 128, 128, 0.04);
}
.insight-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
}
.insight-header h4 {
    margin: 0;
    font-weight: 800;
    font-size: 1.05rem;
}
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    color: white;
}
.insight-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
    margin-bottom: 12px;
}
.stat-box {
    background: rgba(128, 128, 128, 0.06);
    border-radius: 8px;
    padding: 8px 12px;
}
.stat-label {
    font-size: 0.72rem;
    opacity: 0.65;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.stat-value {
    font-size: 1.05rem;
    font-weight: 700;
    margin-top: 2px;
}
.maps-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 8px;
    background: #4285F4;
    color: white !important;
    font-weight: 700;
    font-size: 0.85rem;
    text-decoration: none !important;
    transition: background 0.2s ease;
}
.maps-btn:hover {
    background: #3367D6;
}

/* Sidebar header */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}
</style>
""", unsafe_allow_html=True)


# ==============================
# RISK COLOR PALETTE (shared)
# ==============================
RISK_COLORS = {
    'Adequate': '#2ecc71',
    'Low Deficit': '#f1c40f',
    'Moderate Deficit': '#e67e22',
    'High Deficit': '#e74c3c',
}


# ==============================
# SIDEBAR - DATA INPUT
# ==============================
st.sidebar.header("📂 Data Source")

uploaded_file = st.sidebar.file_uploader(
    "Upload grid data CSV",
    type=["csv"],
    accept_multiple_files=False,
    help="CSV must contain a geometry column (geom / geometry / wkt / the_geom) "
         "plus population, school_count, distance_k, gap, category."
   
)


# ==============================
# LOAD DATA (WKT parsing)
# ==============================
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)

    # detect geometry column
    geom_col = None
    for candidate in ['geom', 'geometry', 'wkt', 'the_geom']:
        if candidate in df.columns:
            geom_col = candidate
            break

    if geom_col is None:
        return None, "No geometry column found (expected one of: geom, geometry, wkt, the_geom)."

    df = df[df[geom_col].notnull()].copy()

    def safe_geom(x):
        try:
            return wkt.loads(x)
        except Exception:
            return None

    df[geom_col] = df[geom_col].apply(safe_geom)
    df = df[df[geom_col].notnull()]

    if df.empty:
        return None, "No valid geometries could be parsed from the geometry column."

    required_cols = {'population', 'school_count', 'distance_k', 'gap', 'category'}
    missing = required_cols - set(df.columns)
    if missing:
        return None, f"Missing required columns: {', '.join(sorted(missing))}"

    gdf = gpd.GeoDataFrame(df, geometry=geom_col)
    gdf.set_crs(epsg=4326, inplace=True)

    return gdf, None


# ==============================
# PAGE TITLE
# ==============================
st.title("School Accessibility Dashboard")

if uploaded_file is None:
    st.info("👈 Upload a grid data CSV from the sidebar to load the dashboard.")
    st.stop()

gdf, error = load_data(uploaded_file)

if error:
    st.error(f"⚠️ {error}")
    st.stop()


# ==============================
# DERIVED METRICS (computed once on full data)
# ==============================
gdf['schools_needed'] = gdf['gap'].apply(
    lambda x: max(0, int(x / 500) + 1 if pd.notnull(x) and x > 0 else 0)
)
gdf['centroid'] = gdf.geometry.centroid

# ==============================
# SIDEBAR - FILTERS
# ==============================
st.sidebar.header("🔍 Filters")

categories = st.sidebar.multiselect(
    "Select Category",
    options=gdf['category'].dropna().unique(),
    default=gdf['category'].dropna().unique()
)

pop_min, pop_max = float(gdf['population'].min()), float(gdf['population'].max())
population_range = st.sidebar.slider(
    "Population Range",
    min_value=int(pop_min),
    max_value=int(pop_max) + 1 if pop_max > int(pop_max) else int(pop_max),
    value=(int(pop_min), int(pop_max) + 1 if pop_max > int(pop_max) else int(pop_max))
)

dist_min, dist_max = float(gdf['distance_k'].min()), float(gdf['distance_k'].max())
distance_range = st.sidebar.slider(
    "Distance to Nearest School (km)",
    min_value=dist_min,
    max_value=max(dist_max, dist_min + 0.1),
    value=(dist_min, dist_max)
)

# ==============================
# APPLY FILTERS (drives everything)
# ==============================
filtered_gdf = gdf[
    gdf['category'].isin(categories) &
    gdf['population'].between(population_range[0], population_range[1]) &
    gdf['distance_k'].between(distance_range[0] - 1e-9, distance_range[1] + 1e-9)
].copy()

need_df = filtered_gdf[filtered_gdf['schools_needed'] > 0].copy()

if filtered_gdf.empty:
    st.warning("No data matches the current filters. Adjust filters in the sidebar.")
    st.stop()

# Map center based on filtered extent
bounds = filtered_gdf.total_bounds  # minx, miny, maxx, maxy
center_lat = (bounds[1] + bounds[3]) / 2
center_lon = (bounds[0] + bounds[2]) / 2

# ==============================
# KPIs
# ==============================
st.markdown('<div class="section-title">📊 Key Metrics</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

kpi_data = [
    ("Total Grids", f"{len(filtered_gdf):,}"),
    ("Total Population", f"{int(filtered_gdf['population'].sum()):,}"),
    ("Grids with Schools", f"{int((filtered_gdf['school_count'] > 0).sum()):,}"),
    ("Schools Needed", f"{int(filtered_gdf['schools_needed'].sum()):,}"),
]

for col, (label, value) in zip([col1, col2, col3, col4], kpi_data):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ==============================
# TABS
# ==============================
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ Maps",
    "📈 Charts",
    "📋 Data Table",
    "📌 Insights",
])

# ==============================
# TAB 1 - MAPS
# ==============================
with tab1:

    st.markdown('<div class="section-title">🗺️ Accessibility Map</div>', unsafe_allow_html=True)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

    def style(feature):
        cat = feature['properties'].get('category', '')
        return {
            'fillColor': RISK_COLORS.get(cat, '#999999'),
            'color': 'black',
            'weight': 0.3,
            'fillOpacity': 0.6
        }

    tooltip_fields = ['population', 'school_count', 'distance_k', 'gap', 'category']
    map_gdf = filtered_gdf[tooltip_fields + [filtered_gdf.geometry.name]].copy()
    map_gdf = map_gdf.reset_index(drop=True)
    map_gdf = map_gdf.set_geometry(filtered_gdf.geometry.name)
    map_gdf = map_gdf.set_crs(epsg=4326, allow_override=True)

    geojson_data = json.loads(map_gdf.to_json())

    folium.GeoJson(
        geojson_data,
        style_function=style,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=['Population', 'Schools', 'Distance (km)', 'Gap', 'Category']
        )
    ).add_to(m)

    # Legend
    legend_html = """
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 9999;
        background: white; color: black; padding: 10px 14px;
        border-radius: 8px; font-size: 13px; box-shadow: 0 2px 6px rgba(0,0,0,0.25);
        font-family: 'Nunito', sans-serif;">
        <b>Risk Category</b><br>
    """
    for cat, color in RISK_COLORS.items():
        legend_html += f'<span style="color:{color};">●</span> {cat}<br>'
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    if bounds[0] != bounds[2] and bounds[1] != bounds[3]:
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    st_folium(m, width=1000, height=550, key=f"map1_{len(filtered_gdf)}")

    st.divider()

    st.markdown('<div class="section-title">📍 Proposed School Locations</div>', unsafe_allow_html=True)

    if need_df.empty:
        st.info("No grids meet the threshold for new schools under current filters.")
    else:
        m2 = folium.Map(location=[center_lat, center_lon], zoom_start=13)

        for _, row in need_df.iterrows():
            folium.Marker(
                location=[row['centroid'].y, row['centroid'].x],
                popup=f"""
                <b>Schools Needed:</b> {row['schools_needed']}<br>
                <b>Population:</b> {int(row['population'])}<br>
                <b>Gap:</b> {int(row['gap'])}
                """,
                icon=folium.Icon(color='red', icon='graduation-cap', prefix='fa')
            ).add_to(m2)

        if bounds[0] != bounds[2] and bounds[1] != bounds[3]:
            m2.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        st_folium(m2, width=1000, height=550, key=f"map2_{len(need_df)}")

# ==============================
# TAB 2 - CHARTS
# ==============================
with tab2:

    chart_df = filtered_gdf[['population', 'school_count', 'distance_k', 'gap', 'category']].copy()

    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Grid Count by Risk Category**")
        cat_counts = chart_df['category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Grid Count']

        fig = px.pie(
            cat_counts,
            names='Category',
            values='Grid Count',
            color='Category',
            color_discrete_map=RISK_COLORS,
            hole=0.4,
        )
        fig.update_traces(textinfo='label+percent')
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Total Population by Risk Category**")
        pop = chart_df.groupby('category')['population'].sum().reset_index()

        fig = px.bar(
            pop,
            x='category',
            y='population',
            color='category',
            color_discrete_map=RISK_COLORS,
            labels={'category': 'Risk Category', 'population': 'Total Population'},
            text_auto=True,
        )
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Average Distance to Nearest School by Category**")
        dist = chart_df.groupby('category')['distance_k'].mean().reset_index()

        fig = px.bar(
            dist,
            x='category',
            y='distance_k',
            color='category',
            color_discrete_map=RISK_COLORS,
            labels={'category': 'Risk Category', 'distance_k': 'Avg Distance (km)'},
            text_auto='.2f',
        )
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("**Schools Needed by Risk Category**")
        needed = chart_df.copy()
        needed['schools_needed'] = filtered_gdf['schools_needed'].values
        needed_sum = needed.groupby('category')['schools_needed'].sum().reset_index()

        fig = px.bar(
            needed_sum,
            x='category',
            y='schools_needed',
            color='category',
            color_discrete_map=RISK_COLORS,
            labels={'category': 'Risk Category', 'schools_needed': 'Schools Needed'},
            text_auto=True,
        )
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# TAB 3 - TABLE
# ==============================
with tab3:
    st.markdown('<div class="section-title">📋 Filtered Data Table</div>', unsafe_allow_html=True)
    st.caption(f"Showing {len(filtered_gdf)} of {len(gdf)} grids")
    st.dataframe(
        filtered_gdf[['population', 'school_count', 'distance_k', 'gap', 'category', 'schools_needed']],
        use_container_width=True
    )

# ==============================
# TAB 4 - INSIGHTS
# ==============================
with tab4:
    st.markdown('<div class="section-title">📌 Priority Zones</div>', unsafe_allow_html=True)

    if need_df.empty:
        st.info("No priority zones identified under current filters.")
    else:
        max_zones = len(need_df)
        num_to_show = st.slider(
            "Number of priority zones to display",
            min_value=1,
            max_value=max_zones,
            value=min(5, max_zones),
            help="Showing the top zones ranked by gap size, in descending order."
        )

        top_priority = need_df.sort_values(by='gap', ascending=False).head(num_to_show)

        for zone_num, (_, row) in enumerate(top_priority.iterrows(), start=1):
            lat = row['centroid'].y
            lon = row['centroid'].x
            color = RISK_COLORS.get(row['category'], '#999999')
            maps_url = f"https://www.google.com/maps?q={lat},{lon}"

            st.markdown(f"""
            <div class="insight-card">
                <div class="insight-header">
                    <h4>📍 Zone {zone_num}</h4>
                    <span class="badge" style="background:{color};">{row['category']}</span>
                </div>
                <div class="insight-stats">
                    <div class="stat-box">
                        <div class="stat-label">Population</div>
                        <div class="stat-value">{int(row['population']):,}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Gap</div>
                        <div class="stat-value">{int(row['gap']):,}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Schools Needed</div>
                        <div class="stat-value">{row['schools_needed']}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Location</div>
                        <div class="stat-value">{lat:.4f}, {lon:.4f}</div>
                    </div>
                </div>
                <a class="maps-btn" href="{maps_url}" target="_blank">🔗 View on Google Maps</a>
            </div>
            """, unsafe_allow_html=True)
import streamlit as st
from fitparse import FitFile
import pandas as pd
import numpy as np
import altair as alt

st.title("Cycling Test Analysis — CP, MAP, W′")

# Get rider weight first
weight_kg = st.number_input("Enter body weight (kg)", min_value=30.0, max_value=120.0, value=70.0)

# Upload .fit files
uploaded_files = st.file_uploader(
    "Upload one or more .fit files", type=["fit"], accept_multiple_files=True
)

if uploaded_files:
    all_data = []

    def get_peak_interval(df, window):
        rolling = df['power'].rolling(window=window).mean()
        peak_start = rolling.idxmax() - window + 1
        peak_end = peak_start + window
        return peak_start, peak_end

    for file in uploaded_files:
        fitfile = FitFile(file)
        records = []
        for record in fitfile.get_messages("record"):
            data = {d.name: d.value for d in record if d.name in ["timestamp", "power"]}
            if "timestamp" in data and "power" in data:
                records.append(data)

        df = pd.DataFrame(records)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        df['power'] = df['power'].astype(float)
        all_data.append(df)

    combined_power = pd.concat(all_data, ignore_index=True)
    combined_power['seconds'] = np.arange(len(combined_power))

    # Identify peak effort locations
    i3s, i3e = get_peak_interval(combined_power, 180)
    i6s, i6e = get_peak_interval(combined_power, 360)
    i12s, i12e = get_peak_interval(combined_power, 720)

    # Tag the highlight areas
    combined_power['highlight'] = 'Other'
    combined_power.loc[i3s:i3e, 'highlight'] = '3-min'
    combined_power.loc[i6s:i6e, 'highlight'] = '6-min'
    combined_power.loc[i12s:i12e, 'highlight'] = '12-min'

    # Peak power values
    peak_3min = combined_power.loc[i3s:i3e, 'power'].mean()
    peak_6min = combined_power.loc[i6s:i6e, 'power'].mean()
    peak_12min = combined_power.loc[i12s:i12e, 'power'].mean()

    # CP, MAP, W′
    t1, t2 = 180, 720
    cp = (peak_12min * t2 - peak_3min * t1) / (t2 - t1)
    w_prime = (peak_3min - cp) * t1
    map_watts = peak_6min
    frac_util = cp / map_watts

    st.header("Best Peak Powers Across All Uploaded Files")
    col1, col2, col3 = st.columns(3)
    col1.metric("Peak 3-min Power", f"{peak_3min:.0f} W")
    col2.metric("Peak 6-min Power (MAP)", f"{peak_6min:.0f} W")
    col3.metric("Peak 12-min Power", f"{peak_12min:.0f} W")

    st.header("CP, W′, MAP, Fractional Utilisation")
    col1, col2, col3 = st.columns(3)
    col1.metric("Critical Power (CP)", f"{cp:.0f} W", f"{cp/weight_kg:.2f} W/kg")
    col2.metric("W′", f"{w_prime/1000:.1f} kJ", f"{(w_prime/1000)/weight_kg:.2f} kJ/kg")
    col3.metric("MAP (6-min)", f"{map_watts:.0f} W", f"{map_watts/weight_kg:.2f} W/kg")

    st.metric("Fractional Utilisation", f"{frac_util:.2%}")

    st.markdown("---")

    st.header("Exercise Intensity Domains")

    lt1 = cp * 0.75
    domain_ranges = pd.DataFrame({
        "Domain": ["Moderate", "Heavy", "Severe", "Extreme"],
        "Start": [0, lt1, cp, map_watts],
        "End": [lt1, cp, map_watts, map_watts + 150],
        "Color": ["#aed581", "#fff176", "#ff8a65", "#e57373"]
    })

    base = alt.Chart(domain_ranges).mark_bar().encode(
        x=alt.X("Start:Q", title="Power (Watts)"),
        x2="End:Q",
        y=alt.value(60),
        color=alt.Color("Domain:N", scale=alt.Scale(range=domain_ranges["Color"].tolist()), legend=None)
    ).properties(
        width=800,
        height=120
    )

    marker_df = pd.DataFrame({
        "value": [lt1, cp, map_watts]
    })

    lines = alt.Chart(marker_df).mark_rule(strokeDash=[4, 4], color="black").encode(
        x='value:Q'
    )

    st.altair_chart(base + lines, use_container_width=False)

    st.markdown(f"""
    <style>
    .domain-boxes {{
        display: flex;
        justify-content: space-between;
        margin-top: 1rem;
        font-family: sans-serif;
    }}
    .domain-box {{
        flex: 1;
        padding: 0.8rem;
        margin: 0 0.5rem;
        border-radius: 6px;
        text-align: center;
        font-size: 0.9rem;
    }}
    .mod {{ background-color: #aed581; border-top: 5px solid #aed581; }}
    .heav {{ background-color: #fff176; border-top: 5px solid #fff176; }}
    .sev {{ background-color: #ff8a65; border-top: 5px solid #ff8a65; }}
    .ext {{ background-color: #e57373; border-top: 5px solid #e57373; }}
    </style>

    <div class="domain-boxes">
        <div class="domain-box mod">
            <strong>Moderate</strong><br>
            0 – {lt1:.0f} W<br>
            Sustainable aerobic
        </div>
        <div class="domain-box heav">
            <strong>Heavy</strong><br>
            {lt1:.0f} – {cp:.0f} W<br>
            Lactate steady state
        </div>
        <div class="domain-box sev">
            <strong>Severe</strong><br>
            {cp:.0f} – {map_watts:.0f} W<br>
            VO₂ + W′ depletion
        </div>
        <div class="domain-box ext">
            <strong>Extreme</strong><br>
            > {map_watts:.0f} W<br>
            Sprints & fatigue
        </div>
    </div>
    """, unsafe_allow_html=True)

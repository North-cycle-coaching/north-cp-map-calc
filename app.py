import streamlit as st
from fitparse import FitFile
import pandas as pd
import numpy as np
import altair as alt

st.title("Cycling Test Analysis — CP, MAP, W′")

# Rider weight
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

    # Identify peak intervals
    i3s, i3e = get_peak_interval(combined_power, 180)
    i6s, i6e = get_peak_interval(combined_power, 360)
    i12s, i12e = get_peak_interval(combined_power, 720)

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

    st.header("Anaerobic Energy Contribution")

    watts = np.linspace(0, map_watts + 100, 200)
    oxygen_demand = watts * 0.2
    oxygen_uptake = np.where(watts <= cp, watts * 0.2, cp * 0.2 + (watts - cp) * 0.05)

    vo2_df = pd.DataFrame({
        "Power (W)": np.round(watts, 0),
        "O₂ Demand": np.round(oxygen_demand, 1),
        "O₂ Uptake": np.round(oxygen_uptake, 1)
    })

    base = alt.Chart(vo2_df).encode(x=alt.X("Power (W):Q"))

    demand_line = base.mark_line(color="#1f77b4", strokeWidth=2).encode(
        y=alt.Y("O₂ Demand:Q", title="Oxygen Equivalent")
    )

    uptake_line = base.mark_line(color="#2ca02c", strokeWidth=2).encode(
        y="O₂ Uptake:Q"
    )

    area = base.mark_area(opacity=0.3, color="#1f77b4").encode(
        y="O₂ Uptake:Q",
        y2="O₂ Demand:Q"
    )

    st.altair_chart(area + demand_line + uptake_line, use_container_width=True)

    st.markdown("""
    The gap between O₂ demand and uptake represents anaerobic energy contribution, depleting W′.
    """)

    st.markdown("---")

    st.subheader("Power & Time Above CP")

    step_powers = np.arange(cp + 10, cp + 310, 10)
    depletion_times = w_prime / (step_powers - cp)

    df_burn = pd.DataFrame({
        "Power (W)": step_powers.astype(int),
        "Time to W′ = 0 (s)": depletion_times.round(1),
        "Minutes": (depletion_times / 60).round(2)
    })

    st.dataframe(df_burn, use_container_width=True)

    st.markdown("---")

    # Interactive Intensity Domains
    st.header("Interactive Exercise Intensity Domains")

    lt1 = cp * 0.75

    domain_ranges = pd.DataFrame({
        "Domain": ["Moderate", "Heavy", "Severe", "Extreme"],
        "Start": [0, lt1, cp, map_watts],
        "End": [lt1, cp, map_watts, map_watts + 200],
        "Description": [
            "Fat-burning",
            "Carb-burning steady-state",
            "High-intensity anaerobic",
            "Maximum sprint"
        ],
        "Color": ["#aed581", "#fff176", "#ff8a65", "#e57373"]
    })

    color_scale = alt.Scale(domain=domain_ranges["Domain"].tolist(), range=domain_ranges["Color"].tolist())

    base = alt.Chart(domain_ranges).mark_bar().encode(
        x=alt.X("Start:Q", title="Power (W)"),
        x2="End:Q",
        y=alt.value(50),
        color=alt.Color("Domain:N", scale=color_scale, legend=None),
        tooltip=["Domain", "Start", "End", "Description"]
    ).properties(width=800, height=100)

    thresholds = pd.DataFrame({"Threshold": ["PT1", "CP (PT2)", "MAP"], "Value": [lt1, cp, map_watts]})

    lines = alt.Chart(thresholds).mark_rule(strokeDash=[6,4], color="black").encode(x="Value:Q")
    text = alt.Chart(thresholds).mark_text(dy=-15).encode(x='Value:Q', text='Threshold')

    st.altair_chart((base + lines + text).interactive(), use_container_width=True)


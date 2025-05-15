import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from matplotlib.patches import Wedge
import numpy as np

# --- Indlæs og forbered data ---
import gspread
from gspread_dataframe import get_as_dataframe

# Opsætning af adgang
from google.oauth2 import service_account
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(credentials)

# Social-dashboard
SHEET_ID = "1hSHzko--Pnt2R6iZD_jyi-WMOycVw49snibLi575Z2M"
worksheet = client.open_by_key(SHEET_ID).worksheet("Salg")
df = get_as_dataframe(worksheet, evaluate_formulas=True)

# Fjern tomme rækker
df = df.dropna(how='all')
df = df[['Produkt', 'Pris', 'Dato for salg']].dropna(subset=['Produkt', 'Pris'])
df['Dato for salg'] = pd.to_datetime(df['Dato for salg'], dayfirst=True)
df['Uge'] = df['Dato for salg'].dt.isocalendar().week
df['Pris'] = pd.to_numeric(df['Pris'], errors='coerce')

# --- Beregninger ---
samlet = df['Pris'].sum()
q2_maal = 90880
kendte_produkter = ["Leadpage", "Klaviyo", "Lead Ads", "Ekstra kampagne", "Xtra Visual", "SST"]
procent = samlet / q2_maal if q2_maal else 0

# --- Ugeopsætning ---
start_uge = 18
slut_uge = 26
alle_uger = list(range(start_uge, slut_uge + 1))

ugevis = df.groupby('Uge')['Pris'].sum().reindex(alle_uger, fill_value=0)
ugevis.index = ugevis.index.map(lambda u: f"Uge {u}")

# Layout og autorefresh
st.set_page_config(page_title="Social Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;margin-top:-50px;margin-bottom:-80px'>Social - Q2 Mål</h1>", unsafe_allow_html=True)
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=300_000, key="datarefresh")

col1, col2 = st.columns([2, 1])

# --- Linechart med markering af nuværende uge ---
with col1:
    st.subheader(" ")
    inner_cols = st.columns([0.1, 0.8, 0.1])
    with inner_cols[1]:
        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor('none')
        ax.set_facecolor('none')
        for spine in ax.spines.values():
            spine.set_visible(False)
        ugevis.plot(ax=ax, marker='o', label='Realisering', color='steelblue')

        ugentlig_maal = q2_maal / (slut_uge - start_uge + 1)
        ax.axhline(y=ugentlig_maal, color='orange', linestyle='--', label='Mål pr. uge')

        nu_uge = datetime.datetime.now().isocalendar().week
        uge_labels = list(ugevis.index)
        if f"Uge {nu_uge}" in uge_labels:
            pos = uge_labels.index(f"Uge {nu_uge}")
            ax.axvspan(pos - 0.1, pos + 0.1, color='lightblue', alpha=0.2, label='Nuværende uge')

        ax.set_xlabel("Uge")
        ax.set_ylabel("kr.")
        ax.legend()
        st.pyplot(fig)

# --- Donutgraf med gradienteffekt ---
with col2:
    st.subheader(" ")
    inner_cols = st.columns([0.2, 0.6, 0.2])
    with inner_cols[1]:
        fig2, ax2 = plt.subplots(figsize=(3, 3))
        ax2.set_xlim(-1.2, 1.2)
        ax2.set_ylim(-1.2, 1.2)
        ax2.axis('off')

        from matplotlib.colors import LinearSegmentedColormap
        gradient_cmap = LinearSegmentedColormap.from_list("custom_blue", ["#1f77b4", "#66b3ff"])
        gradient_color = gradient_cmap(0.5)

        wedges = [
            Wedge(center=(0, 0), r=1, theta1=90 - procent * 360, theta2=90,
                  facecolor=gradient_color, width=0.3),
            Wedge(center=(0, 0), r=1, theta1=90, theta2=450 - procent * 360,
                  facecolor="#e0e0e0", width=0.3)
        ]
        for w in wedges:
            ax2.add_patch(w)

        ax2.text(0, 0, f"{procent*100:.2f}%", ha='center', va='center', fontsize=20)
        st.pyplot(fig2)

# --- Alle produkter solgt, sorteret efter omsætning ---
st.markdown("<br>", unsafe_allow_html=True)
produkt_data = df.groupby("Produkt")["Pris"].agg(["sum", "count"]).reindex(kendte_produkter, fill_value=0)

cols = st.columns(len(produkt_data))
for i, (navn, row) in enumerate(produkt_data.iterrows()):
    cols[i].markdown(f"""
    <div style="text-align:center; padding:10px; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
      <div style="font-size:18px; font-weight:bold;">{navn}</div>
      <div style="font-size:16px;">{int(row['count'])} solgt</div>
      <div style="font-size:24px; font-weight:normal;">{row['sum']:,.0f} kr.</div>
    </div>
    """, unsafe_allow_html=True)

# --- Total og progressbar ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(f"""
<div style="text-align:center; font-size:24px; font-weight:bold; margin-bottom:10px;">
  Samlet: {samlet:,.0f} kr.
</div>
""", unsafe_allow_html=True)
progress_text = f"{samlet:,.0f} kr. / {q2_maal:,.0f} kr."
st.markdown(f"""
<div style="margin-top: 20px;">
  <div style="font-size:16px; text-align:center; margin-bottom:4px;">
    {progress_text}
  </div>
  <div style="background-color:#e0e0e0; border-radius:10px; height:30px; width:100%;">
    <div style="background: linear-gradient(90deg, #1f77b4, #66b3ff); width:{procent*100}%; height:30px; border-radius:10px;"></div>
  </div>
</div>
""", unsafe_allow_html=True)
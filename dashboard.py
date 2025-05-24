import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.patches import Wedge
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import gspread
from gspread_dataframe import get_as_dataframe
from google.oauth2 import service_account

# --- Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["service_account"]
credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(credentials)

# --- Hent data ---
SHEET_ID = "1plU6MRL7v9lkQ9VeaGJUD4ljuftZve16nPF8N6y36Kg"
worksheet = client.open_by_key(SHEET_ID).worksheet("Salg")
df = get_as_dataframe(worksheet, evaluate_formulas=True)
df = df.dropna(how="all")

# --- Opdel i salg og tilbud ---
solgte_df = df[["Produkt", "Pris", "Dato for salg"]].dropna(subset=["Produkt", "Pris"])
solgte_df["Dato for salg"] = pd.to_datetime(solgte_df["Dato for salg"], dayfirst=True, errors="coerce")
solgte_df["Uge"] = solgte_df["Dato for salg"].dt.isocalendar().week
solgte_df["Pris"] = pd.to_numeric(solgte_df["Pris"], errors="coerce")

tilbud_df = df[["Produkt tilbudt", "Tilbudspris", "Dato for tilbud", "Status"]].dropna(subset=["Produkt tilbudt", "Tilbudspris", "Dato for tilbud"])
tilbud_df["Dato for tilbud"] = pd.to_datetime(tilbud_df["Dato for tilbud"], dayfirst=True, errors="coerce")
tilbud_df["Uge"] = tilbud_df["Dato for tilbud"].dt.isocalendar().week

# --- Rens statusfelt for stavefejl og mellemrum ---
tilbud_df["Status"] = (
    tilbud_df["Status"]
    .astype(str)
    .str.strip()
    .str.capitalize()
    .replace({"Aflsag": "Afslag"})
)

# --- Konstanter ---
total_goal = 48000
solgt_sum = solgte_df["Pris"].sum()
total_count = len(solgte_df)
procent = solgt_sum / total_goal if total_goal else 0

# --- Ugeopsætning ---
start_uge = 18
slut_uge = 26
alle_uger = list(range(start_uge, slut_uge + 1))
ugevis = solgte_df.groupby("Uge")["Pris"].sum().reindex(alle_uger, fill_value=0)
ugevis.index = ugevis.index.map(lambda u: f"Uge {u}")

# --- Dynamisk ugemål ---
nu_uge = datetime.now().isocalendar().week
resterende_uger = len([u for u in alle_uger if u > nu_uge])
manglende_beloeb = max(total_goal - solgt_sum, 0)
restmaal = manglende_beloeb / resterende_uger if resterende_uger > 0 else manglende_beloeb

# --- Layout ---
st.set_page_config(page_title="Web Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;margin-top:-50px;margin-bottom:-80px'>Web - Q2 Mål</h1>", unsafe_allow_html=True)
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=300_000, key="datarefresh")

col1, col2 = st.columns([2, 1])

# --- Linechart ---
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

        # Tilbud sendt (stiplet grå linje)
        tilbud_ugevis = tilbud_df.groupby("Uge")["Tilbudspris"].sum().reindex(alle_uger, fill_value=0)
        ax.plot([f"Uge {u}" for u in tilbud_ugevis.index], tilbud_ugevis.values, linestyle='dashed', color='gray', alpha=0.5, label='Tilbud sendt')

        ax.axhline(y=restmaal, color='red', linestyle='--', label='Ugemål')

        uge_labels = list(ugevis.index)
        if f"Uge {nu_uge}" in uge_labels:
            pos = uge_labels.index(f"Uge {nu_uge}")
            ax.axvspan(pos - 0.1, pos + 0.1, color='lightblue', alpha=0.2, label='Nuværende uge')

        ax.set_xlabel("Uge")
        ax.set_ylabel("kr.")
        ax.legend()
        st.pyplot(fig)

# --- Donutgraf + Hitrate ---
with col2:
    st.subheader(" ")
    inner_cols = st.columns([0.2, 0.6, 0.2])
    with inner_cols[1]:
        fig2, ax2 = plt.subplots(figsize=(3, 3))
        ax2.set_xlim(-1.2, 1.2)
        ax2.set_ylim(-1.2, 1.2)
        ax2.axis('off')

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

        # --- Beregn hitrate inkl. alle tilbud ---
        q2_tilbud = tilbud_df[tilbud_df["Uge"].between(18, 26)]
        status_renset = q2_tilbud["Status"].astype(str).str.strip().str.capitalize().replace({"Aflsag": "Afslag"})

        antal_godkendt = (status_renset == "Godkendt").sum()
        antal_afslag = (status_renset == "Afslag").sum()
        antal_afventer = (status_renset == "Tilbud").sum()

        total_tilbud = antal_godkendt + antal_afslag + antal_afventer
        hitrate = (antal_godkendt / total_tilbud * 100) if total_tilbud > 0 else 0

        st.markdown(f"""
        <div style="text-align:center; font-size:14px; margin-top:-10px;">
          Hitrate: {hitrate:.1f}%<br>
          <span style="font-size:12px;">(Solgt: {antal_godkendt}, Afslag: {antal_afslag}, Tilbud: {antal_afventer})</span>
        </div>
        """, unsafe_allow_html=True)

# --- Produkter + tilbudsboks + totalboks ---
st.markdown("<br>", unsafe_allow_html=True)
produktliste = [
    "Cookie", "Ekstra undersider", "Tekster til undersider",
    "Undersider med tekster", "SoMe Feed Pro"
]

produkt_data = solgte_df.groupby("Produkt")["Pris"].agg(["sum", "count"]).reindex(produktliste, fill_value=0).sort_values("sum", ascending=False).head(3)
cols = st.columns(5)

for i, (navn, row) in enumerate(reversed(list(produkt_data.iterrows()))):
    cols[2 - i].markdown(f"""
    <div style="text-align:center; padding:10px; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
      <div style="font-size:18px; font-weight:bold;">{navn}</div>
      <div style="font-size:16px;">{int(row['count'])} solgt</div>
      <div style="font-size:24px; font-weight:normal;">{format(row['sum'], ',.0f').replace(',', '.')} kr.</div>
    </div>
    """, unsafe_allow_html=True)

# Tilbudsboks
antal_tilbud = len(tilbud_df)
total_tilbud_beloeb = tilbud_df["Tilbudspris"].sum()
cols[3].markdown(f"""
<div style="text-align:center; padding:10px; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
  <div style="font-size:18px; font-weight:bold;">Tilbud sendt</div>
  <div style="font-size:16px;">{antal_tilbud} stk</div>
  <div style="font-size:24px; font-weight:normal;">{format(total_tilbud_beloeb, ',.0f').replace(',', '.')} kr.</div>
</div>
""", unsafe_allow_html=True)

# Totalboks
cols[4].markdown(f"""
<div style="text-align:center; padding:10px; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
  <div style="font-size:18px; font-weight:bold;">Antal produkter solgt</div>
  <div style="font-size:16px;">{total_count} solgt</div>
  <div style="font-size:24px; font-weight:normal;">{format(solgt_sum, ',.0f').replace(',', '.')} kr.</div>
</div>
""", unsafe_allow_html=True)

# --- Total og progressbar ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(f"""
<div style="text-align:center; font-size:24px; font-weight:bold; margin-bottom:10px;">
  Samlet: {format(solgt_sum, ',.0f').replace(',', '.')} kr.
</div>
""", unsafe_allow_html=True)
progress_text = f"{format(solgt_sum, ',.0f').replace(',', '.')} kr. / {format(total_goal, ',.0f').replace(',', '.')} kr."
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
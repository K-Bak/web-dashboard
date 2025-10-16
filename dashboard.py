import streamlit as st
st.set_page_config(page_title="Web Dashboard", layout="wide")

import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.patches import Wedge
from matplotlib.colors import LinearSegmentedColormap
import gspread
from gspread_dataframe import get_as_dataframe
from google.oauth2 import service_account

# --- Setup ----------------------------------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["service_account"]
credentials = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=scope)
client = gspread.authorize(credentials)

# --- Hent data ------------------------------------------------
SHEET_ID = "1plU6MRL7v9lkQ9VeaGJUD4ljuftZve16nPF8N6y36Kg"
df = (get_as_dataframe(client.open_by_key(SHEET_ID)
                       .worksheet("Salg"), evaluate_formulas=True)
      .dropna(how="all"))

# --- Standardisering ------------------------------------------
df["Status"] = (df["Status"].astype(str).str.strip().str.capitalize()
                .replace({"Aflsag": "Afslag"}))
df["Dato"] = pd.to_datetime(df["Dato"], dayfirst=True, errors="coerce")
df["Pris"] = pd.to_numeric(df["Pris"], errors="coerce")
df["Uge"] = df["Dato"].dt.isocalendar().week
df["År"] = df["Dato"].dt.year

# ------------ Konstanter & vinduer (Q4) -----------------------
YEAR_GOAL = 100_000           # hele året (uændret)
Q4_GOAL   = 49_175            # Q4-mål
START_UGE = 40                # uge 40–51 er Q4
SLUT_UGE  = 51
YEAR      = datetime.now().year

# --- Filtre ---------------------------------------------------
q4_mask   = df["Uge"].between(START_UGE, SLUT_UGE) & (df["År"] == YEAR)
year_mask = df["År"] == YEAR

df_q4      = df[q4_mask]
solgte_q4  = df_q4[df_q4["Status"] == "Godkendt"]
tilbud_q4  = df_q4[df_q4["Status"] == "Tilbud"]
afslag_q4  = df_q4[df_q4["Status"] == "Afslag"]

# (Top-produkter kører på hele året ↓)
solgte_year = df[year_mask & (df["Status"] == "Godkendt")]

# --- Q4 KPI’er ------------------------------------------------
q4_sum   = solgte_q4["Pris"].sum()
q4_count = len(solgte_q4)
q4_pct   = q4_sum / Q4_GOAL if Q4_GOAL else 0

# Uge-opsætning til grafer
alle_uger = list(range(START_UGE, SLUT_UGE + 1))
ugevis_q4 = (solgte_q4.groupby("Uge")["Pris"]
             .sum().reindex(alle_uger, fill_value=0))
ugevis_q4.index = ugevis_q4.index.map(lambda u: f"Uge {u}")

# Rest-ugemål i Q4
nu_uge = datetime.now().isocalendar().week
resterende_uger = len([u for u in alle_uger if u > nu_uge])
restmål = max(Q4_GOAL - q4_sum, 0) / resterende_uger if resterende_uger else 0

# --- Layout ---------------------------------------------------
st.markdown(
    "<h1 style='text-align:center;margin-top:-50px;margin-bottom:-80px'>"
    "Web – Q4 Mål</h1>", unsafe_allow_html=True)

# --- Autorefresh hver 5. min ----------------------------------
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=300_000, key="datarefresh")

col1, col2 = st.columns([2, 1])

# ---------------- Grafer --------------------------------------
with col1:
    st.subheader(" ")
    with st.columns([0.05, 0.9, 0.05])[1]:
        fig, ax = plt.subplots(figsize=(10, 4))
        for spine in ax.spines.values():
            spine.set_visible(False)
        ugevis_q4.plot(ax=ax, marker="o", label="Realisering", color="steelblue")

        # Tilbud & Afslag linjer
        tilbud_ugevis = (tilbud_q4.groupby("Uge")["Pris"]
                         .sum().reindex(alle_uger, fill_value=0))
        afslag_ugevis = (afslag_q4.groupby("Uge")["Pris"]
                         .sum().reindex(alle_uger, fill_value=0))

        ax.plot(tilbud_ugevis.index.map(lambda u: f"Uge {u}"),
                tilbud_ugevis.values, ls="--", color="gray", alpha=.5,
                label="Tilbud sendt")
        ax.plot(afslag_ugevis.index.map(lambda u: f"Uge {u}"),
                afslag_ugevis.values, ls=":", color="firebrick", alpha=.6,
                label="Afslag")

        ax.axhline(restmål, color="red", ls="--", label="Ugemål")
        if START_UGE <= nu_uge <= SLUT_UGE:
            try:
                pos = list(ugevis_q4.index).index(f"Uge {nu_uge}")
                ax.axvspan(pos-.1, pos+.1, color="lightblue", alpha=.2,
                           label="Nuværende uge")
            except ValueError:
                pass

        ax.set_xlabel("Uge")
        ax.set_ylabel("kr.")
        ax.legend()
        st.pyplot(fig)

# ---------------- Donut & hitrate ------------------------------
with col2:
    st.subheader(" ")
    with st.columns([0.2, 0.6, 0.2])[1]:
        fig2, ax2 = plt.subplots(figsize=(3, 3))
        ax2.axis("equal"); ax2.axis("off")
        # sikrer at hele ringen er i billedet
        ax2.set_xlim(-1.2, 1.2); ax2.set_ylim(-1.2, 1.2)

        cmap = LinearSegmentedColormap.from_list("blue", ["#1f77b4", "#66b3ff"])

        # Blå sektion (progress)
        ax2.add_patch(Wedge((0, 0), 1,
                            90,                           # start kl. 12
                            90 + q4_pct*360,              # længde = pct
                            width=.3,
                            facecolor=cmap(.5)))

        # Grå baggrund (resten af ringen)
        ax2.add_patch(Wedge((0, 0), 1,
                            90 + q4_pct*360, 450,
                            width=.3,
                            facecolor="#e0e0e0"))

        ax2.text(0, 0, f"{q4_pct*100:.1f}%", ha="center", va="center",
                 fontsize=20)
        st.pyplot(fig2)

        # Hitrate i Q4
        status_q4 = df_q4["Status"]
        g, a, t = (status_q4=="Godkendt").sum(), (status_q4=="Afslag").sum(), \
                  (status_q4=="Tilbud").sum()
        total_tilbud = g + a + t
        hit = g/total_tilbud*100 if total_tilbud else 0
        st.markdown(f"""
<div style='text-align:center;font-size:14px;margin-top:-10px;'>
  Hitrate: {hit:.1f}%<br>
  <span style='font-size:12px;'>(Solgt: {g}, Afslag: {a}, Tilbud: {t})</span>
</div>
""", unsafe_allow_html=True)

# ---------------- Produkt-top3 (år) ---------------------------
st.markdown("<br>", unsafe_allow_html=True)
produktliste = ["Cookie", "5 tekster", "Tekster + Undersider",
                "Ekstra undersider", "SEO Starter", "SoMe Feed Pro",
                "Ekstra Sproglag", "Produktvisning", "Logo design",
                "Blogfunktion"]
prod_year = (solgte_year.groupby("Produkt")["Pris"]
             .agg(["sum","count"]).reindex(produktliste, fill_value=0)
             .sort_values("sum", ascending=False).head(3))

cols = st.columns(5)
for i,(navn,row) in enumerate(reversed(list(prod_year.iterrows()))):
    cols[2-i].markdown(f"""
<div style='text-align:center;padding:10px;background:white;border-radius:10px;
            box-shadow:0 2px 8px rgba(0,0,0,0.05);'>
  <div style='font-size:18px;font-weight:bold;'>{navn}</div>
  <div style='font-size:16px;'>{int(row['count'])} solgt</div>
  <div style='font-size:24px;'>{row['sum']:,.0f} kr.</div>
</div>
""", unsafe_allow_html=True)

# Tilbuds-boks (Q4)
cols[3].markdown(f"""
<div style='text-align:center;padding:10px;background:white;border-radius:10px;
            box-shadow:0 2px 8px rgba(0,0,0,0.05);'>
  <div style='font-size:18px;font-weight:bold;'>Tilbud sendt (Q4)</div>
  <div style='font-size:16px;'>{len(tilbud_q4)} stk</div>
  <div style='font-size:24px;'>{tilbud_q4['Pris'].sum():,.0f} kr.</div>
</div>
""", unsafe_allow_html=True)

# Solgt-boks (Q4)
cols[4].markdown(f"""
<div style='text-align:center;padding:10px;background:white;border-radius:10px;
            box-shadow:0 2px 8px rgba(0,0,0,0.05);'>
  <div style='font-size:18px;font-weight:bold;'>Produktsalg (Q4)</div>
  <div style='font-size:16px;'>{q4_count} solgt</div>
  <div style='font-size:24px;'>{q4_sum:,.0f} kr.</div>
</div>
""", unsafe_allow_html=True)

# ---------------- Progress-barer -------------------------------
st.markdown("<br>", unsafe_allow_html=True)

# Q4-progress
st.markdown(f"""
<div style='text-align:center;font-size:20px;font-weight:bold;margin-bottom:6px;'>
  Q4 mål: {q4_sum:,.0f} / {Q4_GOAL:,.0f} kr.
</div>
<div style='background:#e0e0e0;border-radius:10px;height:30px;'>
  <div style='background:linear-gradient(90deg,#1f77b4,#66b3ff);
              width:{q4_pct*100:.1f}%;height:30px;border-radius:10px;'></div>
</div>
""", unsafe_allow_html=True)

# År-progress
year_sum = solgte_year["Pris"].sum()
year_pct = year_sum / YEAR_GOAL if YEAR_GOAL else 0
st.markdown(f"""
<div style='text-align:center;font-size:20px;font-weight:bold;margin:18px 0 6px;'>
  År til dato: {year_sum:,.0f} / {YEAR_GOAL:,.0f} kr.
</div>
<div style='background:#e0e0e0;border-radius:10px;height:30px;'>
  <div style='background:linear-gradient(90deg,#228b22,#7fe27f);
              width:{year_pct*100:.1f}%;height:30px;border-radius:10px;'></div>
</div>
""", unsafe_allow_html=True)
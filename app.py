import streamlit as st
import pandas as pd
from supabase import create_client, Client
import plotly.express as px
import os
from dotenv import load_dotenv

# -------------------------------
# --- Load environment variables ---
# -------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# -------------------------------
# --- Setup Supabase client ---
# -------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# --- Streamlit config ---
# -------------------------------
st.set_page_config(page_title="Panthers Stats Dashboard", layout="wide")
st.title("🏈 Panthers Team Stats")

# Sidebar: Select stat category
table_name = st.sidebar.selectbox("Select stat category", [
    "passing", "rushing", "receiving", "defense", "interception",
    "kicking", "punting", "return", "kick_return"
])

# Query Supabase
response = supabase.table(table_name).select("*").order("updated_at", desc=True).limit(100).execute()
df = pd.DataFrame(response.data)

if df.empty:
    st.warning("No data found for this category.")
    st.stop()

# Sidebar: Filter by player
players = df["Player"].dropna().unique().tolist()
selected_players = st.sidebar.multiselect("Filter by player", players, default=players)

filtered_df = df[df["Player"].isin(selected_players)]

# Identify numeric columns
numeric_columns = [col for col in filtered_df.columns if col not in ["Player", "updated_at"] and pd.api.types.is_numeric_dtype(filtered_df[col])]

# Tabs for views
tab1, tab2, tab3, tab4 = st.tabs(["📋 Table View", "🥧 Pie Chart", "🏆 Leaderboard", "🔍 Player Comparison"])

# 📋 Table View
with tab1:
    st.subheader(f"Latest {table_name.capitalize()} Stats")
    st.dataframe(filtered_df, use_container_width=True)

# 🥧 Pie Chart
with tab2:
    if numeric_columns:
        stat_column = st.selectbox("Pie chart stat", numeric_columns)
        pie_data = filtered_df.groupby("Player")[stat_column].sum().reset_index()
        fig = px.pie(pie_data, names="Player", values=stat_column, title=f"{stat_column} by Player")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric columns available for pie chart.")

# 🏆 Leaderboard
with tab3:
    st.subheader("Top 5 Players")
    leaderboard_column = st.selectbox("Choose stat for leaderboard", numeric_columns)
    top_df = filtered_df.sort_values(by=leaderboard_column, ascending=False).head(5)
    st.table(top_df[["Player", leaderboard_column]])

# 🔍 Player Comparison
with tab4:
    st.subheader("Compare Two Players")
    compare_players = st.multiselect("Select two players", players, max_selections=2)
    if len(compare_players) == 2:
        comp_df = filtered_df[filtered_df["Player"].isin(compare_players)].set_index("Player")
        st.write(comp_df[numeric_columns].transpose())
    else:
        st.info("Please select exactly two players.")
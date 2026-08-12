import os
import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.title("Project 2: Real-Time Crypto Telemetry Dashboard")
st.subheader("Live Market Price Logs & Moving Averages")


# Function to connect to PostgreSQL and fetch price logs
def load_data():
    try:
        conn = psycopg2.connect(
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=5432
        )
        query = "SELECT crypto_name, current_price, sma_value, time_created FROM price_logs ORDER BY time_created DESC LIMIT 100;"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"[PostgreDB_APP] Failed connection to database from frontend: {e}")

# Load data and render table
data_df = load_data()
st.dataframe(data_df, use_container_width=True)
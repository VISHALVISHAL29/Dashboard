import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

def read_excel(file):
    df = pd.read_excel(file, engine="openpyxl", parse_dates=["Posting Date"])
    df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors='coerce')
    return df

def filter_data(df, chemical, start_date, end_date):
    df = df[
        ((df["SoE Description"] == chemical) | (df["Sub SoE Description"] == chemical)) &
        (df["Posting Date"] >= start_date) &
        (df["Posting Date"] <= end_date)
    ]
    return df

def get_cost_usage_plot(df):
    grouped = df.groupby("Posting Date").agg({"Value": "sum", "Quantity": "sum"}).reset_index()
    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.set_xlabel("Date")
    ax1.set_ylabel("Cost", color="tab:red")
    ax1.plot(grouped["Posting Date"], grouped["Value"], color="tab:red", label="Cost")
    ax1.tick_params(axis="y", labelcolor="tab:red")

    ax2 = ax1.twinx()
    ax2.set_ylabel("Quantity", color="tab:blue")
    ax2.plot(grouped["Posting Date"], grouped["Quantity"], color="tab:blue", label="Quantity")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    fig.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    return buf

def generate_report(df):
    if df.empty:
        return "No data available in selected range."
    highest_day = df.groupby("Posting Date")["Value"].sum().idxmax()
    max_val = df.groupby("Posting Date")["Value"].sum().max()
    return f"The highest cost occurred on {highest_day.strftime('%Y-%m-%d')} with a total value of ₹{max_val}."

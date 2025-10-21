# Placeholder for plot_utils.py
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit as st
import pandas as pd
import seaborn as sns
import numpy as np
import calendar


# --------------------- Mean + Per-Point Time Series ---------------------
def plot_time_series(df_line, show=True):
    """
    Plot time series of mRVI values for each point and the mean across points.
    Returns the matplotlib figure object.
    """
    st.subheader("Time Series of Mean mRVI at Sample Points")
    
    if df_line is None or df_line.empty:
        st.warning("No data available for time series plot.")
        return None

    df_line["time"] = pd.to_datetime(df_line["time"])
    df_line = df_line.sort_values("time")

    fig1, ax1 = plt.subplots(figsize=(12, 6))

    # Plot each point
    for pid, group in df_line.groupby("point_id"):
        ax1.plot(group["time"], group["mRVI"], marker="o", linestyle="-", alpha=0.5, label=f"Point {pid}")

    # Mean curve
    mean_df = df_line.groupby("time")["mRVI"].mean().reset_index()
    ax1.plot(mean_df["time"], mean_df["mRVI"], color="green", linewidth=2.5, marker="o", markersize=6, label="Mean mRVI")

    # Format
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax1.set_xlabel("Date")
    ax1.set_ylabel("mRVI Value")
    ax1.set_title("Time Series of Mean mRVI at Sample Points")
    plt.xticks(rotation=45)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
    plt.tight_layout()

    st.pyplot(fig1)


# --------------------- Per-Point mRVI Time Series ---------------------
def plot_point_series(df_points, show=True):
    """
    Plot mRVI values per individual point over time.
    Returns the matplotlib figure object.
    """
    st.subheader("Time Series of mRVI at Sample Points")

    if df_points is None or df_points.empty:
        st.warning("No data available for point-wise plot.")
        return None

    df_points["time"] = pd.to_datetime(df_points["time"])
    df_points = df_points.sort_values("time")

    fig2, ax2 = plt.subplots(figsize=(12, 6))

    for pid, group in df_points.groupby("point_id"):
        ax2.plot(group["time"], group["mRVI_median"], marker="o", linestyle="-", markersize=5, alpha=0.7, label=f"Point {pid}")

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax2.set_xlabel("Date")
    ax2.set_ylabel("mRVI Value")
    ax2.set_title("Time Series of mRVI at Sample Points")
    plt.xticks(rotation=45)
    plt.tight_layout()

    st.pyplot(fig2)


# --------------------- Plot Boxplot ---------------------
def plot_outlier_boxplot(df_points):
    """Plot mRVI dispersion and potential outliers."""

    df_long = df_points.melt(
        id_vars=["time"],
        value_vars=["mRVI_median"],
        var_name="variable",
        value_name="value"
    )
    df_long["point"] = df_points["point_id"]
    df_long["time"] = pd.to_datetime(df_long["time"])

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(x="time", y="value", data=df_long, ax=ax)
    plt.xticks(rotation=45)
    ax.set_xlabel("Date")
    ax.set_ylabel("mRVI Value")
    ax.set_title("mRVI Dispersion and Outlier Analysis at Sample Points")
    plt.tight_layout()
    return fig


def plot_statistics(month_stats, mmdd_stats, season_start=10):
    """Plot paddy area statistics as bar and pie charts."""
    seasonal_order = [(season_start + i - 1) % 12 + 1 for i in range(12)]

    # --- Month-level DataFrame
    df_month = pd.DataFrame(list(month_stats.items()), columns=["Month", "Area_ha"])
    df_month = df_month[df_month["Month"] != 0]
    df_month["Month_Name"] = df_month["Month"].apply(lambda x: calendar.month_name[int(x)])
    df_month["Seasonal_Order"] = df_month["Month"].apply(lambda x: seasonal_order.index(int(x)))
    df_month = df_month.sort_values("Seasonal_Order")
    df_month["Cumulative_Area_ha"] = df_month["Area_ha"].cumsum()

    # --- MMDD-level DataFrame
    df_mmdd = pd.DataFrame(list(mmdd_stats.items()), columns=["MMDD", "Area_ha"])
    df_mmdd = df_mmdd[df_mmdd["MMDD"] != 0]
    df_mmdd["Month_Day"] = df_mmdd["MMDD"].apply(lambda x: f"{str(int(x)).zfill(4)[:2]}-{str(int(x)).zfill(4)[2:]}")

    def consecutive_day_index(mmdd):
        month = int(str(int(mmdd)).zfill(4)[:2])
        day = int(str(int(mmdd)).zfill(4)[2:])
        month_shifted = (month - season_start) % 12
        return month_shifted * 31 + day

    df_mmdd["Seasonal_Index"] = df_mmdd["MMDD"].apply(consecutive_day_index)
    df_mmdd = df_mmdd.sort_values("Seasonal_Index")
    df_mmdd["Cumulative_Area_ha"] = df_mmdd["Area_ha"].cumsum()

    # --- Plot 1: Bar chart by Month
    fig_1, ax_1 = plt.subplots(figsize=(8, 6))
    ax_1.bar(df_month["Month_Name"], df_month["Area_ha"], color="skyblue")
    ax_1.set_xlabel("Month")
    ax_1.set_ylabel("Area (ha)")
    ax_1.set_title("Paddy Area by Month (Seasonal Order)")
    plt.xticks(rotation=45)
    st.session_state[f"stats_bar_month"] = fig_1

    # --- Plot 2: Bar chart by MMDD
    fig_2, ax_2 = plt.subplots(figsize=(10, 6))
    ax_2.bar(df_mmdd["Month_Day"], df_mmdd["Area_ha"], color="lightgreen")
    ax_2.set_xlabel("Start Date (MM-DD)")
    ax_2.set_ylabel("Area (ha)")
    ax_2.set_title("Paddy Area by Start Date (Seasonal Order)")
    plt.xticks(rotation=90)
    st.session_state[f"stats_bar_day"] = fig_2

    # --- Plot 3: Pie chart by Month
    fig_3, ax_3 = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax_3.pie(
        df_month["Area_ha"],
        startangle=90,
        colors=plt.cm.tab20.colors,
        autopct=lambda pct: f"{pct:.1f}%",
        pctdistance=0.8,
        wedgeprops=dict(width=0.5),
    )
    ax_3.legend(
        wedges, df_month["Month_Name"], title="Start Month",
        loc="center left", bbox_to_anchor=(1, 0, 0.5, 1)
    )
    ax_3.set_title("Paddy Area % by Month (Seasonal Order)")
    st.session_state[f"stats_pie_month"] = fig_3

    # --- Plot 4: Pie chart by MMDD
    labels = df_mmdd["Month_Day"]
    sizes = df_mmdd["Area_ha"]
    cmap = plt.cm.viridis(np.linspace(0, 1, len(labels)))

    fig_4, ax_4 = plt.subplots(figsize=(10, 10))
    wedges, texts, autotexts = ax_4.pie(
        sizes,
        labels=None,
        startangle=90,
        colors=cmap,
        autopct=lambda pct: f"{pct:.1f}%",
        pctdistance=0.85,
        wedgeprops=dict(width=0.5, edgecolor="w"),
    )
    ax_4.legend(
        wedges, labels, title="Start Date (MM-DD)",
        loc="center left", bbox_to_anchor=(1, 0, 0.5, 1)
    )
    ax_4.set_title("Paddy Area % by Start Date (Seasonal Order)", fontsize=14)
    st.session_state[f"stats_pie_day"] = fig_4

    # --- Month-level Bar + Cumulative Line ---
    fig_5, ax5 = plt.subplots(figsize=(9,6))
    x = np.arange(len(df_month))
    ax5.bar(x, df_month["Area_ha"], color="#43A047", width=0.5, alpha=0.8, label="Monthly Area (ha)")
    ax5.plot(x, df_month["Cumulative_Area_ha"], color="#1E88E5", marker="o", linewidth=2.5, label="Cumulative Area (ha)")
    ax5.fill_between(x, df_month["Cumulative_Area_ha"], color="#1E88E5", alpha=0.15)
    ax5.set_xticks(x)
    ax5.set_xticklabels(df_month["Month_Name"], rotation=45)
    ax5.set_xlabel("Month")
    ax5.set_ylabel("Area (ha)")
    ax5.set_title("Monthly and Cumulative Paddy Area")
    ax5.grid(axis="y", linestyle="--", alpha=0.5)
    ax5.legend()
    st.session_state["stats_combo_month"] = fig_5

    # --- Daily (MM-DD) Bar + Cumulative Line ---
    fig_6, ax6 = plt.subplots(figsize=(12,6))
    x = np.arange(len(df_mmdd))
    ax6.bar(x, df_mmdd["Area_ha"], color="#43A047", width=0.6, alpha=0.8, label="Dekadal Area (ha)")
    ax6.plot(x, df_mmdd["Cumulative_Area_ha"], color="#1E88E5", marker="o", linewidth=2.5, label="Cumulative Area (ha)")
    ax6.fill_between(x, df_mmdd["Cumulative_Area_ha"], color="#1E88E5", alpha=0.15)
    ax6.set_xticks(x)
    ax6.set_xticklabels(df_mmdd["Month_Day"], rotation=45)
    ax6.set_xlabel("Start Date (MM-DD)")
    ax6.set_ylabel("Area (ha)")
    ax6.set_title("Dekadal and Cumulative Paddy Area")
    ax6.grid(axis="y", linestyle="--", alpha=0.5)
    ax6.legend()
    st.session_state["stats_combo_day"] = fig_6


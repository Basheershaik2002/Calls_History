import os
import pandas as pd
import streamlit as st

# File upload via Streamlit
st.title("DPDzero Data Pipeline Summary")
calls_file = st.file_uploader("Upload Call Logs CSV", type="csv")
agents_file = st.file_uploader("Upload Agent Roster CSV", type="csv")
dispositions_file = st.file_uploader("Upload Disposition Summary CSV", type="csv")

if calls_file and agents_file and dispositions_file:
    calls = pd.read_csv(calls_file, parse_dates=["call_date", "created_ts"])
    agents = pd.read_csv(agents_file)
    dispositions = pd.read_csv(dispositions_file, parse_dates=["call_date"])

    # Validation
    required_cols = {
        "calls_log": ["call_id", "agent_id", "org_id", "installment_id", "status", "duration", "call_date"],
        "agent_roster": ["agent_id", "org_id", "users_first_name", "users_last_name"],
        "disposition_summary": ["agent_id", "org_id", "call_date"]
    }

    for name, cols in required_cols.items():
        df = eval(name)
        missing = set(cols) - set(df.columns)
        if missing:
            st.error(f"Missing columns in {name}: {missing}")
        if df.duplicated().any():
            st.warning(f"Duplicate rows found in {name}")
    
    # Merge
    merged = pd.merge(calls, agents, on=["agent_id", "org_id"], how="left")
    merged = pd.merge(merged, dispositions, on=["agent_id", "org_id", "call_date"], how="left")

    # Feature engineering
    merged["is_completed"] = merged["status"].str.lower() == "completed"
    merged["Presence"] = merged["login_time"].notnull().astype(int)
    merged["duration"] = pd.to_numeric(merged["duration"], errors="coerce").fillna(0)

    summary = merged.groupby(
        ["agent_id", "users_first_name", "users_last_name", "call_date"]
    ).agg(
        Total_Calls=("call_id", "count"),
        Unique_Loans=("installment_id", "nunique"),
        Completed_Calls=("is_completed", "sum"),
        Avg_Duration_Min=("duration", lambda x: round(x.mean() / 60, 2)),
        Presence=("Presence", "max")
    ).reset_index()

    summary["Connect_Rate"] = (summary["Completed_Calls"] / summary["Total_Calls"]).round(2)

    # Show summary table
    st.subheader("Agent Performance Summary")
    st.dataframe(summary)

    # Show Slack-style summary
    if not summary.empty:
        latest_date = summary["call_date"].max()
        top_agent = summary.sort_values("Connect_Rate", ascending=False).iloc[0]
        avg_duration = summary["Avg_Duration_Min"].mean()

        st.markdown(f"""
        ### :clipboard: Agent Summary for {latest_date.date()}
        - :trophy: **Top Performer**: {top_agent['users_first_name']} {top_agent['users_last_name']} ({int(top_agent['Connect_Rate']*100)}% connect rate)
        - :busts_in_silhouette: **Total Active Agents**: {summary.shape[0]}
        - :hourglass_flowing_sand: **Average Call Duration**: {avg_duration:.2f} minutes
        """)

    # Option to download
    st.download_button(
        "Download Summary CSV",
        summary.to_csv(index=False).encode("utf-8"),
        file_name="agent_performance_summary.csv",
        mime="text/csv"
    )
else:
    st.info("Please upload all three required CSV files to proceed.")

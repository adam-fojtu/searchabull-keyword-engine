import pandas as pd
import streamlit as st
import datetime as dt

st.title("Get Group IDs")

df = st.file_uploader("📁 Upload your keywords Excel file", type=["xlsx"])

num_cols = df.columns.difference(["Keyword", "Total Volume"])

df["VolumePatternKey"] = df[num_cols].astype(str).agg('|'.join, axis=1)

# Assign GroupIDs in order of first appearance
group_id_dict = {}
group_id_counter = 1
group_ids = []

for key in df["VolumePatternKey"]:
    if key not in group_id_dict:
        group_id_dict[key] = group_id_counter
        group_id_counter += 1
    group_ids.append(group_id_dict[key])

df["GroupID"] = group_ids

# Drop helper column if not needed
df.drop(columns=["VolumePatternKey"], inplace=True)

filename = f"group_id_table {dt.datetime.now().strftime('%d-%m-%Y %H-%M-%S')}"

st.download_button("Download Table with Group IDs", df, file_name=filename)

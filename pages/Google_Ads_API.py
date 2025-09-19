import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import yaml
import streamlit as st
import json
from io import BytesIO
import datetime as dt
import time
import os
from zoneinfo import ZoneInfo

config = {
    "developer_token": st.secrets["developer_token"],
    "client_id": st.secrets["client_id"],
    "client_secret": st.secrets["client_secret"],
    "refresh_token": st.secrets["refresh_token"],
    "customer_id": st.secrets["customer_id"],
    "use_proto_plus": st.secrets["use_proto_plus"] == "True",
}

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 You must be logged in to access this page.")
    st.stop()


st.set_page_config(page_title="Google Ads API Tool", layout="wide")
st.title("🔑 Monthly Access Tool")

with st.sidebar:
    st.markdown("## 👤 Profile")
    st.text_input("User", value=st.session_state.user, key="user_display", disabled=True)

with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)

with open("languages.json", "r", encoding="utf-8") as f:
    languages = json.load(f)

regions_list = [
    "Europe", "Asia-Pacific", "South America", "North America"
]

locations_list = [
    "France", "Germany", "Austria", "Netherlands", "Belgium", "Switzerland",
    "United Kingdom", "Ireland", "Italy", "Spain", "Portugal", "Sweden",
    "Norway", "Denmark", "Finland", "Slovakia", "Czechia", "Poland", "Romania",
    "Hungary", "India", "Indonesia", "Australia", "New Zealand", "Brazil",
    "Colombia", "Argentina", "Chile", "United States", "Canada", "Mexico", "Saudi Arabia",
    "Japan"
]

languages_list = [
    "French", "German", "Dutch", "English", "Italian", "Spanish", "Portuguese",
    "Swedish", "Norwegian", "Danish", "Finnish", "Slovak", "Czech", "Polish",
    "Romanian", "Hungarian", "Hindi", "Indonesian", "Arabic", "Japanese"
]

selection = pd.DataFrame(columns=["region", "target_location", "target_language"])

tool_type = st.radio("Choose Tool:", ["Historical Volumes", "Keyword Ideas"])
category = st.text_input("Category")
template = st.file_uploader("Upload a target location template:", type=["yaml", "yml"])


selected = st.data_editor(
    selection,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "region": st.column_config.SelectboxColumn("Region", options=regions_list),
        "target_location": st.column_config.SelectboxColumn("Location", options=locations_list),
        "target_language": st.column_config.SelectboxColumn("Language", options=languages_list)
    },
    height=400
)

uploaded_file = st.file_uploader("📁 Upload your keywords Excel file", type=["xlsx"])

df_locations = pd.DataFrame(locations)
df_languages = pd.DataFrame(languages)

client_type = "GenerateKeywordHistoricalMetricsRequest" if tool_type == "Historical Volumes" else "GenerateKeywordIdeasRequest"

if template:
    try:
        selected = yaml.safe_load(template)["params"]
        targets = pd.DataFrame(selected)[["target_location"]].rename(columns={"target_location": "Selected Countries"})
        st.dataframe(targets, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Failed to read the template: {e}")

if uploaded_file:
    if not template:
        st.session_state.params = selected.to_dict(orient="records")
    else:
        st.session_state.params = selected
    try:
        params = st.session_state.params
        keywords = pd.read_excel(uploaded_file, header=0)
        keywords_list = keywords.iloc[:, 0].dropna().to_list()
        all_data, all_failed = [], []
        st.success(f"Loaded {len(keywords_list)} keywords.")
        st.write(keywords.head())
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        st.stop()

    if st.button("🚀 Run Volume Script" if tool_type == "Historical Volumes" else "🚀 Get Keyword Ideas"):
        start = dt.datetime.now()
        # ✅ Moved client outside loop
        client = GoogleAdsClient.load_from_dict(config)
        googleads_service = client.get_service("GoogleAdsService")
        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

        for param in params:
            st.badge(param["target_location"])
            geo_code = int(df_locations.loc[df_locations["location_name"] == param["target_location"], "location_code"].values[0])
            language_code = int(df_languages.loc[df_languages["language_name"] == param["target_language"], "id"].values[0])

            batch_size = 10000 if tool_type == "Historical Volumes" else 20
            all_rows, failed_terms = [], []
            progress_bar = st.progress(0)
            status_text = st.empty()
            batch_num = 0
            total_batches = len(keywords_list) // batch_size + (1 if len(keywords_list) % batch_size != 0 else 0)

            with st.spinner("⏳ Processing..."):
                for i in range(0, len(keywords_list), batch_size):
                    batch = keywords_list[i:i + batch_size]

                    request = client.get_type(client_type)
                    request.customer_id = config["customer_id"]

                    if tool_type == "Historical Volumes":
                        request.keywords.extend([str(k) for k in batch])
                    else:
                        request.keyword_seed.keywords.extend([str(k) for k in batch])

                    request.geo_target_constants.append(
                        googleads_service.geo_target_constant_path(geo_code)
                    )
                    request.language = googleads_service.language_constant_path(language_code)
                    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

                    try:
                        request_method = (
                            keyword_plan_idea_service.generate_keyword_historical_metrics
                            if tool_type == "Historical Volumes"
                            else keyword_plan_idea_service.generate_keyword_ideas
                        )

                        response = request_method(request=request, timeout=90)
                        results = []
                        for result in response.results:
                            metrics = result.keyword_metrics if tool_type == "Historical Volumes" else result.keyword_idea_metrics
                            results.append({
                                "query": result.text,
                                "volume": metrics.monthly_search_volumes,
                            })

                        for result in results:
                            row = {"Keyword": result["query"]}
                            for record in result["volume"]:
                                month = record.month - 1
                                col = f"{month}-{record.year}"
                                row[col] = record.monthly_searches
                            all_rows.append(row)

                    except GoogleAdsException as e:
                        st.error(f"Google Ads API error: {e}")
                        st.stop()

                    batch_num += 1
                    progress = batch_num / total_batches
                    progress_bar.progress(progress)
                    status_text.markdown(f"""
                    <b>📦 Batch {batch_num} of {total_batches}</b>  
                    <b>✅ Progress: {int(progress * 100)}%</b>
                    """, unsafe_allow_html=True)

                    time.sleep(5)

            # ✅ Build df only once here
            df = pd.DataFrame(all_rows)
            df["Region"] = param["region"]
            df["Country"] = param["target_location"]
            df["Language"] = param["target_language"]
            df["Category"] = category
            description_columns = ["Category", "Language","Region", "Country"]
            col_order = description_columns + [c for c in df.columns if c not in description_columns]
            df = df[col_order]

            result_terms = set(df["Keyword"])
            input_terms = set(keywords_list)
            missing_terms = [(param["target_location"], term) for term in input_terms - result_terms]
            df_failed_terms = pd.DataFrame(missing_terms, columns=["Country", "Keyword"])

            numeric_df = df.select_dtypes(include="number")
            date_index = pd.to_datetime(numeric_df.columns, format="%m-%Y", errors="coerce")

            quarter_labels = date_index.to_series().dt.to_period("Q").astype(str)
            rename_map_q = dict(zip(numeric_df.columns, [quarter_labels[c] for c in date_index]))
            renamed_df = df[numeric_df.columns].rename(columns=rename_map_q)
            aggregated_df = renamed_df.T.groupby(level=0).sum().T
            aggregated_df.columns = [f"Q{c.split('Q')[1]} {c.split('Q')[0].split('0')[1]}" for c in aggregated_df.columns]
            full_df = pd.concat([df, aggregated_df], axis=1)

            new_col_names = date_index.strftime("%b-%y")
            rename_map_m = dict(zip(numeric_df.columns, new_col_names))
            full_df.rename(columns=rename_map_m, inplace=True)

            latest_year = date_index[-1].strftime("%y")
            latest_month = date_index[-1].strftime("%b")
            rolling_12m_column_name = f"12M to {latest_month} {latest_year}"
            full_df[rolling_12m_column_name] = numeric_df.sum(axis=1)

            all_data.append(full_df)
            all_failed.append(df_failed_terms)

        final_data = pd.concat(all_data, axis=0)
        final_failed = pd.concat(all_failed, axis=0)
        buffer = BytesIO()

        final_data.sort_values(by=final_data.columns[-1], ascending=False, inplace=True)

        # ✅ Use xlsxwriter for better performance
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            final_data.to_excel(writer, index=False, sheet_name="data")
            final_failed.to_excel(writer, index=False, sheet_name="failed_terms")

        location_code = df_locations.loc[df_locations.location_name == param["target_location"], "country_iso_code"].values[0]
        local_now = dt.datetime.now(ZoneInfo("Europe/Bratislava"))
        timestamp = local_now.strftime("%d-%m-%Y %H-%M-%S")
        filename = f"{'SEARCH VOLUMES' if tool_type == 'Historical Volumes' else 'KEYWORD IDEAS'} - {category} - {timestamp}.xlsx"
        end = dt.datetime.now()
        duration = (end - start).total_seconds() / 60
        st.success(f"Process done in {duration:.2f} minutes")
        st.success("✅ Done! Download your Excel file below:")
        st.download_button("📥 Download Excel", buffer.getvalue(), file_name=filename)

import streamlit as st
import pandas as pd
import json
import requests
import time
import os
import base64
import datetime as dt
from dotenv import load_dotenv
from io import BytesIO
import random
import yaml
from zoneinfo import ZoneInfo

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 You must be logged in to access this page.")
    st.stop()

# --- LISTS ---
popular_countries = [
    "United Kingdom",
    "United States",
    "Germany",
    "France",
    "Italy",
    "Spain",
    "Canada",
    "Australia",
    "Poland",
    "Netherlands",
    "Brazil",
    "Mexico",
    "India",
    "Japan",
    "South Korea",
    "Russia",
    "China",
    "Turkey",
    "Czechia",
    "Slovakia",
    "Norway",
    "Hungary",
    "Norway",
    "Finland",
    "Netherlands",
    "Romania",
    "Sweden",
    "Denmark",
    "Portugal",
    "Saudi Arabia",
    
]
language_dict = {
    "English": "en",
    "Spanish": "es",
    "German": "de",
    "French": "fr",
    "Portuguese": "pt",
    "Finnish": "fi",
    "Hungarian": "hu",
    "Italian": "it",
    "Norwegian": "no",
    "Polish": "pl",
    "Romanian": "ro",
    "Slovak": "sk",
    "Swedish": "sv",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "Arabic": "ar",
    "Japanese": "ja"
}

regions_list = [
    "Europe", "Asia-Pacific", "South America", "North America"
]


def get_balance():
    # load_dotenv(".env")
    login = st.secrets["DATAFORSEO_LOGIN"]
    password = st.secrets["DATAFORSEO_PASSWORD"]

    auth_string = f"{login}:{password}"
    auth_encoded = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

    url = "https://api.dataforseo.com/v3/appendix/user_data"
    headers = {
        "Authorization": f"Basic {auth_encoded}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        result = data.get("tasks", [])[0].get("result", [])[0]
        balance = result.get("money", {}).get("balance", None)
        return balance

    except Exception as e:
        print(f"❌ Error fetching balance: {e}")
        return None



# --- PAGE CONFIG ---
st.set_page_config(page_title="Keyword Volume Checker", layout="wide")
st.title("📊 Keyword Volume Lookup")

with st.sidebar:
    st.markdown("## 👤 Profile")
    st.text_input("User", value=st.session_state.user, key="user_display", disabled=True)
    
st.sidebar.markdown("### 💰 DataForSEO Balance")
balance = get_balance()
if balance is not None:
    st.sidebar.success(f"${balance:,.2f}")
else:
    st.sidebar.error("Couldn't fetch balance.")

API = st.radio("API Mode", ["SANDBOX", "PAID"])
TOOL_TYPE = st.radio("Choose Tool:", ["Historical Volumes", "Keyword Ideas"])
CATEGORY = st.text_input("Category Label (for export file)")
template = st.file_uploader("Upload a target location template:", type=["yaml", "yml"])
selection = pd.DataFrame(columns=["region", "target_location", "target_language"])

selected = st.data_editor(
    selection,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "region": st.column_config.SelectboxColumn("Region", options=regions_list),
        "target_location": st.column_config.SelectboxColumn("Location", options=popular_countries),
        "target_language": st.column_config.SelectboxColumn("Language", options=language_dict.keys())
    },
    height=400
)

SORT = st.radio("Sort Results By", ["search_volume", "relevance"])
ADULT_KWS = st.checkbox("Include Adult Keywords", value=True)

# --- LOCATIONS ---

with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)
df_locations = pd.DataFrame(locations)


st.markdown("Upload a keyword list and get search volumes from DataForSEO.")

# --- UPLOAD ---
uploaded_file = st.file_uploader("📁 Upload your keywords Excel file", type=["xlsx"])

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
        df_keywords = pd.read_excel(uploaded_file)
        keywords_list = df_keywords.iloc[:, 0].dropna().tolist()
        st.success(f"Loaded {len(keywords_list)} keywords.")
        st.write(df_keywords.head())
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        st.stop()

    if st.button("🚀 Run Volume Script" if TOOL_TYPE == "Historical Volumes" else "🚀 Get Keyword Ideas"):
        # --- ENV + AUTH ---
        # load_dotenv()
        start = dt.datetime.now()
        login = os.getenv("DATAFORSEO_LOGIN")
        password = os.getenv("DATAFORSEO_PASSWORD")
        auth_string = f"{login}:{password}"
        auth_encoded = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")


        # --- TIME RANGE ---
        today = dt.date.today()
        DATE_TO = today.replace(day=1)
        DATE_FROM = DATE_TO.replace(year=DATE_TO.year - 4)
        DATE_FROM = DATE_FROM.strftime("%Y-%m-%d")
        DATE_TO = DATE_TO.strftime("%Y-%m-%d")

        #--- URL & PAYLOAD ---
        base_url = {
            "SANDBOX": "https://sandbox.dataforseo.com",
            "PAID": "https://api.dataforseo.com"
        }[API]

        url = (
            f"{base_url}/v3/keywords_data/google_ads/search_volume/live"
            if TOOL_TYPE == "Historical Volumes"
            else f"{base_url}/v3/keywords_data/google_ads/keywords_for_keywords/live"
        )
        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "Content-Type": "application/json"
        }
        all_rows = []
        failed_batches = []
        # --- PROCESSING ---
        for param in params:
            st.badge(param["target_location"])
            location = int(df_locations.loc[df_locations["location_name"] == param["target_location"], "location_code"].values[0])
            location_code = df_locations.loc[df_locations["location_name"] == param["target_location"], "country_iso_code"].values[0]

            batch_size = 1000 if TOOL_TYPE == "Historical Volumes" else 20
            
            total_batches = len(keywords_list) // batch_size + (1 if len(keywords_list) % batch_size != 0 else 0)

            progress_bar = st.progress(0)
            status_text = st.empty()
            batch_num = 0
            
            with st.spinner("⏳ Processing..."):
                for i in range(0, len(keywords_list), batch_size):
                    batch = keywords_list[i:i + batch_size]
                    payload_dict = [{
                        "date_from": DATE_FROM,
                        "date_to": DATE_TO,
                        "keywords": batch,
                        "location_code": location,
                        "language_code": language_dict[param["target_language"]],
                        "sort_by": SORT,
                        "include_adult_keywords": ADULT_KWS
                    }]

                    retries = 0
                    success = False

                    while not success and retries < 3:
                        try:
                            response = requests.post(url, headers=headers, data=json.dumps(payload_dict), timeout=30)
                            response.raise_for_status()
                            response_json = response.json()

                            results = response_json["tasks"][0].get("result")
                            if not results:
                                raise ValueError("Empty result from API")
                            
                            for entry in results:
                                keyword = entry["keyword"]
                                monthly_data = entry.get("monthly_searches", [])
                                row = {
                                    "Category": CATEGORY,
                                    "Language": param["target_language"],
                                    "Region": param["region"],
                                    "Country": param["target_location"], 
                                    "Keyword": keyword
                                    }
                                
                                if monthly_data:
                                    total_volume = 0
                                    for month_entry in monthly_data:
                                        month = str(month_entry["month"]).zfill(2)
                                        year = str(month_entry["year"])
                                        column_name = f"{month}-{year}"
                                        row[column_name] = int(month_entry["search_volume"])
                                        total_volume += int(month_entry["search_volume"])
                                    row["Total Volume"] = int(total_volume)
                                    
                                else:
                                    row["Total Volume"] = pd.NA

                                all_rows.append(row)

                            success = True
                        except Exception as e:
                            retries += 1
                            wait = 5 * (2 ** (retries - 1))
                            st.warning(f"❌ Error in batch {i // batch_size + 1}: {e} — retrying in {wait}s...")
                            time.sleep(wait)

                    if not success:
                        failed_batches.append(i)

                    batch_num += 1
                    progress = batch_num / total_batches
                    progress_bar.progress(progress)
                    status_text.markdown(f"""
                    <b>📦 Batch {batch_num} of {total_batches}</b>  
                    <b>✅ Progress: {int(progress * 100)}%</b>
                    """, unsafe_allow_html=True)
                    time.sleep(5.1 + random.uniform(0.5, 1.5))

        # --- FINALIZE ---
        df_volumes = pd.DataFrame(all_rows)
        description_cols = ["Category", "Language", "Region", "Country", "Language", "Total Volume", "Keyword"]
        date_cols = sorted(
            [col for col in df_volumes.columns if col not in description_cols],
            key=lambda x: pd.to_datetime(x, format="%m-%Y")
        )
        df_volumes = df_volumes[description_cols + date_cols]
        df_volumes = df_volumes.sort_values("Total Volume", ascending=False)

        # Add the yearly rolling windows
        latest_date = df_volumes.columns[-1]
        latest_month = pd.to_datetime(latest_date, format="%m-%Y").strftime("%b")
        latest_year = pd.to_datetime(latest_date, format="%m-%Y").strftime("%y")
        first_month_col_name = df_volumes.select_dtypes("number").columns[1]
        idx = df_volumes.columns.get_loc(first_month_col_name)
        for i in range(3, -1, -1):
            df_volumes[f"12M to {latest_month} {int(latest_year)-i}"] = df_volumes.iloc[:, idx:idx + 12].sum(axis=1)
            idx += 12

        # --- EXPORT ---
        local_now = dt.datetime.now(ZoneInfo("Europe/Bratislava"))
        timestamp = local_now.strftime("%d-%m-%Y %H-%M-%S")
        filename = f"SEARCH VOLUMES - {CATEGORY} - {timestamp}.xlsx"
        buffer = BytesIO()
        df_volumes.to_excel(buffer, index=False, engine="openpyxl")
        end = dt.datetime.now()
        duration = (end - start).total_seconds() / 60
        st.success(f"Process done in {duration:.2f} minutes")
        st.success("✅ Done! Download your Excel file below:")
        st.download_button("📥 Download Excel", buffer.getvalue(), file_name=filename)

        if failed_batches:
            st.warning(f"⚠️ Some batches failed: {failed_batches}")
        else:
            st.info("✅ All batches processed successfully!")

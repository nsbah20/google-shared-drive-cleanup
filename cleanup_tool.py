import streamlit as st
import pandas as pd
from datetime import datetime
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']

st.title("📁 Shared Drive Cleanup Tool")

# Session state setup
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'drive_service' not in st.session_state:
    st.session_state.drive_service = None
if 'scanned_data' not in st.session_state:
    st.session_state.scanned_data = None
if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = None
if 'deleted_empty_folders' not in st.session_state:
    st.session_state.deleted_empty_folders = []

# Authentication
if st.sidebar.button("🔐 Authenticate"):
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "C:/Users/adama/OneDrive/Desktop/LAWD PROJECTS/Migration Project/Duplicates Check/client_secrets.json", SCOPES)
        creds = flow.run_local_server(port=0)
        drive_service = build('drive', 'v3', credentials=creds)
        st.session_state.authenticated = True
        st.session_state.drive_service = drive_service
        st.sidebar.success("Authenticated successfully!")
    except Exception as e:
        st.sidebar.error(f"Authentication failed: {str(e)}")

# Main app logic
if st.session_state.authenticated and st.session_state.drive_service:
    drive_service = st.session_state.drive_service
    st.sidebar.header("📁 Shared Drive Settings")

    try:
        shared_drives = drive_service.drives().list().execute().get('drives', [])
        drive_choices = {d['name']: d['id'] for d in shared_drives}
        selected_drive = st.sidebar.selectbox("Choose Drive:", list(drive_choices.keys()))
    except HttpError as e:
        st.error(f"Error fetching shared drives: {e}")

    st.sidebar.header("📅 Filter Options")
    start_date = st.sidebar.date_input("Start Date")
    end_date = st.sidebar.date_input("End Date")

    filter_mode = st.sidebar.radio("Filter Mode", ["All Files in Date Range", "Filter by Keywords"])
    keyword_input = ""
    if filter_mode == "Filter by Keywords":
        keyword_input = st.sidebar.text_input("Enter keywords (comma separated)")

    keyword_pattern = re.compile("|".join([kw.strip() for kw in keyword_input.split(",") if kw.strip()]), re.IGNORECASE)

    if st.sidebar.button("🔍 Run Report"):
        ROOT_FOLDER_ID = drive_choices[selected_drive]
        visited_folders = set()
        files = []
        title_counts = {}
        title_only_counts = {}
        empty_folders = []

        def scan_folder(folder_id):
            if folder_id in visited_folders:
                return
            visited_folders.add(folder_id)

            try:
                folder_metadata = drive_service.files().get(fileId=folder_id, fields="name").execute()
                folder_name = folder_metadata.get("name", folder_id)
            except:
                folder_name = folder_id

            with st.spinner(f"📂 Scanning: {folder_name}..."):
                query = f"'{folder_id}' in parents and trashed=false"
                page_token = None

                while True:
                    try:
                        response = drive_service.files().list(
                            q=query,
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True,
                            fields="nextPageToken, files(id, name, modifiedTime, mimeType)",
                            pageToken=page_token
                        ).execute()

                        items = response.get('files', [])
                        folder_has_files = False

                        for file in items:
                            if file['mimeType'] == 'application/vnd.google-apps.folder':
                                scan_folder(file['id'])
                            else:
                                folder_has_files = True
                                try:
                                    mod = file['modifiedTime']
                                    modified_date = datetime.strptime(mod, "%Y-%m-%dT%H:%M:%S.%fZ")
                                    title = file['name']
                                    file_signature = (title, file['id'])
                                    title_counts[file_signature] = title_counts.get(file_signature, 0) + 1

                                    title_only_counts[title] = title_only_counts.get(title, 0) + 1
                                    reason = 'duplicate_title' if title_only_counts[title] > 1 else ''

                                    if start_date <= modified_date.date() <= end_date:
                                        if filter_mode == "All Files in Date Range" or keyword_pattern.search(title):
                                            files.append({
                                                'title': title,
                                                'id': file['id'],
                                                'modified': modified_date,
                                                'modified_str': mod,
                                                'reason': reason
                                            })
                                except Exception:
                                    continue

                        if not folder_has_files and not items:
                            empty_folders.append(folder_name)

                        page_token = response.get('nextPageToken', None)
                        if page_token is None:
                            break

                    except Exception as e:
                        st.error(f"Error scanning folder: {e}")
                        break

        scan_folder(ROOT_FOLDER_ID)
        st.session_state.deleted_empty_folders = empty_folders

        if files:
            df_filtered = pd.DataFrame(files)
            st.session_state.scanned_data = df_filtered
            st.session_state.filtered_data = df_filtered
        else:
            st.warning("🚫 No matching files found in the selected folder and filters.")
            st.session_state.filtered_data = None
            st.session_state.scanned_data = None

# Display data and allow deletion
if st.session_state.filtered_data is not None:
    df_filtered = st.session_state.filtered_data
    st.success(f"Found {len(df_filtered)} matching files.")
    st.dataframe(df_filtered[['title', 'modified_str', 'reason']])

    st.download_button(
        "📅 Download CSV",
        data=df_filtered.to_csv(index=False),
        file_name="scan_results.csv",
        mime="text/csv"
    )

    if st.session_state.deleted_empty_folders:
        st.info(f"📂 Found {len(st.session_state.deleted_empty_folders)} empty folders.")
        st.download_button(
            "📁 Download Empty Folders CSV",
            data=pd.DataFrame({'empty_folder': st.session_state.deleted_empty_folders}).to_csv(index=False),
            file_name="empty_folders.csv",
            mime="text/csv"
        )

    if st.button("🗑️ Delete All Filtered Files"):
        with st.spinner("Deleting files..."):
            delete_statuses = []
            for index, row in df_filtered.iterrows():
                file_id = row['id']
                try:
                    drive_service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                    try:
                        drive_service.files().get(fileId=file_id, supportsAllDrives=True).execute()
                        delete_statuses.append("Failed ❌: File still exists")
                    except HttpError as e:
                        if e.resp.status == 404:
                            delete_statuses.append("Deleted ✅")
                        else:
                            delete_statuses.append(f"Error ❌: {str(e)}")
                except HttpError as e:
                    if e.resp.status == 404:
                        delete_statuses.append("Already Deleted ⚠️")
                    else:
                        delete_statuses.append(f"Delete Error ❌: {str(e)}")
                except Exception as e:
                    delete_statuses.append(f"Unknown Error ❌: {str(e)}")

            df_filtered['delete_status'] = delete_statuses
            failed_count = sum(1 for status in delete_statuses if "Deleted" not in status)

            if failed_count == 0:
                st.success("✅ All files were deleted successfully.")
            else:
                st.warning(f"⚠️ {failed_count} files could not be deleted. Download the CSV for details.")

            st.download_button(
                "📅 Download Delete Results CSV",
                data=df_filtered.to_csv(index=False),
                file_name="delete_results.csv",
                mime="text/csv"
            )

            st.session_state.filtered_data = None
            st.session_state.scanned_data = None

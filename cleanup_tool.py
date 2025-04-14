import streamlit as st
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from datetime import datetime, timedelta
import re
import os

# Title
st.title("📁 Shared Drive Cleanup Tool")

# Use session state to persist across reruns
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'drive' not in st.session_state:
    st.session_state.drive = None

# Authentication
st.sidebar.header("Step 1: Authenticate")
if st.sidebar.button("🔐 Authenticate"):
    try:
        ga = GoogleAuth()
        ga.LoadClientConfigFile("client_secrets.json")
        ga.CommandLineAuth()
        drive = GoogleDrive(ga)
        st.session_state.authenticated = True
        st.session_state.drive = drive
        st.sidebar.success("Authenticated successfully!")
    except Exception as e:
        st.sidebar.error(f"Authentication failed: {str(e)}")

# Proceed only if authenticated
if st.session_state.authenticated and st.session_state.drive:
    drive = st.session_state.drive
    st.sidebar.header("Step 2: Select and Scan a Shared Drive")

    shared_drives = drive.auth.service.teamdrives().list().execute().get('items', [])
    drive_choices = {d['name']: d['id'] for d in shared_drives}

    selected_drive = st.sidebar.selectbox("Select a Shared Drive:", list(drive_choices.keys()))
    if st.sidebar.button("🔍 Scan Drive"):
        ROOT_FOLDER_ID = drive_choices[selected_drive]

        visited_folders = set()
        files_to_flag = []
        seen_titles = {}
        cutoff_date = datetime.utcnow() - timedelta(days=730)

        def scan_folder(folder_id):
            if folder_id in visited_folders:
                return
            visited_folders.add(folder_id)

            file_list = drive.ListFile({
                'q': f"'{folder_id}' in parents and trashed=false",
                'supportsAllDrives': True,
                'includeItemsFromAllDrives': True
            }).GetList()

            for file in file_list:
                if file['mimeType'] == 'application/vnd.google-apps.folder':
                    scan_folder(file['id'])
                else:
                    file_id = file['id']
                    title = file['title']
                    modified_str = file['modifiedDate']
                    modified_date = datetime.strptime(modified_str, "%Y-%m-%dT%H:%M:%S.%fZ")

                    is_duplicate = title in seen_titles
                    if not is_duplicate:
                        seen_titles[title] = file_id

                    is_old = modified_date < cutoff_date

                    if is_duplicate or is_old:
                        files_to_flag.append({
                            'title': title,
                            'id': file_id,
                            'modified': modified_str,
                            'reason': 'duplicate' if is_duplicate else 'stale'
                        })

        with st.spinner("Scanning Drive. Please wait..."):
            scan_folder(ROOT_FOLDER_ID)

        if files_to_flag:
            df = pd.DataFrame(files_to_flag)
            st.success(f"Found {len(df)} flagged files.")
            st.dataframe(df)

            csv_name = f"flagged_files_{selected_drive.replace(' ', '_')}.csv"
            st.download_button("📥 Download CSV", data=df.to_csv(index=False), file_name=csv_name, mime="text/csv")

            if st.button("🗑️ Delete Flagged Files"):
                for f in files_to_flag:
                    try:
                        file = drive.CreateFile({'id': f['id']})
                        file.Delete()
                    except:
                        pass
                st.warning("Deleted all flagged files!")
        else:
            st.info("No flagged files found.")

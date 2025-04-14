# 🧹 Shared Drive Cleanup Tool

A Streamlit app that connects to your Google Shared Drives and identifies:
- 📄 Duplicate files
- 🕒 Old/stale files (over 2 years old)

## 🚀 Features

- Google authentication with PyDrive
- Recursive folder scanning
- CSV export of flagged files
- Optional deletion of duplicates or stale content

## 📦 Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

## ▶️ Run the app

```bash
streamlit run cleanup_tool.py
```

## 🔐 Setup

To use this app, you'll need a `client_secrets.json` file from the Google Developer Console.  
Place it in the same folder and **do not upload it to GitHub**.

## 🙋‍♂️ Author

Adama N. Bah  
[LinkedIn](https://www.linkedin.com/in/adama-ns-bah-a6653798/) • [Twitter](https://twitter.com/nsbah20)

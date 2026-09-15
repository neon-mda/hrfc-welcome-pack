import requests
import streamlit as st

def generate_short_link(public_url: str, custom_path: str = None) -> str:
    # Use fallback dictionaries so the linter doesn't raise undefined warnings
    secrets = st.secrets if hasattr(st, "secrets") else {}
    api_key = secrets.get("SHORT_API_KEY", "dummy_key")
    domain = secrets.get("SHORT_DOMAIN", "hrfc.short.gy")

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": api_key
    }

    payload = {
        "originalURL": public_url,
        "domain": domain,
    }
    if custom_path:
        payload["path"] = custom_path

    response = requests.post("https://api.short.io/links", json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("shortURL")
    else:
        raise RuntimeError(f"Short.io API failed: {response.text}")
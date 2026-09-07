import requests
import streamlit as st

def generate_short_link(public_url: str, custom_path: str = None) -> str:
    api_key = st.secrets["SHORT_API_KEY"]
    domain = st.secrets["SHORT_DOMAIN"]
    
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
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import requests
import io
import platform
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Function definitions remain unchanged (setup_chrome_driver, extract_data, scrape_google_maps, etc.)
# ... (All functions like setup_chrome_driver, extract_data, scrape_google_maps, etc., remain the same)

def main():
    # Custom logo path
    logo_path = "calibrage.png"

    # Set page configuration
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon=logo_path,
        layout="wide"
    )

    # Apply custom CSS for styling
    def local_css():
        st.markdown("""
        <style>
            /* Center align the header */
            .header {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                margin-bottom: 20px;
            }
            /* Style for the logo */
            .logo {
                width: 150px;
                margin-bottom: 10px;
            }
            /* Search box styling */
            .stTextInput > div > div > input {
                padding: 10px;
                font-size: 16px;
                border-radius: 10px;
                border: 1px solid #ccc;
            }
            /* Button styling */
            .stButton > button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-size: 16px;
            }
            .stButton > button:hover {
                background-color: #45a049;
            }
            /* Hide the sidebar */
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """, unsafe_allow_html=True)

    # Apply custom CSS
    local_css()

    # Create a custom header container
    st.markdown("""
    <div class="header">
        <img src="https://github.com/rajendraambati/safron-search-engine/edit/main/calibrage.png" class="logo" alt="Calibrage Logo">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)

    # Search term instruction
    #st.write("Enter multiple search terms below (separated by commas). Example: palm oil, software companies in india")

    # Search term input with placeholder
    search_input = st.text_input("", placeholder="Enter your search key term...", key="search_input")
    search_queries = [query.strip() for query in search_input.split(",") if query.strip()]

    # Session state initialization
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'previous_queries' not in st.session_state:
        st.session_state.previous_queries = []
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False

    # Placeholders for dynamic content
    progress_placeholder = st.empty()
    success_placeholder = st.empty()   # Success message
    download_placeholder = st.empty()
    table_placeholder = st.empty()     # Table

    # Trigger scraping on new search queries
    if search_queries and search_queries != st.session_state.previous_queries:
        st.session_state.previous_queries = search_queries
        run_scraping(
            search_queries,
            progress_placeholder,
            table_placeholder,
            success_placeholder,
            download_placeholder
        )

    # Clear UI after download
    if st.session_state.download_clicked:
        progress_placeholder.empty()
        table_placeholder.empty()
        success_placeholder.empty()
        download_placeholder.empty()
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False

if __name__ == "__main__":
    main()

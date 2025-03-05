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
    format="%(asctime)s  - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def setup_chrome_driver():
    """Set up and return a Chrome WebDriver with additional options for cloud environment."""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-features=NetworkService")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-extensions")
        
        try:
            options.binary_location = "/usr/bin/chromium"
        except:
            try:
                options.binary_location = "/usr/bin/chromium-browser"
            except:
                st.warning("Could not set Chromium binary location.")

        try:
            service = Service(executable_path="/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
            return driver 
        except Exception as e:
            logging.error(f"First attempt failed: {str(e)}")
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                return driver
            except Exception as e:
                logging.error(f"Second attempt failed: {str(e)}")
                try:
                    driver = webdriver.Chrome(options=options)
                    return driver
                except Exception as e:
                    logging.error(f"All attempts failed: {str(e)}")
                    return None
    except Exception as e:
        logging.error(f"Error in setup_chrome_driver: {str(e)}")
        return None

def main():
    # Set page configuration
    st.set_page_config(
        page_title="Calibrage Info Systems",
        page_icon="🔍",
        layout="wide"
    )

    # Add logo
    logo_path = "logo.png"  # Replace with your logo file name or path
    col1, col2 = st.columns([1, 3])  # Create two columns for layout

    with col1:
        # Display the logo in the first column
        st.image(logo_path, width=150)  # Adjust width as needed

    with col2:
        # Add the title and subtitle in the second column
        st.title("🔍 Calibrage Data Search Engine")
        st.write("Enter multiple search terms below (separated by commas). Example: palm oil, software companies in india")

    # Rest of the code remains unchanged
    search_input = st.text_input("", key="search_input")
    search_queries = [query.strip() for query in search_input.split(",") if query.strip()]

    # Sidebar system info
    st.sidebar.markdown("### System Information")
    st.sidebar.text(f"Python: {platform.python_version()}")
    st.sidebar.text(f"System: {platform.system()}")
    st.sidebar.text(f"Platform: {platform.platform()}")

    # Session state initialization
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'previous_queries' not in st.session_state:
        st.session_state.previous_queries = []
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False

    # Placeholders for dynamic content
    progress_placeholder = st.empty()
    success_placeholder = st.empty()
    download_placeholder = st.empty()
    table_placeholder = st.empty()

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

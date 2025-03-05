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

# [Your existing setup_chrome_driver, extract_data, scrape_google_maps, 
# extract_emails_from_text, scrape_website_for_emails functions remain unchanged]

def run_scraping(search_query, progress_placeholder, table_placeholder, success_placeholder, download_placeholder):
    if not search_query.strip():
        st.error("Please enter a valid search query.")
        return
    
    driver = None
    try:
        driver = setup_chrome_driver()
        if driver is None:
            st.error("Failed to initialize Chrome driver.")
            return
        
        df = scrape_google_maps(search_query, driver, max_companies=1000)
        
        if df is not None and not df.empty:
            websites = df["Website"].tolist()
            email_results = []
            progress_bar = progress_placeholder.progress(0)
            
            for i, website in enumerate(websites):
                if website != "N/A" and isinstance(website, str) and website.strip():
                    urls_to_try = [f"http://{website}", f"https://{website}"]
                    emails_found = []
                    for url in urls_to_try:
                        try:
                            emails = scrape_website_for_emails(url)
                            emails_found.extend(emails)
                        except Exception as e:
                            logging.warning(f"Error scraping emails from {url}: {str(e)}")
                    email_results.append(", ".join(set(emails_found)) if emails_found else "N/A")
                else:
                    email_results.append("N/A")
                progress_bar.progress((i + 1) / len(websites))
            
            df["Email"] = email_results
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            st.session_state.scraping_completed = True
            table_placeholder.table(df)
            success_placeholder.success("Done! 👇Click Download Button Below")
            download_placeholder.download_button(
                label="Download Results",
                data=excel_data,
                file_name="Calibrage Data Extraction.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=lambda: setattr(st.session_state, 'download_clicked', True)
            )
        else:
            st.warning("No results found for the given search query.")
    except Exception as e:
        st.error(f"An error occurred during scraping: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def main():
    st.set_page_config(
        page_title="Calibrage Info Systems",
        page_icon="🔍",
        layout="wide"
    )

    st.title("🔍 Calibrage Info Systems Data Search Engine")
    st.write("Enter the search Term Below 👇 (e.g: palm oil, software companies in india)")

    # Use a form to handle Enter key press
    with st.form(key="search_form"):
        search_query = st.text_input("", key="search_input")
        submit_button = st.form_submit_button(label="Search")  # Optional button, Enter also works

    # Sidebar system info
    st.sidebar.markdown("### System Information")
    st.sidebar.text(f"Python: {platform.python_version()}")
    st.sidebar.text(f"System: {platform.system()}")
    st.sidebar.text(f"Platform: {platform.platform()}")

    # Session state initialization
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False

    # Placeholders for dynamic content
    progress_placeholder = st.empty()
    table_placeholder = st.empty()
    success_placeholder = st.empty()
    download_placeholder = st.empty()

    # Trigger scraping when form is submitted (Enter pressed or button clicked)
    if submit_button or (search_query.strip() and st.session_state.get("form_submitted", False)):
        st.session_state.form_submitted = True
        run_scraping(
            search_query,
            progress_placeholder,
            table_placeholder,
            success_placeholder,
            download_placeholder
        )

    # Clear UI and reset state after download
    if st.session_state.download_clicked:
        progress_placeholder.empty()
        table_placeholder.empty()
        success_placeholder.empty()
        download_placeholder.empty()
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False
        st.session_state.form_submitted = False  # Reset form submission state
        # Clear the input field by resetting the widget key
        st.session_state.search_input = ""  # This clears the text input

if __name__ == "__main__":
    main()
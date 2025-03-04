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

# [Previous function definitions remain unchanged: setup_chrome_driver, extract_data, 
# scrape_google_maps, extract_emails_from_text, scrape_website_for_emails]

def run_scraping(search_query, progress_bar_placeholder, download_button_placeholder, 
                success_message_placeholder, result_table_placeholder):
    """
    Run the scraping process for the given search query with UI updates.
    """
    if not search_query.strip():
        st.error("Please enter a valid search query.")
        return
    
    driver = None
    try:
        driver = setup_chrome_driver()
        
        if driver is None:
            st.error("""
             Failed to initialize Chrome driver. This could be due to:
            1. Chrome browser not installed
            2. Running in a restricted environment
            3. System compatibility issues
            """)
            return
        
        df = scrape_google_maps(search_query, driver, max_companies=1000)
        
        if df is not None and not df.empty:
            websites = df["Website"].tolist()
            email_results = []
            
            # 4. Show progress bar
            progress_bar = progress_bar_placeholder.progress(0)
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
                
                # Update progress bar
                progress_bar.progress((i + 1) / len(websites))
            
            df["Email"] = email_results
            
            # Prepare Excel data
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            # Mark scraping as completed
            st.session_state.scraping_completed = True
            
            # 7. Display results table
            result_table_placeholder.table(df)
            
            # 5. Show success message
            success_message_placeholder.success("Done! 👇Click Download Button Below")
            
            # 6. Add download button
            download_button_placeholder.download_button(
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

    # 1. Site title
    st.title("🔍 Calibrage Info Systems Data Search Engine")
    
    # Sidebar with system info
    st.sidebar.markdown("### System Information")
    st.sidebar.text(f"Python: {platform.python_version()}")
    st.sidebar.text(f"System: {platform.system()}")
    st.sidebar.text(f"Platform: {platform.platform()}")
    
    # Session state initialization
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'previous_query' not in st.session_state:
        st.session_state.previous_query = ""
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False
    
    # 2. Instruction text
    st.markdown("Enter the search Term Below 👇 (e.g: palm oil, software companies in india)")
    
    # 3. Search box
    search_query = st.text_input("", key="search_input")
    
    # Create placeholders for remaining UI elements
    progress_bar_placeholder = st.empty()    # 4
    success_message_placeholder = st.empty() # 5
    download_button_placeholder = st.empty() # 6
    result_table_placeholder = st.empty()    # 7
    
    # Trigger scraping when new search query is entered
    if search_query.strip() and search_query != st.session_state.previous_query:
        st.session_state.previous_query = search_query
        run_scraping(
            search_query,
            progress_bar_placeholder,
            download_button_placeholder,
            success_message_placeholder,
            result_table_placeholder
        )
    
    # Clear UI after download
    if st.session_state.download_clicked:
        progress_bar_placeholder.empty()
        success_message_placeholder.empty()
        download_button_placeholder.empty()
        result_table_placeholder.empty()
        
        # Reset session state
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False
        st.session_state.previous_query = ""

if __name__ == "__main__":
    main()

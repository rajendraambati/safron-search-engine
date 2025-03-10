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
import logging

# Custom CSS for layout and styling
st.markdown("""
<style>
    /* Main container styling */
    .main-container {
        padding: 2rem;
    }
    
    /* Search input styling */
    .search-input {
        width: 60%;
        margin-bottom: 1rem;
    }
    
    /* Button container positioning */
    .button-container {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        width: 60%;
        margin-bottom: 2rem;
    }
    
    /* Clear button styling */
    .clear-button {
        position: relative;
        bottom: 1.5rem;
        left: 1rem;
        background-color: #ff4444 !important;
    }
    
    /* Sidebar log styling */
    .sidebar-log {
        height: 60vh;
        overflow-y: auto;
        padding: 1rem;
        background-color: #f0f0f0;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Custom logging handler for Streamlit
class StreamlitLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
        self.placeholder = st.sidebar.empty()
        
    def emit(self, record):
        if 'label got an empty value' in record.getMessage():
            return  # Filter out Streamlit's label warnings
        msg = self.format(record)
        self.logs.append(msg)
        self.placeholder.markdown(f"```\\n{'\\n'.join(self.logs[-20:])}\\n```")

# Setup logging
logger = logging.getLogger()
handler = StreamlitLogHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def setup_chrome_driver():
    """Setup Chrome driver with enhanced error handling"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except Exception as e:
        logger.error(f"Driver setup failed: {str(e)}")
        return None

def extract_data(xpath, driver):
    """Safely extract data using XPath"""
    try:
        return driver.find_element(By.XPATH, xpath).text
    except:
        return "N/A"

def scrape_google_maps(search_query, driver, max_companies=1000):
    """Enhanced Google Maps scraping function"""
    try:
        driver.get("https://www.google.com/maps")
        search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
        search_box.send_keys(search_query + Keys.ENTER)
        time.sleep(5)
        
        # Zoom out for better results visibility
        for _ in range(5):
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(1)
            
        # Scroll to load all results
        scrollable = driver.find_element(By.XPATH, '//div[@aria-label="Results for"]')
        last_height = 0
        
        while True:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable)
            time.sleep(3)
            new_height = scrollable.size['height']
            if new_height == last_height:
                break
            last_height = new_height
            
        results = []
        for listing in driver.find_elements(By.XPATH, '//a[contains(@href, "/maps/place/")]'):
            href = listing.get_attribute('href')
            if href:
                driver.get(href)
                time.sleep(3)
                results.append({
                    "Name": extract_data('//h1', driver),
                    "Address": extract_data('//button[@data-item-id="address"]', driver),
                    "Phone": extract_data('//button[@data-item-id^="phone"]', driver),
                    "Website": extract_data('//a[@data-item-id="authority"]', driver)
                })
                logger.info(f"Scraped: {results[-1]['Name']}")
                
        return pd.DataFrame(results)
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        return pd.DataFrame()

def run_scraping(search_terms, progress, table, success, download):
    """Main scraping workflow with progress tracking"""
    driver = setup_chrome_driver()
    if not driver:
        st.error("Failed to initialize browser driver")
        return

    try:
        all_results = []
        for term in search_terms:
            df = scrape_google_maps(term, driver)
            if not df.empty:
                # Scrape emails from websites
                df['Email'] = df['Website'].apply(lambda url: 
                    ', '.join(scrape_website_emails(url)) if pd.notna(url) else "N/A")
                all_results.append(df)
                
            progress.progress(0.5)
            
        if all_results:
            final_df = pd.concat(all_results)
            table.dataframe(final_df)
            excel_io = io.BytesIO()
            final_df.to_excel(excel_io, index=False)
            download.download_button(
                "Download Results",
                excel_io,
                "calibrage_data.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            success.success("Scraping completed successfully!")
    finally:
        driver.quit()

def main():
    # Page configuration
    st.set_page_config(
        page_title="Calibrage Maps Scraper",
        layout="wide",
        page_icon="🗺️"
    )
    
    # Header section
    st.markdown("""
    <div class="header">
        <img src="https://github.com/rajendraambati/safron-search-engine/raw/main/calibrage.jpg" 
             style="width:150px; margin:20px;">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Search input with proper labeling
    search_terms = st.text_input(
        "Search Terms", 
        placeholder="Enter comma-separated search terms...",
        label_visibility="hidden",
        key="search_input",
        help="Enter multiple terms separated by commas"
    )
    
    # Button container with clear button positioning
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            search_btn = st.button("Start Scraping", use_container_width=True)
        with col2:
            st.markdown('<div class="clear-button">', unsafe_allow_html=True)
            clear_btn = st.button("Clear All", key="clear_btn", help="Reset the application")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Dynamic content placeholders
    progress_bar = st.empty()
    results_table = st.empty()
    success_msg = st.empty()
    download_btn = st.empty()
    
    # Clear button handler
    if clear_btn:
        st.session_state.search_input = ""
        progress_bar.empty()
        results_table.empty()
        success_msg.empty()
        download_btn.empty()
        st.rerun()
    
    # Search button handler
    if search_btn:
        terms = [t.strip() for t in search_terms.split(",") if t.strip()]
        if terms:
            with st.spinner("Initializing browser..."):
                run_scraping(terms, progress_bar, results_table, success_msg, download_btn)
        else:
            st.error("Please enter valid search terms")

if __name__ == "__main__":
    main()

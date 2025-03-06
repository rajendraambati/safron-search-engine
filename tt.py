import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
import requests
import io
import platform
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def setup_chrome_driver():
    """Set up and return a Chrome WebDriver with additional options for Linux environment."""
    try:
        logging.info(f"Setting up Chrome driver for: Python {sys.version}, {platform.system()} {platform.release()}")
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-features=NetworkService")
        options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        # Check for common Chromium paths in Linux
        linux_chrome_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable"
        ]
        
        chrome_path = None
        for path in linux_chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                logging.info(f"Found Chrome/Chromium at: {chrome_path}")
                break
        
        if chrome_path:
            options.binary_location = chrome_path
        
        # Try multiple methods to initialize the driver
        driver_attempts = [
            lambda: webdriver.Chrome(service=Service(executable_path="/usr/bin/chromedriver"), options=options),
            lambda: webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options),
            lambda: webdriver.Chrome(options=options)
        ]
        
        for i, attempt in enumerate(driver_attempts, 1):
            try:
                driver = attempt()
                logging.info(f"Chrome driver initialized successfully (method {i})")
                return driver
            except Exception as e:
                logging.error(f"Attempt {i} failed: {str(e)}")
        
        return None
    except Exception as e:
        logging.error(f"Driver setup failed: {str(e)}")
        return None

def extract_data(xpath, driver, wait_time=10):
    """Extract data from the page using the provided XPath with waiting."""
    try:
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        element = driver.find_element(By.XPATH, xpath)
        return element.text.strip()
    except Exception as e:
        logging.warning(f"Failed to extract data with XPath '{xpath}': {str(e)}")
        return "N/A"

def try_alternative_selectors(driver, selectors_dict):
    """Try multiple selectors for each data point and use the first one that works."""
    results = {}
    for data_type, selector_list in selectors_dict.items():
        for selector in selector_list:
            try:
                element = driver.find_element(By.XPATH, selector)
                if element and element.text.strip():
                    results[data_type] = element.text.strip()
                    break
            except:
                continue
        results[data_type] = results.get(data_type, "N/A")
    return results

def scrape_google_maps(search_query, driver, max_companies=50):
    """Scrape Google Maps for company details with more robust handling."""
    try:
        logging.info(f"Starting to scrape Google Maps for: '{search_query}'")
        
        # Navigate to Google Maps
        driver.get("https://www.google.com/maps")
        time.sleep(5)
        
        # Handle consent popup if present
        try:
            consent_button = driver.find_element(By.XPATH, '//button[@aria-label="Accept all"]')
            consent_button.click()
            time.sleep(2)
        except:
            pass
        
        # Enter search query
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//input[@id="searchboxinput"]'))
        )
        search_box.clear()
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)
        
        # Zoom out to see more results
        for _ in range(5):
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
        
        # Scroll and collect results
        scrollable_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]'))
        )
        
        all_listings = set()
        prev_height = 0
        scroll_attempts = 0
        
        while scroll_attempts < 20:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(3)
            
            # Extract listings
            listings = driver.find_elements(By.XPATH, '//a[contains(@href, "/maps/place/")]')
            current_listings = [listing.get_attribute("href") for listing in listings]
            all_listings.update(current_listings)
            
            # Check if we've reached the bottom
            new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            if new_height == prev_height:
                break
            prev_height = new_height
            scroll_attempts += 1
        
        # Process each listing
        results = []
        for i, href in enumerate(all_listings):
            if i >= max_companies:
                break
                
            try:
                driver.get(href)
                time.sleep(5)
                
                # Extract details with multiple selectors
                selectors = {
                    "Name": [
                        '//h1[contains(@class, "DUwDvf")]',
                        '//h1[@class="fontHeadlineLarge"]'
                    ],
                    "Address": [
                        '//button[@data-item-id="address"]//div[@class="fontBodyMedium"]',
                        '//div[contains(text(), "Address")]/following-sibling::div'
                    ],
                    "Phone": [
                        '//button[@data-item-id="phone:tel:"]//div[@class="fontBodyMedium"]',
                        '//div[contains(text(), "Phone")]/following-sibling::div'
                    ],
                    "Website": [
                        '//a[@data-item-id="authority"]//div[@class="fontBodyMedium"]',
                        '//a[contains(@aria-label, "Website")]'
                    ]
                }
                
                data = try_alternative_selectors(driver, selectors)
                
                results.append({
                    "Name": data["Name"],
                    "Address": data["Address"],
                    "Phone Number": data["Phone"],
                    "Website": data["Website"]
                })
                
                logging.info(f"Processed {i+1}/{len(all_listings)}: {data['Name']}")
            except Exception as e:
                logging.warning(f"Error processing {href}: {str(e)}")
                continue
        
        return pd.DataFrame(results) if results else None
    except Exception as e:
        logging.error(f"Error in scrape_google_maps: {str(e)}")
        return None

def extract_emails_from_text(text):
    """Extract email addresses from text using regex."""
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def scrape_website_for_emails(url, timeout=15):
    """Scrape a website for email addresses with increased timeout."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        response = requests.get(url, timeout=timeout, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        emails = set(extract_emails_from_text(soup.get_text()))
        
        # Check footer
        footer = soup.find('footer')
        if footer:
            emails.update(extract_emails_from_text(footer.get_text()))
        
        # Check contact pages
        for a in soup.find_all('a', href=True):
            if 'contact' in a['href'].lower() or 'about' in a['href'].lower():
                full_url = a['href'] if a['href'].startswith('http') else f"{url}/{a['href']}"
                try:
                    contact_response = requests.get(full_url, timeout=timeout, headers=headers)
                    contact_soup = BeautifulSoup(contact_response.content, 'html.parser')
                    emails.update(extract_emails_from_text(contact_soup.get_text()))
                except:
                    continue
        
        return list(emails)
    except Exception as e:
        logging.warning(f"Error scraping emails from {url}: {str(e)}")
        return []

def run_scraping(search_queries, progress, table, success, download):
    """Run scraping for multiple search queries and update results dynamically."""
    if not search_queries:
        st.error("Please enter at least one valid search query.")
        return
    
    driver = None
    cumulative_results = []
    
    try:
        # Initialize Chrome driver
        progress.info("Setting up web browser...")
        driver = setup_chrome_driver()
        
        if driver is None:
            st.error("Failed to initialize Chrome driver. Please check system compatibility.")
            return
        
        for query in search_queries:
            progress.info(f"Processing: {query}")
            df = scrape_google_maps(query, driver)
            
            if df is not None and not df.empty:
                # Extract emails
                progress.info("Extracting email addresses...")
                df["Email"] = df["Website"].apply(lambda url: 
                    ", ".join(scrape_website_for_emails(url)) if url != "N/A" else "N/A"
                )
                
                cumulative_results.append(df)
                table.dataframe(pd.concat(cumulative_results))
                success.success(f"✅ Processed '{query}' ({len(df)} results)")
            else:
                st.warning(f"No results found for: {query}")
        
        # Create download button
        if cumulative_results:
            final_df = pd.concat(cumulative_results)
            excel = io.BytesIO()
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                final_df.to_excel(writer, index=False)
            excel.seek(0)
            
            download.download_button(
                label="Download Results (Excel)",
                data=excel,
                file_name="calibrage_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        if driver:
            driver.quit()

def main():
    # Page configuration
    st.set_page_config(
        page_title="Calibrage Data Search",
        page_icon="🔍",
        layout="wide"
    )

    # Custom CSS
    st.markdown("""
    <style>
        .stButton>button { background-color: #4CAF50; color: white; }
        .stDownloadButton>button { background-color: #008CBA; }
        .main { padding: 2rem; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #2c3e50;">Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)

    # Input section
    with st.form("search_form", clear_on_submit=False):
        st.text_input(
            label="Enter search terms (comma-separated)",
            placeholder="e.g., palm oil companies in guntur",
            key="search_input",
            label_visibility="visible"
        )
        col1, col2 = st.columns(2)
        with col1:
            max_results = st.slider("Max results per query", 10, 100, 50)
        with col2:
            wait_time = st.slider("Page load wait time (sec)", 3, 10, 5)
        submitted = st.form_submit_button("🔍 Search")

    # Initialize session state
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False

    # Process search
    if submitted:
        search_queries = [q.strip() for q in st.session_state.search_input.split(",") if q.strip()]
        if search_queries:
            progress = st.empty()
            table = st.empty()
            success = st.empty()
            download = st.empty()
            
            run_scraping(
                search_queries=search_queries,
                progress=progress,
                table=table,
                success=success,
                download=download
            )
        else:
            st.error("Please enter at least one search term")

    # Footer
    st.markdown("---")
    st.markdown("© 2025 Calibrage Data Search Engine | For business inquiries only", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

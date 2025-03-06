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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def setup_chrome_driver():
    """Set up and return a Chrome WebDriver with optimized options"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    
    try:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except Exception as e:
        logging.error(f"Driver setup failed: {str(e)}")
        return None

def extract_data(xpath, driver, wait_time=10):
    """Extract data with explicit waits"""
    try:
        element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return element.text.strip()
    except:
        return "N/A"

def scrape_google_maps(search_query, driver, max_companies=1000):
    try:
        driver.get("https://www.google.com/maps")
        
        # Improved search handling
        search_box = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, '//input[@id="searchboxinput"]'))
        )
        search_box.clear()
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        
        # Wait for results container
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//div[@role="main"]//div[@role="feed"]'))
        )
        
        # Scroll to load all results
        scroll_container = driver.find_element(By.XPATH, '//div[@role="main"]//div[@role="feed"]')
        last_height = 0
        retry_count = 0
        
        while len(driver.find_elements(By.XPATH, '//a[contains(@href, "/maps/place/")]')) < max_companies and retry_count < 5:
            driver.execute_script("arguments[0].scrollBy(0, 2000)", scroll_container)
            time.sleep(2)
            
            new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
            if new_height == last_height:
                retry_count += 1
            else:
                retry_count = 0
            last_height = new_height
        
        # Collect all listing URLs
        listings = set()
        for elem in driver.find_elements(By.XPATH, '//a[contains(@href, "/maps/place/")]'):
            href = elem.get_attribute("href").split("?")[0]
            listings.add(href)
        
        results = []
        for idx, url in enumerate(listings):
            if idx >= max_companies:
                break
            try:
                driver.get(url)
                name = extract_data('//h1[contains(@class, "DUwDvf")]', driver)
                address = extract_data('//button[@data-item-id="address"]', driver)
                phone = extract_data('//button[starts_with(@data-item-id, "phone")]', driver)
                website = extract_data('//a[@data-item-id="authority"]//div[@class="Io6YTe"]', driver)
                
                results.append({
                    "Name": name,
                    "Address": address,
                    "Phone": phone,
                    "Website": website
                })
                logging.info(f"Processed {idx+1}/{len(listings)}: {name}")
            except Exception as e:
                logging.warning(f"Error processing {url}: {str(e)}")
        
        return pd.DataFrame(results) if results else None
    except Exception as e:
        logging.error(f"Google Maps scraping failed: {str(e)}")
        return None

def scrape_website_for_emails(url):
    """Enhanced email scraping with better error handling"""
    if not url or "example.com" in url:
        return []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        response = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract from text content
        emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', soup.get_text()))
        
        # Check footer specifically
        footer = soup.find('footer')
        if footer:
            emails.update(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', footer.get_text()))
        
        # Check contact pages
        for link in soup.find_all('a', href=True):
            if 'contact' in link['href'].lower():
                full_url = requests.compat.urljoin(url, link['href'])
                try:
                    contact_resp = requests.get(full_url, timeout=10, headers=headers)
                    emails.update(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', contact_resp.text))
                except:
                    continue
        
        return list(emails)
    except Exception as e:
        logging.warning(f"Email scraping failed for {url}: {str(e)}")
        return []

def run_scraping(search_query, progress_placeholder, table_placeholder, success_placeholder, download_placeholder):
    if not search_query.strip():
        st.error("Please enter a valid search query")
        return
    
    driver = None
    try:
        driver = setup_chrome_driver()
        if not driver:
            st.error("Failed to initialize browser")
            return
        
        df = scrape_google_maps(search_query, driver)
        
        if df is None or df.empty:
            st.warning("No results found for this search query")
            return
        
        # Process websites for emails
        websites = df["Website"].tolist()
        email_results = []
        progress_bar = progress_placeholder.progress(0)
        
        for i, website in enumerate(websites):
            if website != "N/A" and isinstance(website, str):
                emails = []
                for prefix in ('http://', 'https://'):
                    full_url = prefix + website if not website.startswith(('http', 'www')) else website
                    try:
                        emails = scrape_website_for_emails(full_url)
                        if emails:
                            break
                    except:
                        continue
                email_results.append(", ".join(emails) if emails else "N/A")
            else:
                email_results.append("N/A")
            progress_bar.progress((i+1)/len(websites))
        
        df["Email"] = email_results
        
        # Prepare Excel download
        excel_data = io.BytesIO()
        with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        excel_data.seek(0)
        
        table_placeholder.write(df)
        success_placeholder.success("Scraping completed successfully!")
        download_placeholder.download_button(
            label="Download Results",
            data=excel_data,
            file_name=f"{search_query.replace(' ', '_')}_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        if driver:
            driver.quit()

# Streamlit app setup
def main():
    logo_path = "calibrage.jpg"

    # Set page configuration
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon=logo_path,
        layout="wide"
    )


    st.title("🔍 Business Intelligence Scraper")
    st.write("Enter search terms like: 'Software companies in California' or 'Restaurants in Tokyo'")
    
    search_query = st.text_input("Search Query", key="search_input")
    
    # Placeholders for dynamic content
    progress_placeholder = st.empty()
    table_placeholder = st.empty()
    success_placeholder = st.empty()
    download_placeholder = st.empty()
    
    if st.button("Start Scraping"):
        with st.spinner("Initializing..."):
            run_scraping(
                search_query,
                progress_placeholder,
                table_placeholder,
                success_placeholder,
                download_placeholder
            )

if __name__ == "__main__":
    main()

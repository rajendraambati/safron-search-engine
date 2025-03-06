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

def extract_data(xpath, driver):
    """Extract data from the page using the provided XPath."""
    try:
        element = driver.find_element(By.XPATH, xpath)
        return element.text
    except:
        return "N/A"

def scrape_google_maps(search_query, driver, max_companies=1000):
    """Scrape Google Maps for company details based on the search query."""
    try:
        driver.get("https://www.google.com/maps")
        time.sleep(5)
        search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)
        
        actions = ActionChains(driver)
        for _ in range(10):
            actions.key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(1)
        
        all_listings = set()
        previous_count = 0
        max_scrolls = 50
        scroll_attempts = 0
        
        while scroll_attempts < max_scrolls:
            try:
                scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for")]')
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(3)
                current_listings = driver.find_elements(By.XPATH, '//a[contains(@href, "https://www.google.com/maps/place")]')
                current_count = len(current_listings)
                
                for listing in current_listings:
                    href = listing.get_attribute("href")
                    if href:
                        all_listings.add(href)
                
                if current_count == previous_count or len(all_listings) >= max_companies:
                    break
                previous_count = current_count
                scroll_attempts += 1
            except Exception as e:
                logging.warning(f"Error during scrolling: {str(e)}")
                break
        
        results = []
        for i, href in enumerate(all_listings): 
            if i >= max_companies:
                break
            try:
                driver.get(href)
                time.sleep(3)
                name = extract_data('//h1[contains(@class, "DUwDvf lfPIob")]', driver)
                address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', driver)
                phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', driver)
                website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', driver)
                
                results.append({
                    "Name": name,
                    "Address": address,
                    "Phone Number": phone,
                    "Website": website
                })
                logging.info(f"Scraped company: {name}")
            except Exception as e:
                logging.warning(f"Error processing listing {i+1}: {str(e)}")
                continue
        
        return pd.DataFrame(results) if results else None
    except Exception as e:
        logging.error(f"Error in scrape_google_maps: {str(e)}")
        return None

def extract_emails_from_text(text):
    """Extract email addresses from text using regex."""
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def scrape_website_for_emails(url):
    """Scrape a website for email addresses."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        emails = set(extract_emails_from_text(soup.get_text()))
        footer = soup.find('footer')
        if footer:
            emails.update(extract_emails_from_text(footer.get_text()))
        
        contact_links = [a['href'] for a in soup.find_all('a', href=True) if 'contact' in a['href'].lower()]
        for link in contact_links:
            if not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")
            try:
                contact_response = requests.get(link, timeout=10)
                contact_soup = BeautifulSoup(contact_response.content, 'html.parser')
                emails.update(extract_emails_from_text(contact_soup.get_text()))
            except Exception:
                continue 
        return list(emails)
    except Exception:
        return []

def run_scraping(search_query, progress_placeholder, table_placeholder, success_placeholder, download_placeholder):
    """Run scraping for the given search query."""
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
                file_name="Calibrage_Data_Extraction.xlsx",
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
    
    # 2. Search term instruction
    st.write("Enter the search Term Below 👇 (e.g: palm oil, software companies in india)")
    
    # 3. Search term input
    search_query = st.text_input("", key="search_input", on_change=lambda: setattr(st.session_state, 'force_run', True))
    
    # Sidebar system info
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
    if 'force_run' not in st.session_state:
        st.session_state.force_run = False
    
    # 4-7. Placeholders for dynamic content
    progress_placeholder = st.empty()  # 4. Progress bar
    table_placeholder = st.empty()     # 5. Table
    success_placeholder = st.empty()   # 6. Success message
    download_placeholder = st.empty()  # 7. Download button
    
    # Trigger scraping on new search query or force run
    if (search_query.strip() and search_query != st.session_state.previous_query) or st.session_state.force_run:
        st.session_state.previous_query = search_query
        st.session_state.force_run = False  # Reset the force_run flag
        run_scraping(
            search_query,
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

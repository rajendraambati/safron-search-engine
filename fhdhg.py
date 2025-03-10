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

def run_scraping(search_queries, progress_placeholder, table_placeholder, success_placeholder, download_placeholder):
    """Run scraping for multiple search queries and update results dynamically."""
    if not search_queries:
        st.error("Please enter at least one valid search query.")
        return
    
    driver = None
    cumulative_results = []
    try:
        driver = setup_chrome_driver()
        if driver is None:
            st.error("Failed to initialize Chrome driver.")
            return
        
        for query_index, search_query in enumerate(search_queries):
            st.session_state.current_query = search_query
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
                cumulative_results.append(df)
                combined_df = pd.concat(cumulative_results, ignore_index=True)
                table_placeholder.table(combined_df)
                success_placeholder.success(f"Query {query_index + 1}/{len(search_queries)} completed.")
            else:
                st.warning(f"No results found for the query: {search_query}")
        
        if cumulative_results:
            combined_df = pd.concat(cumulative_results, ignore_index=True)
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                combined_df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            st.session_state.scraping_completed = True
            success_placeholder.success("All queries completed! 👇 Click Download Button Below")
            download_placeholder.download_button(
                label="Download Results",
                data=excel_data,
                file_name="Calibrage_Data_Extraction.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=lambda: setattr(st.session_state, 'download_clicked', True)
            )
        else:
            st.warning("No results found for any of the queries.")
    except Exception as e:
        st.error(f"An error occurred during scraping: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
# ... (previous code remains the same until the main function)

def main():
    # Set page configuration first
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon="calibrage.jpg",
        layout="wide"
    )
    
    # Custom CSS (unchanged)
    st.markdown("""
    <style>
        /* Hide left sidebar */
        .stSidebar {
            display: none !important;
        }
        
        /* Center main content */
        .main-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        /* Search input styling */
        .search-input input {
            width: 100% !important;
            margin-bottom: 1rem;
        }
        
        /* Search container */
        .search-container {
            width: 40%;
            margin: 0 auto;
        }
        
        /* Button styling */
        .search-button, .clear-button {
            width: 48%;
            padding: 10px;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .search-button {
            background-color: #4CAF50 !important;
        }
        
        .clear-button {
            background-color: #ff4444 !important;
        }
        
        /* Button container */
        .button-container {
            display: flex;
            justify-content: space-between;
            width: 40%;
            margin: 0 auto;
            margin-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header section (unchanged)
    st.markdown("""
    <div class="header" style="text-align: center;">
        <img src="https://github.com/rajendraambati/safron-search-engine/raw/main/calibrage.jpg" 
             style="width:150px; margin:20px;">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state for controlling clear action
    if 'clear_trigger' not in st.session_state:
        st.session_state.clear_trigger = False
    if 'search_terms' not in st.session_state:
        st.session_state.search_terms = ""

    # Search container
    with st.container():
        st.markdown('<div class="search-container">', unsafe_allow_html=True)
        
        # Search input - Use a separate variable instead of direct session state manipulation
        search_input = st.text_input(
            "Search Terms", 
            value=st.session_state.search_terms,
            placeholder="Enter comma-separated search terms...",
            label_visibility="hidden",
            key="search_input",
            help="Enter multiple terms separated by commas"
        )
        
        # Update session state with input
        st.session_state.search_terms = search_input
        
        # Button container
        st.markdown('<div class="button-container">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            search_btn = st.button("Search", use_container_width=True, key="search_btn")
        with col2:
            clear_btn = st.button("Clear", use_container_width=True, key="clear_btn")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

    # Dynamic content placeholders
    progress_bar = st.empty()
    results_table = st.empty()
    success_msg = st.empty()
    download_btn = st.empty()
    
    # Clear button handler
    if clear_btn:
        # Reset session state variables
        st.session_state.search_terms = ""
        st.session_state.clear_trigger = True
        
        # Clear all output elements
        progress_bar.empty()
        results_table.empty()
        success_msg.empty()
        download_btn.empty()
        
        # Trigger a rerun to refresh the UI
        st.experimental_rerun()

    # Search button handler
    if search_btn:
        terms = [t.strip() for t in st.session_state.search_terms.split(",") if t.strip()]
        if terms:
            with st.spinner("Initializing browser..."):
                run_scraping(terms, progress_bar, results_table, success_msg, download_btn)
        else:
            st.error("Please enter valid search terms")

if __name__ == "__main__":
    main()

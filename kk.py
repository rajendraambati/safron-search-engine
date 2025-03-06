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
        options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
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
            # Method 1: Use system chromedriver
            lambda: webdriver.Chrome(service=Service(executable_path="/usr/bin/chromedriver"), options=options),
            # Method 2: Use webdriver_manager
            lambda: webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options),
            # Method 3: Just use options
            lambda: webdriver.Chrome(options=options)
        ]
        
        for i, attempt in enumerate(driver_attempts, 1):
            try:
                logging.info(f"Driver initialization attempt {i}")
                driver = attempt()
                logging.info(f"Chrome driver successfully initialized with method {i}")
                return driver
            except Exception as e:
                logging.error(f"Attempt {i} failed: {str(e)}")
                continue
        
        logging.error("All driver initialization attempts failed")
        return None
    except Exception as e:
        logging.error(f"Error in setup_chrome_driver: {str(e)}")
        return None

def extract_data(xpath, driver, wait_time=5):
    """Extract data from the page using the provided XPath with waiting."""
    try:
        # Wait for the element to be present
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        element = driver.find_element(By.XPATH, xpath)
        return element.text
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
                    results[data_type] = element.text
                    break
            except:
                continue
        if data_type not in results:
            results[data_type] = "N/A"
    return results

def scrape_google_maps(search_query, driver, max_companies=50):
    """Scrape Google Maps for company details with more robust handling."""
    try:
        logging.info(f"Starting to scrape Google Maps for: '{search_query}'")
        
        # Navigate to Google Maps
        driver.get("https://www.google.com/maps")
        time.sleep(7)  # Increased wait time for initial page load
        
        # Check if search box is available
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[@id="searchboxinput"]'))
            )
            search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
            logging.info("Search box found")
        except Exception as e:
            logging.error(f"Search box not found: {str(e)}")
            # Try an alternative search box selector
            try:
                search_box = driver.find_element(By.XPATH, '//input[contains(@class, "searchbox")]')
                logging.info("Alternative search box found")
            except:
                logging.error("Could not find any search input")
                # Save screenshot for debugging
                driver.save_screenshot("maps_error.png")
                return None
        
        # Enter search query and submit
        search_box.clear()
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        logging.info(f"Submitted query: {search_query}")
        time.sleep(7)  # Increased wait time for search results
        
        # Zoom out to see more results
        actions = ActionChains(driver)
        for _ in range(10):
            actions.key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(0.5)
        
        # Debug: Take screenshot of search results
        driver.save_screenshot("search_results.png")
        logging.info("Zoomed out to see more results")
        
        # Collect all listings by scrolling
        all_listings = set()
        previous_count = 0
        max_scrolls = 20  # Reduced from 50 to make the process faster
        scroll_attempts = 0
        
        # Try different selectors for the results container
        scrollable_div_selectors = [
            '//div[contains(@aria-label, "Results for")]',
            '//div[contains(@role, "feed")]',
            '//div[contains(@class, "section-layout")]'
        ]
        
        scrollable_div = None
        for selector in scrollable_div_selectors:
            try:
                scrollable_div = driver.find_element(By.XPATH, selector)
                logging.info(f"Found scrollable results container with selector: {selector}")
                break
            except:
                continue
        
        if not scrollable_div:
            logging.error("Could not find results container")
            return None
        
        while scroll_attempts < max_scrolls:
            try:
                # Scroll down in the results panel
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(3)
                
                # Try different selectors for listings
                listing_selectors = [
                    '//a[contains(@href, "https://www.google.com/maps/place")]',
                    '//div[contains(@class, "section-result")]//a',
                    '//div[@role="article"]//a'
                ]
                
                current_listings = []
                for selector in listing_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        if elements:
                            current_listings = elements
                            break
                    except:
                        continue
                
                current_count = len(current_listings)
                logging.info(f"Found {current_count} listings on scroll attempt {scroll_attempts+1}")
                
                for listing in current_listings:
                    try:
                        href = listing.get_attribute("href")
                        if href and "maps/place" in href:
                            all_listings.add(href)
                    except:
                        continue
                
                if current_count == previous_count or len(all_listings) >= max_companies:
                    logging.info(f"Stopping scrolling: Found {len(all_listings)} unique listings")
                    break
                    
                previous_count = current_count
                scroll_attempts += 1
            except Exception as e:
                logging.warning(f"Error during scrolling: {str(e)}")
                break
        
        logging.info(f"Total unique listings found: {len(all_listings)}")
        if len(all_listings) == 0:
            logging.error("No listings found. Check if Google Maps layout has changed.")
            return None
        
        # Process each listing
        results = []
        for i, href in enumerate(all_listings):
            if i >= max_companies:
                break
                
            try:
                logging.info(f"Processing listing {i+1}/{len(all_listings)}: {href}")
                driver.get(href)
                time.sleep(5)  # Wait for page to load
                
                # Try multiple selectors for each data type
                selectors = {
                    "Name": [
                        '//h1[contains(@class, "DUwDvf")]',
                        '//h1',
                        '//div[contains(@class, "fontHeadlineLarge")]'
                    ],
                    "Address": [
                        '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]',
                        '//button[contains(@aria-label, "Address")]/following-sibling::div',
                        '//div[contains(text(), "Address")]/following-sibling::div'
                    ],
                    "Phone": [
                        '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]',
                        '//button[contains(@aria-label, "Phone")]/following-sibling::div',
                        '//div[contains(text(), "Phone")]/following-sibling::div'
                    ],
                    "Website": [
                        '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]',
                        '//a[contains(@aria-label, "Website")]',
                        '//a[contains(text(), "Website")]'
                    ]
                }
                
                data = try_alternative_selectors(driver, selectors)
                
                results.append({
                    "Name": data["Name"],
                    "Address": data["Address"],
                    "Phone Number": data["Phone"],
                    "Website": data["Website"]
                })
                
                logging.info(f"Successfully scraped company: {data['Name']}")
            except Exception as e:
                logging.warning(f"Error processing listing {i+1}: {str(e)}")
                continue
        
        if not results:
            logging.error("No results were successfully processed")
            return None
            
        return pd.DataFrame(results)
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
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        }
        response = requests.get(url, timeout=timeout, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        emails = set(extract_emails_from_text(soup.get_text()))
        
        # Check footer specifically
        footer = soup.find('footer')
        if footer:
            emails.update(extract_emails_from_text(footer.get_text()))
        
        # Also check contact pages
        contact_links = []
        for a in soup.find_all('a', href=True):
            if 'contact' in a['href'].lower() or 'about' in a['href'].lower():
                contact_links.append(a['href'])
        
        for link in contact_links:
            if not link.startswith("http"):
                # Handle relative URLs
                base_url = url.split('//')[-1].split('/', 1)[0]
                if link.startswith('/'):
                    link = f"https://{base_url}{link}"
                else:
                    link = f"https://{base_url}/{link}"
            
            try:
                contact_response = requests.get(link, timeout=timeout, headers=headers)
                contact_soup = BeautifulSoup(contact_response.content, 'html.parser')
                emails.update(extract_emails_from_text(contact_soup.get_text()))
            except Exception:
                continue
                
        return list(emails)
    except Exception as e:
        logging.warning(f"Error scraping emails from {url}: {str(e)}")
        return []

def run_scraping(search_queries, progress_placeholder, table_placeholder, success_placeholder, download_placeholder):
    """Run scraping for multiple search queries and update results dynamically."""
    if not search_queries:
        st.error("Please enter at least one valid search query.")
        return
    
    driver = None
    cumulative_results = []
    
    try:
        # Initialize Chrome driver
        progress_placeholder.info("Setting up web browser...")
        driver = setup_chrome_driver()
        
        if driver is None:
            st.error("Failed to initialize Chrome driver. Please check system compatibility.")
            return
        
        # Process each search query
        for query_index, search_query in enumerate(search_queries):
            st.session_state.current_query = search_query
            progress_placeholder.info(f"Processing search query: {search_query}")
            
            # Scrape Google Maps
            df = scrape_google_maps(search_query, driver, max_companies=50)
            
            if df is not None and not df.empty:
                progress_placeholder.success(f"Found {len(df)} companies for '{search_query}'")
                
                # Extract emails from websites
                websites = df["Website"].tolist()
                email_results = []
                progress_bar = progress_placeholder.progress(0)
                
                for i, website in enumerate(websites):
                    if website != "N/A" and isinstance(website, str) and website.strip():
                        # Try both http and https
                        urls_to_try = []
                        if website.startswith('http'):
                            urls_to_try = [website]
                        else:
                            urls_to_try = [f"https://{website}", f"http://{website}"]
                        
                        emails_found = []
                        for url in urls_to_try:
                            try:
                                progress_placeholder.info(f"Checking {url} for emails...")
                                emails = scrape_website_for_emails(url)
                                if emails:
                                    emails_found.extend(emails)
                                    break  # If found emails, no need to try other URL variants
                            except Exception as e:
                                logging.warning(f"Error scraping emails from {url}: {str(e)}")
                        
                        email_results.append(", ".join(set(emails_found)) if emails_found else "N/A")
                    else:
                        email_results.append("N/A")
                    
                    # Update progress
                    progress_bar.progress((i + 1) / len(websites))
                
                # Add emails to dataframe
                df["Email"] = email_results
                cumulative_results.append(df)
                
                # Show current results
                combined_df = pd.concat(cumulative_results, ignore_index=True)
                table_placeholder.dataframe(combined_df)
                success_placeholder.success(f"Query {query_index + 1}/{len(search_queries)} completed. Found {len(df)} results.")
            else:
                st.warning(f"No results found for the query: {search_query}")
        
        # Create download button if there are results
        if cumulative_results:
            combined_df = pd.concat(cumulative_results, ignore_index=True)
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                combined_df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            st.session_state.scraping_completed = True
            success_placeholder.success(f"All queries completed! Found {len(combined_df)} total results. 👇 Click Download Button Below")
            download_placeholder.download_button(
                label="Download Results",
                data=excel_data,
                file_name="Calibrage_Data_Extraction.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=lambda: setattr(st.session_state, 'download_clicked', True)
            )
        else:
            st.warning("No results found for any of the queries. Try different search terms or check your internet connection.")
    except Exception as e:
        st.error(f"An error occurred during scraping: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("Chrome driver closed successfully")
            except:
                pass

def main():
    # Set page configuration
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon="📊",
        layout="wide"
    )

    # Apply custom CSS for styling
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

    # Create a custom header container
    st.markdown("""
    <div class="header">
        <img src="https://github.com/rajendraambati/safron-search-engine/blob/main/calibrage.png?raw=true" class="logo" alt="Calibrage Logo">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)

    # System info
    with st.expander("System Information"):
        st.code(f"""
Python: {sys.version}
System: {platform.system()}
Platform: {platform.platform()}
        """)

    # Search term input with placeholder
    st.markdown("### Enter search terms below (separate multiple terms with commas)")
    st.markdown("Example: `palm oil companies in guntur, software companies in hyderabad`")
    search_input = st.text_input("", placeholder="Enter your search key term...", key="search_input")
    search_queries = [query.strip() for query in search_input.split(",") if query.strip()]

    # Options
    with st.expander("Advanced Options"):
        st.markdown("These settings help fine-tune the scraping process")
        col1, col2 = st.columns(2)
        with col1:
            max_results = st.slider("Maximum results per query", 10, 100, 50)
        with col2:
            wait_time = st.slider("Page load wait time (seconds)", 3, 10, 5)

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

    # Search button
    if st.button("🔎 Search"):
        if search_queries:
            progress_placeholder.info("Starting search process...")
            st.session_state.previous_queries = search_queries
            run_scraping(
                search_queries,
                progress_placeholder,
                table_placeholder,
                success_placeholder,
                download_placeholder
            )
        else:
            st.error("Please enter at least one search term")

    # Clear UI after download
    if st.session_state.download_clicked:
        progress_placeholder.empty()
        table_placeholder.empty()
        success_placeholder.empty()
        download_placeholder.empty()
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align:center">
            <p>© 2025 Calibrage Data Search Engine | For business inquiries only</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

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
    format="%(asctime)s  - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def setup_chrome_driver():
    """
    Set up and return a Chrome WebDriver with additional options for cloud environment.
    """
    try:
        options = webdriver.ChromeOptions()
        
        # Essential options for running in cloud
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Additional options to help with stability
        options.add_argument("--disable-features=NetworkService")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-extensions")
        
        # Try different binary locations
        try:
            # For Debian/Ubuntu
            options.binary_location = "/usr/bin/chromium"
        except:
            try:
                # Alternative location
                options.binary_location = "/usr/bin/chromium-browser"
            except:
                st.warning("Could not set Chromium binary location.")

        # Add user agent to avoid detection
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        try:
            # First attempt: Try with system chromedriver
            service = Service(executable_path="/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
            return driver 
        except Exception as e:
            logging.error(f"First attempt failed: {str(e)}")
            
            try:
                # Second attempt: Try with ChromeDriver Manager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                return driver
            except Exception as e:
                logging.error(f"Second attempt failed: {str(e)}")
                
                try:
                    # Third attempt: Direct instantiation
                    driver = webdriver.Chrome(options=options)
                    return driver
                except Exception as e:
                    logging.error(f"All attempts to initialize Chrome driver failed: {str(e)}")
                    return None
                    
    except Exception as e:
        logging.error(f"Error in setup_chrome_driver: {str(e)}")
        return None

def extract_data(driver, selector_type, selector, wait_time=5):
    """
    Extract data from the page using the provided selector.
    If the element exists, return its text; otherwise, return "N/A".
    
    Args:
        driver: Selenium WebDriver instance
        selector_type: By.XPATH, By.CSS_SELECTOR, etc.
        selector: The selector string
        wait_time: Maximum wait time in seconds
    """
    try:
        # Wait for the element to be present
        element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((selector_type, selector))
        )
        return element.text
    except Exception as e:
        logging.debug(f"Failed to extract data with selector {selector}: {str(e)}")
        return "N/A"

def scrape_google_maps(search_query, driver, max_companies=1000):
    try:
        # Open Google Maps
        driver.get("https://www.google.com/maps")
        
        # Wait for page to load and accept any cookies/consent
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "searchboxinput"))
        )
        
        # Check for and accept consent if present
        try:
            consent_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept all') or contains(., 'I agree')]"))
            )
            consent_button.click()
            time.sleep(2)
        except:
            logging.info("No consent dialog found or already accepted")
        
        # Enter the search query into the search box
        search_box = driver.find_element(By.ID, "searchboxinput")
        search_box.clear()
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        
        # Wait for search results to load
        time.sleep(7)  # Extended wait time for results
        
        # Switch to list view to get more consistent results
        try:
            # Look for the list view button and click it
            list_view_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='List view' or contains(@aria-label, 'list') or contains(@data-value, 'list')]"))
            )
            list_view_button.click()
            time.sleep(5)  # Wait for list view to load
        except Exception as e:
            logging.warning(f"Could not switch to list view: {str(e)}")
            # If we can't switch to list view, try to continue with map view
            
        # Collect all listings
        all_listings = set()  # Use a set to avoid duplicates 
        previous_count = 0
        max_scrolls = 50  # Limit the number of scrolls to prevent infinite loops
        scroll_attempts = 0
        
        # Multiple selectors to try for the results panel
        result_panel_selectors = [
            '//div[contains(@aria-label, "Results for")]',
            '//div[@role="feed"]',
            '//div[contains(@class, "section-layout") and contains(@class, "section-scrollbox")]',
            '//div[@id="pane"]//div[contains(@class, "scrollable")]',
            '//div[contains(@class, "section-result-content")]',
            '//div[@role="region"]'
        ]
        
        # Find the scrollable results panel
        scrollable_div = None
        for selector in result_panel_selectors:
            try:
                scrollable_div = driver.find_element(By.XPATH, selector)
                logging.info(f"Found scrollable results panel with selector: {selector}")
                break
            except:
                continue
        
        if not scrollable_div:
            logging.warning("Could not find scrollable results panel. Using body element instead.")
            scrollable_div = driver.find_element(By.TAG_NAME, "body")
        
        # Scroll and collect listings
        while scroll_attempts < max_scrolls:
            # Log current scroll attempt
            logging.info(f"Scroll attempt {scroll_attempts+1}/{max_scrolls}")
            
            try:
                # Scroll down in the results panel
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight", 
                    scrollable_div
                )
                time.sleep(3)  # Wait for new results to load
                
                # Multiple selectors to find place listings
                listing_selectors = [
                    '//a[contains(@href, "maps/place")]',
                    '//div[@role="article"]',
                    '//div[contains(@class, "section-result")]//a',
                    '//div[@jsaction="pane.listView.visitLink"]',
                    '//a[contains(@data-item-id, "placeret")]'
                ]
                
                # Try different selectors to find listings
                found_listings = []
                for selector in listing_selectors:
                    try:
                        found_listings = driver.find_elements(By.XPATH, selector)
                        if found_listings:
                            logging.info(f"Found {len(found_listings)} listings with selector: {selector}")
                            break
                    except:
                        continue
                
                # No listings found with any selector
                if not found_listings:
                    logging.warning("No listings found with any selector.")
                    scroll_attempts += 1
                    continue
                
                # Process found listings
                current_count = len(found_listings)
                logging.info(f"Found {current_count} listings in this scroll")
                
                # Store listing href or data-item-id or any identifier
                for listing in found_listings:
                    try:
                        href = listing.get_attribute("href")
                        if href and "maps/place" in href:
                            all_listings.add(href)
                        else:
                            # Try to get the place ID or any other identifier
                            data_id = listing.get_attribute("data-item-id") or listing.get_attribute("jsan")
                            if data_id:
                                # Click the listing to open details and get the URL
                                listing.click()
                                time.sleep(2)
                                current_url = driver.current_url
                                if "maps/place" in current_url:
                                    all_listings.add(current_url)
                                # Go back to results list
                                driver.execute_script("window.history.go(-1)")
                                time.sleep(2)
                    except Exception as e:
                        logging.debug(f"Error processing listing: {str(e)}")
                        continue
                
                # Log progress
                logging.info(f"Total unique listings found so far: {len(all_listings)}")
                
                # Check if we've found enough listings or if scrolling isn't yielding new results
                if len(all_listings) >= max_companies or current_count == previous_count:
                    # Try one more scroll just to be sure we've reached the end
                    if current_count == previous_count:
                        scroll_attempts += 1
                        # If we've had multiple identical counts, break
                        if scroll_attempts > 3:
                            logging.info("No new listings after multiple scrolls. Ending search.")
                            break
                    else:
                        logging.info(f"Found maximum number of listings ({max_companies}). Ending search.")
                        break
                else:
                    previous_count = current_count
                    scroll_attempts += 1
                    
            except Exception as e:
                logging.warning(f"Error during scrolling: {str(e)}")
                scroll_attempts += 1
        
        logging.info(f"Found {len(all_listings)} unique listings to process")
        
        # If no listings were found, return None
        if not all_listings:
            logging.warning("No listings found for the given search query.")
            return None
        
        # Extract details for each unique listing
        results = []
        for i, href in enumerate(list(all_listings)[:max_companies]):
            try:
                # Navigate to the listing page
                driver.get(href)
                time.sleep(3)  # Wait for the page to load
                
                # Different selectors for business information
                name_selectors = [
                    '//h1[contains(@class, "DUwDvf")]',
                    '//h1[contains(@class, "fontHeadlineLarge")]',
                    '//div[contains(@class, "fontHeadlineLarge")]',
                    '//div[contains(@class, "x3AX1-LfntMc-header-title-title")]'
                ]
                
                address_selectors = [
                    '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]',
                    '//button[contains(@data-item-id, "address")]//div[contains(@class, "fontBodyMedium")]',
                    '//div[contains(text(), "Address")]/following-sibling::div',
                    '//div[contains(@class, "rogA2c")]/div[contains(@class, "fontBodyMedium")]'
                ]
                
                phone_selectors = [
                    '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]',
                    '//button[contains(@aria-label, "Phone")]//div[contains(@class, "fontBodyMedium")]',
                    '//div[contains(text(), "Phone")]/following-sibling::div',
                    '//button[contains(@data-item-id, "phone")]//div[contains(@class, "fontBodyMedium")]'
                ]
                
                website_selectors = [
                    '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]',
                    '//a[contains(@data-item-id, "authority")]//div[contains(@class, "fontBodyMedium")]',
                    '//div[contains(text(), "Website")]/following-sibling::div/a',
                    '//a[contains(@aria-label, "Website")]'
                ]
                
                # Extract business details using multiple selector attempts
                name = "N/A"
                for selector in name_selectors:
                    name = extract_data(driver, By.XPATH, selector)
                    if name != "N/A":
                        break
                        
                address = "N/A"
                for selector in address_selectors:
                    address = extract_data(driver, By.XPATH, selector)
                    if address != "N/A":
                        break
                
                phone = "N/A"
                for selector in phone_selectors:
                    phone = extract_data(driver, By.XPATH, selector)
                    if phone != "N/A":
                        break
                        
                website = "N/A"
                for selector in website_selectors:
                    website = extract_data(driver, By.XPATH, selector)
                    if website != "N/A":
                        break
                
                # Try to extract website URL from href attribute if text extraction failed
                if website == "N/A":
                    try:
                        website_element = None
                        for selector in website_selectors:
                            try:
                                website_element = driver.find_element(By.XPATH, selector)
                                break
                            except:
                                continue
                                
                        if website_element:
                            parent_a = driver.find_element(By.XPATH, "//a[contains(@data-item-id, 'authority') or contains(@aria-label, 'Website')]")
                            website = parent_a.get_attribute("href")
                    except:
                        pass
                
                # Process website URL if found
                if website != "N/A" and website.startswith("https://www.google.com/url"):
                    # Extract the actual URL from Google's redirect URL
                    match = re.search(r"q=([^&]+)", website)
                    if match:
                        website = match.group(1)
                
                # Append to results
                results.append({
                    "Name": name,
                    "Address": address,
                    "Phone Number": phone,
                    "Website": website
                })
                
                # Log progress
                logging.info(f"Scraped company {i+1}/{len(all_listings)}: {name}")
                
            except Exception as e:
                logging.warning(f"Error processing listing {i+1}: {str(e)}")
                continue
        
        # Return results as DataFrame
        if results:
            return pd.DataFrame(results)
        else:
            logging.warning("No listings could be processed successfully.")
            return None
    
    except Exception as e:
        logging.error(f"Error in scrape_google_maps: {str(e)}")
        return None

def extract_emails_from_text(text):
    """
    Extract email addresses from text using regex.
    """
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def scrape_website_for_emails(url):
    """
    Scrape a website for email addresses.
    """
    try:
        # Add proper URL scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Set request headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract emails from the homepage
        emails = set(extract_emails_from_text(soup.get_text()))
        
        # Check common pages for emails
        common_pages = ['contact', 'about', 'team', 'about-us', 'contact-us']
        for page in common_pages:
            try:
                page_url = f"{url.rstrip('/')}/{page}"
                page_response = requests.get(page_url, headers=headers, timeout=10)
                page_soup = BeautifulSoup(page_response.content, 'html.parser')
                emails.update(extract_emails_from_text(page_soup.get_text()))
            except:
                continue
        
        return list(emails)
    except Exception as e:
        logging.debug(f"Error scraping emails from {url}: {str(e)}")
        return []

def run_scraping(search_query, placeholder, download_button_placeholder, success_message_placeholder, result_table_placeholder):
    """
    Run the scraping process for the given search query.
    """
    if not search_query.strip():
        st.error("Please enter a valid search query.")
        return
    
    # Show processing message
    placeholder.info("Processing your request... This may take a few minutes.")
    
    # Initialize Chrome driver with automatic installation
    driver = None
    try:
        driver = setup_chrome_driver()
        
        if driver is None:
            st.error("""
             Failed to initialize Chrome driver. This could be due to:
            1. Chrome browser not installed
            2. Running in a restricted environment
            3. System compatibility issues
            
            Please check the system information in the sidebar for details.
            """)
            return
        
        # Log the start of scraping
        logging.info(f"Starting to scrape Google Maps for: {search_query}")
        
        # Scrape Google Maps
        df = scrape_google_maps(search_query, driver, max_companies=1000)
        
        if df is not None and not df.empty:
            # Log success
            logging.info(f"Successfully scraped {len(df)} results for: {search_query}")
            
            # Process websites and emails
            websites = df["Website"].tolist()
            email_results = []
            
            progress_bar = st.progress(0)
            for i, website in enumerate(websites):
                if website != "N/A" and isinstance(website, str) and website.strip():
                    # Process the website to remove unwanted parts
                    clean_website = website.replace('http://', '').replace('https://', '').split('/')[0]
                    emails_found = scrape_website_for_emails(clean_website)
                    email_results.append(", ".join(set(emails_found)) if emails_found else "N/A")
                else:
                    email_results.append("N/A")
                
                # Update the progress bar
                progress_bar.progress((i + 1) / len(websites))
            
            df["Email"] = email_results
            
            # Prepare Excel data for download
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            # Save to session state for potential reuse
            st.session_state.df = df
            st.session_state.excel_data = excel_data
            
            # Clear the processing message
            placeholder.empty()
            
            # Mark scraping as completed
            st.session_state.scraping_completed = True
            
            # Display the table
            result_table_placeholder.table(df)
            
            # Show success message
            success_message_placeholder.success("Done! 👇Click Download Button Below")
             
            # Add download button
            download_button_placeholder.download_button(
                label="Download Results",
                data=excel_data,
                file_name="Calibrage Data Extraction.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=lambda: setattr(st.session_state, 'download_clicked', True)
            )
        else:
            placeholder.empty()
            st.warning("No results found for the given search query. Please try a different search term or check the logs for details.")
            
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

    st.markdown("""
    """, unsafe_allow_html=True)
    
    st.title("🔍 Calibrage Info Systems Data Search Engine")
    
    # Add version info
    st.sidebar.markdown("### System Information")
    st.sidebar.text(f"Python: {platform.python_version()}")
    st.sidebar.text(f"System: {platform.system()}")
    st.sidebar.text(f"Platform: {platform.platform()}")
    
    # Session state for tracking various states
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'previous_query' not in st.session_state:
        st.session_state.previous_query = ""
    
    # Create placeholders for dynamic updates
    result_table_placeholder = st.empty()
    success_message_placeholder = st.empty()
    download_button_placeholder = st.empty()
    processing_placeholder = st.empty()
    
    # Display the search box AFTER the table
    if st.session_state.scraping_completed:
        result_table_placeholder.table(getattr(st.session_state, 'df', pd.DataFrame()))
        success_message_placeholder.success("Done! 👇Click Download Button Below")
        download_button_placeholder.download_button(
            label="Download Results",
            data=getattr(st.session_state, 'excel_data', None),
            file_name="Calibrage Data Extraction.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click=lambda: setattr(st.session_state, 'download_clicked', True)
        )
    
    # Add more explanation text
    st.markdown("""
    ### How to use:
    1. Enter a search term like "palm oil companies", "tech startups in bangalore", etc.
    2. Wait for the results to be scraped (this may take a few minutes)
    3. Download the Excel file with the results
    """)
    
    search_query = st.text_input("Enter the search Term Below 👇 (e.g: palm oil, software companies in india)", "")
    
    # Search button to trigger scraping
    if st.button("Search"):
        if search_query.strip() and search_query != st.session_state.previous_query:
            st.session_state.previous_query = search_query
            run_scraping(
                search_query, 
                processing_placeholder, 
                download_button_placeholder, 
                success_message_placeholder, 
                result_table_placeholder
            )
    
    # Clear all placeholders and reset UI after download
    if getattr(st.session_state, 'download_clicked', False):
        # Clear all placeholders
        result_table_placeholder.empty()
        success_message_placeholder.empty()
        download_button_placeholder.empty()
        processing_placeholder.empty()
        
        # Reset session state variables
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False

if __name__ == "__main__":
    main()

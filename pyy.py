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

def extract_data(xpath, driver):
    """
    Extract data from the page using the provided XPath.
    If the element exists, return its text; otherwise, return "N/A".
    """
    try:
        element = driver.find_element(By.XPATH, xpath)
        return element.text
    except:
        return "N/A"

def scrape_google_maps(search_query, driver, max_companies=1000):
    try:
        # Open Google Maps
        driver.get("https://www.google.com/maps")
        time.sleep(5)  # Wait for the page to load
        
        # Enter the search query into the search box
        search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)  # Wait for results to load
        
        # Zoom out globally to ensure all results are loaded
        actions = ActionChains(driver)
        for _ in range(10):  # Zoom out multiple times
            actions.key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(1)  # Wait for the map to adjust
        
        # Scroll and collect all listings
        all_listings = set()  # Use a set to avoid duplicates
        previous_count = 0
        max_scrolls = 50  # Limit the number of scrolls to prevent infinite loops
        scroll_attempts = 0
        
        while scroll_attempts < max_scrolls:
            try:
                # Scroll down to load more results
                scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for")]')
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(3)  # Wait for new results to load
                
                # Collect all visible listings
                current_listings = driver.find_elements(By.XPATH, '//a[contains(@href, "https://www.google.com/maps/place")]')
                current_count = len(current_listings)
                
                # Add new listings to the set
                for listing in current_listings:
                    href = listing.get_attribute("href")
                    if href:
                        all_listings.add(href)
                
                # Check if no new results were loaded
                if current_count == previous_count or len(all_listings) >= max_companies:
                    break
                
                # Update the previous count
                previous_count = current_count
                scroll_attempts += 1
            except Exception as e:
                logging.warning(f"Error during scrolling: {str(e)}")
                break
        
        # Extract details for each unique listing (up to max_companies)
        results = []
        for i, href in enumerate(all_listings):
            if i >= max_companies:
                break  # Stop processing if we've reached the maximum number of companies
            
            try:
                driver.get(href)
                time.sleep(3)  # Wait for the sidebar to load
                
                # Extract details
                name = extract_data('//h1[contains(@class, "DUwDvf lfPIob")]', driver)
                address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', driver)
                phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', driver)
                website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', driver)
                
                # Append to results
                results.append({
                    "Name": name,
                    "Address": address,
                    "Phone Number": phone,
                    "Website": website
                })
                
                # Log progress
                logging.info(f"Scraped company: {name}")
            except Exception as e:
                logging.warning(f"Error processing listing {i+1}: {str(e)}")
                continue
        
        return pd.DataFrame(results) if results else None
    
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
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract emails from the homepage
        emails = set(extract_emails_from_text(soup.get_text()))
        
        # Check the footer for emails
        footer = soup.find('footer')
        if footer:
            emails.update(extract_emails_from_text(footer.get_text()))
        
        # Find links to the contact page
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

def run_scraping(search_query, placeholder, download_button_placeholder, success_message_placeholder, result_table_placeholder):
    """
    Run the scraping process for the given search query.
    """
    if not search_query.strip():
        st.error("Please enter a valid search query.")
        return
    
    #placeholder.markdown("**Processing..... Please Wait**")
    
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
        
        df = scrape_google_maps(search_query, driver, max_companies=1000)
        
        if df is not None and not df.empty:
            # Process websites and emails
            websites = df["Website"].tolist()
            email_results = []
            
            progress_bar = st.progress(0)
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
                
                # Update the progress bar
                progress_bar.progress((i + 1) / len(websites))
            
            df["Email"] = email_results
            
            # Prepare Excel data for download
            excel_data = io.BytesIO()
            with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            excel_data.seek(0)
            
            # Clear the processing message
            placeholder.empty()
            
            # Mark scraping as completed
            st.session_state.scraping_completed = True
            
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
            
            # Display the table
            result_table_placeholder.table(df)
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
    download_button_placeholder = st.empty()
    success_message_placeholder = st.empty()
    result_table_placeholder = st.empty()
    processing_placeholder = st.empty()
    
    # Handle Enter key press through form submission
    with st.form(key='search_form'):
        search_query = st.text_input("Enter the search Term Below 👇 (e.g: palm oil, software companies in india)", "")
        # Fixed submit button - removed label_visibility parameter
        #submit_button = st.form_submit_button("Search")
        # Make the button less conspicuous using CSS
        st.markdown("""
        <style>
        div.stButton button {
            font-size: 0px;
            height: 0px;
            padding: 0px;
            visibility: hidden;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Clear results when a new search query is entered
    if search_query != st.session_state.previous_query:
        if st.session_state.scraping_completed:
            st.session_state.scraping_completed = False
            download_button_placeholder.empty()
            success_message_placeholder.empty()
            result_table_placeholder.empty()
            processing_placeholder.empty()
    
    # Run scraping when form is submitted (Enter key is pressed)
    if submit_button and not st.session_state.scraping_completed:
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
        download_button_placeholder.empty()
        success_message_placeholder.empty()
        result_table_placeholder.empty()
        processing_placeholder.empty()
        
        # Reset session state variables
        st.session_state.scraping_completed = False
        st.session_state.download_clicked = False

if __name__ == "__main__":
    main()

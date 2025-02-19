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
import spacy

# Load the English language model
@st.cache_resource
def load_spacy_model():
    return spacy.load("en_core_web_sm")

def parse_query_with_nlp(query, nlp):
    """
    Process the query using spaCy and return a list of sub-queries
    """
    # First, try to split by common delimiters
    # Split by both commas and 'and', preserving all terms
    parts = re.split(r'\s*,\s*|\s+and\s+', query.lower())
    
    # Clean up the parts and remove any mentions of 'companies' or location
    keywords = []
    location = None
    
    # Process with spaCy to find location
    doc = nlp(query)
    
    # Extract the location entity
    for ent in doc.ents:
        if ent.label_ == "GPE":
            location = ent.text
            break
    
    # If no location found, look for common country/region names
    if not location:
        common_locations = ["India"]
        query_words = query.upper().split()
        for loc in common_locations:
            if loc in query_words:
                location = loc
                break
    
    # Set default location if none found
    if not location:
        location = "India"
    
    # Clean up each part
    for part in parts:
        # Remove the location if it's in the part
        part = part.replace(location.lower(), "").strip()
        # Remove 'companies in' if present
        part = part.replace("companies in", "").strip()
        # Remove 'companies' if present
        part = part.replace("companies", "").strip()
        
        if part:
            keywords.append(part)
    
    # Remove duplicates while preserving order
    keywords = list(dict.fromkeys(keywords))
    
    # Generate the final queries
    final_queries = [f"{keyword.strip()} companies in {location}" for keyword in keywords if keyword.strip()]
    
    return final_queries

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
        
        # Try to create driver with ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
        
    except Exception as e:
        st.error(f"Error in setup_chrome_driver: {str(e)}")
        return None

def extract_data(xpath, driver):
    """
    Extract data from the page using the provided XPath.
    """
    try:
        element = driver.find_element(By.XPATH, xpath)
        return element.text
    except:
        return "N/A"

def scrape_google_maps(search_query, driver):
    """
    Scrape Google Maps for the given search query
    """
    try:
        # Open Google Maps
        driver.get("https://www.google.com/maps")
        time.sleep(5)  # Wait for the page to load
        
        # Enter the search query into the search box
        search_box = driver.find_element(By.XPATH, '//input[@id="searchboxinput"]')
        search_box.clear()  # Clear any existing text
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)  # Wait for results to load
        
        # Zoom out globally to ensure all results are loaded
        actions = ActionChains(driver)
        for _ in range(5):  # Reduced number of zoom outs
            actions.key_down(Keys.CONTROL).send_keys("-").key_up(Keys.CONTROL).perform()
            time.sleep(1)
        
        # Scroll and collect all listings
        all_listings = set()
        previous_count = 0
        scroll_attempts = 0
        
        while scroll_attempts < 10:  # Reduced max scrolls
            try:
                # Scroll down
                scrollable_div = driver.find_element(By.XPATH, '//div[contains(@aria-label, "Results for")]')
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(3)
                
                # Collect listings
                current_listings = driver.find_elements(By.XPATH, '//a[contains(@href, "https://www.google.com/maps/place")]')
                
                # Add new listings to the set
                for listing in current_listings:
                    href = listing.get_attribute("href")
                    if href:
                        all_listings.add(href)
                
                if len(all_listings) == previous_count:
                    break
                
                previous_count = len(all_listings)
                scroll_attempts += 1
                
            except Exception as e:
                st.warning(f"Error during scrolling: {str(e)}")
                break
        
        # Extract details for each listing
        results = []
        for href in list(all_listings)[:20]:  # Limit to first 20 results
            try:
                driver.get(href)
                time.sleep(3)
                
                name = extract_data('//h1[contains(@class, "DUwDvf")]', driver)
                address = extract_data('//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]', driver)
                phone = extract_data('//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]', driver)
                website = extract_data('//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]', driver)
                
                if name != "N/A":  # Only add if we found a valid name
                    results.append({
                        "Name": name,
                        "Address": address,
                        "Phone Number": phone,
                        "Website": website
                    })
            except Exception as e:
                continue
        
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    except Exception as e:
        st.error(f"Error in scrape_google_maps: {str(e)}")
        return pd.DataFrame()

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
        response = requests.get(url, timeout=5)  # Reduced timeout
        soup = BeautifulSoup(response.content, 'html.parser')
        emails = set(extract_emails_from_text(soup.get_text()))
        return list(emails)
    except:
        return []

def main():
    st.set_page_config(
        page_title="Calibrage Info Systems",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Calibrage Info Systems Data Search Engine")
    
    # Add version info
    st.sidebar.markdown("### System Information")
    st.sidebar.text(f"Python: {platform.python_version()}")
    st.sidebar.text(f"System: {platform.system()}")
    st.sidebar.text(f"Platform: {platform.platform()}")
    
    # Load spaCy model
    try:
        nlp = load_spacy_model()
    except Exception as e:
        st.error(f"Failed to load spaCy model: {str(e)}")
        return
    
    master_query = st.text_input("Enter your search query (e.g., 'food, beverages and sanitization companies in USA')", "")
    placeholder = st.empty()
    
    if st.button("Scrap It!"):
        if not master_query.strip():
            st.error("Please enter a valid search query.")
            return
        
        # Parse the master query into sub-queries
        sub_queries = parse_query_with_nlp(master_query, nlp)
        
        if not sub_queries:
            st.error("Could not parse any valid sub-queries from your input.")
            return
        
        st.write("Generated sub-queries:")
        for query in sub_queries:
            st.write(f"- {query}")
        
        placeholder.markdown("**Processing... Please Wait**")
        
        # Initialize Chrome driver
        driver = setup_chrome_driver()
        
        if driver is None:
            st.error("Failed to initialize Chrome driver. Please ensure Chrome is installed and try again.")
            return
        
        try:
            # Store results for all sub-queries
            all_results = []
            
            # Create a progress bar for overall progress
            progress_bar = st.progress(0)
            
            # Process each sub-query
            for idx, query in enumerate(sub_queries):
                st.write(f"Processing query: {query}")
                
                df = scrape_google_maps(query, driver)
                
                if not df.empty:
                    # Add query information
                    df['Search Query'] = query
                    
                    # Process websites and emails
                    websites = df["Website"].tolist()
                    email_results = []
                    
                    sub_progress = st.progress(0)
                    for i, website in enumerate(websites):
                        if website != "N/A" and isinstance(website, str) and website.strip():
                            urls_to_try = [f"http://{website}", f"https://{website}"]
                            emails_found = []
                            for url in urls_to_try:
                                try:
                                    emails = scrape_website_for_emails(url)
                                    emails_found.extend(emails)
                                except Exception as e:
                                    continue
                            email_results.append(", ".join(set(emails_found)) if emails_found else "N/A")
                        else:
                            email_results.append("N/A")
                        sub_progress.progress((i + 1) / len(websites))
                    
                    df["Email"] = email_results
                    all_results.append(df)
                
                # Update overall progress
                progress_bar.progress((idx + 1) / len(sub_queries))
            
            # Combine all results
            if all_results:
                final_df = pd.concat(all_results, ignore_index=True)
                
                # Save to Excel
                try:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        final_df.to_excel(writer, index=False)
                    output.seek(0)
                    
                    placeholder.empty()
                    st.success("Done! 👇Click Download Button Below")
                    st.download_button(
                        label="Download Results",
                        data=output,
                        file_name="final_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Error saving results: {str(e)}")
            else:
                st.warning("No results found for any of the sub-queries.")
                
        except Exception as e:
            st.error(f"An error occurred during scraping: {str(e)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

if __name__ == "__main__":
    main()

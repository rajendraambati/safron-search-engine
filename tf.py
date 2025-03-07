def main():
    # Custom logo path
    logo_path = "calibrage.jpg"

    # Set page configuration
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon=logo_path,
        layout="wide"
    )
    
    # Create a custom header container
    st.markdown("""
    <style>
        .header-container {
            background-color: #f0f2f6;
            padding: 2rem;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 2rem;
        }
        .header-logo {
            max-width: 200px;
            margin-bottom: 1rem;
        }
    </style>
    <div class="header-container">
        <img src="https://github.com/rajendraambati/safron-search-engine/blob/main/calibrage.jpg?raw=true" class="header-logo">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)

    # Search term input with placeholder
    search_input = st.text_input(
        "Enter your search key terms (comma-separated)",
        placeholder="e.g., palm oil, software companies in india",
        key="search_input"
    )
    
    # Search button positioned below the search bar
    search_button = st.button("Start Search", key="search_button")

    # Session state initialization
    if 'scraping_completed' not in st.session_state:
        st.session_state.scraping_completed = False
    if 'previous_queries' not in st.session_state:
        st.session_state.previous_queries = []
    if 'download_clicked' not in st.session_state:
        st.session_state.download_clicked = False

    # Placeholders for dynamic content
    progress_placeholder = st.empty()
    success_placeholder = st.empty()
    download_placeholder = st.empty()
    table_placeholder = st.empty()

    # Trigger scraping when the search button is clicked
    if search_button:
        search_queries = [query.strip() for query in search_input.split(",") if query.strip()]
        
        if not search_queries:
            st.error("Please enter at least one valid search query.")
        else:
            run_scraping(
                search_queries,
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

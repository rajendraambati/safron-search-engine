def main():
    st.set_page_config(
        page_title="Calibrage Data Search Engine",
        page_icon="calibrage.jpg",
        layout="wide"
    )
    
    # Custom CSS with all requested changes
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

    # Header section
    st.markdown("""
    <div class="header" style="text-align: center;">
        <img src="https://github.com/rajendraambati/safron-search-engine/raw/main/calibrage.jpg" 
             style="width:150px; margin:20px;">
        <h1>Calibrage Data Search Engine</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state for search input
    if 'search_input' not in st.session_state:
        st.session_state.search_input = ''

    # Search container
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    
    # Search input
    search_input = st.text_input(
        "Search Terms", 
        placeholder="Enter comma-separated search terms...",
        label_visibility="hidden",
        key="search_input",
        help="Enter multiple terms separated by commas"
    )
    
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
        # Reset using dictionary syntax to avoid widget state issues
        st.session_state['search_input'] = ""
        progress_bar.empty()
        results_table.empty()
        success_msg.empty()
        download_btn.empty()
        st.rerun()
    
    # Search button handler
    if search_btn:
        terms = [t.strip() for t in search_input.split(",") if t.strip()]
        if terms:
            with st.spinner("Initializing browser..."):
                run_scraping(terms, progress_bar, results_table, success_msg, download_btn)
        else:
            st.error("Please enter valid search terms")

if __name__ == "__main__":
    main()

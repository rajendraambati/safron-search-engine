import streamlit as st

# ... (rest of the imports remain unchanged)

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
    search_query = st.text_input("Search Query", key="search_input", placeholder="Press Enter to Run")

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
    if 'run_count' not in st.session_state:
        st.session_state.run_count = 0  # Track the number of runs
    
    # 4-7. Placeholders for dynamic content
    progress_placeholder = st.empty()  # 4. Progress bar
    table_placeholder = st.empty()     # 5. Table
    success_placeholder = st.empty()   # 6. Success message
    download_placeholder = st.empty()  # 7. Download button
    
    # Trigger scraping on Enter key press
    if search_query.strip():
        # Increment run count to force rerun even if query is unchanged
        if st.session_state.run_count == 0 or st.session_state.previous_query != search_query:
            st.session_state.run_count += 1
            st.session_state.previous_query = search_query
            run_scraping(
                search_query,
                progress_placeholder,
                table_placeholder,
                success_placeholder,
                download_placeholder
            )
        else:
            # Force rerun for the same query
            st.session_state.run_count += 1
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

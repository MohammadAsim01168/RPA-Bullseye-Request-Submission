import streamlit as st
from shared_functions import search_items, update_multiple_brands, update_selection
import re

def validate_url(url):
    """Validate URL and return specific error message if invalid"""
    if not url:
        return False, "Please enter a URL."
    
    # Check if URL starts with http:// or https://
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    
    # Check for valid domain pattern
    domain_pattern = r'^https?://([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'
    if not re.match(domain_pattern, url):
        return False, "Invalid domain format in URL"
    
    # Check for valid path
    path_pattern = r'^https?://([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(/[a-zA-Z0-9-._~:/?#[\]@!$&\'()*+,;=]*)?$'
    if not re.match(path_pattern, url):
        return False, "Invalid URL path format"
    
    return True, ""

def show_x_amazon_section():
    st.title("X-Amazon Submission")

    # Add a loading spinner while initializing
    with st.spinner('Initializing X-Amazon application...'):
        # Selection type radio buttons for X-Amazon options
        x_amazon_type = st.radio(
            "Select X-Amazon Type:",
            ["Walmart", "Target", "Home Depot", "Lowes"],
            key="x_amazon_type"
        )

        # Initialize session state for X-Amazon search results
        if 'x_amazon_search_results' not in st.session_state:
            st.session_state.x_amazon_search_results = None

        # Handle different X-Amazon types
        if x_amazon_type in ["Walmart", "Target"]:
            # Search box for brand selection
            search_term = st.text_input(
                f"Search Brand for {x_amazon_type}:",
                help="Type to search for available options"
            )
            
            if search_term:
                search_results = search_items(search_term, "Brand Name")
                st.session_state.x_amazon_search_results = search_results
                
                if search_results:
                    # For brand search, results are already just brand names
                    selected_values = st.multiselect(
                        "Select Brand(s):",
                        options=search_results,
                        key="x_amazon_brand_select"
                    )
                    
                    if st.button("Submit Selected Brands for X-Amazon"):
                        with st.spinner('Submitting X-Amazon brands...'):
                            if selected_values:
                                if len(selected_values) > 1:
                                    update_multiple_brands(selected_values, x_amazon_type)
                                else:
                                    update_selection("Brand", selected_values[0], x_amazon_type)
                            else:
                                st.warning("Please select at least one brand.")
                else:
                    st.info("No brands found.")
        
        elif x_amazon_type in ["Home Depot", "Lowes"]:
            # URL input for Home Depot and Lowes
            url = st.text_input(
                f"Enter {x_amazon_type} Brand URL:",
                help="Enter the URL for the brand page (must start with http:// or https://)"
            )
            
            if st.button(f"Submit {x_amazon_type} Brand"):
                is_valid, error_message = validate_url(url)
                if not is_valid:
                    st.error(error_message)
                else:
                    with st.spinner(f'Submitting {x_amazon_type} brand...'):
                        update_selection("Brand", url, x_amazon_type)

    # Display X-Amazon current selection
    if x_amazon_type in ["Walmart", "Target"] and 'selected_values' in locals() and selected_values:
        # Convert to list if it's a tuple and ensure all items are strings
        display_values = [str(val) for val in selected_values]
        st.info(f"Current X-Amazon Selection: {', '.join(display_values)}") 
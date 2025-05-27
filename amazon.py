import streamlit as st
from shared_functions import search_items, update_multiple_brands, update_selection
from send_email import send_email_notification
import re
import uuid
import time

def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    return True, ""

def initialize_session_state():
    """Initialize all session state variables if they don't exist"""
    if 'amazon_search_results' not in st.session_state:
        st.session_state.amazon_search_results = None
    if 'amazon_selected_brands' not in st.session_state:
        st.session_state.amazon_selected_brands = []
    if 'amazon_manual_brands' not in st.session_state:
        st.session_state.amazon_manual_brands = ""
    if 'submission_type' not in st.session_state:
        st.session_state.submission_type = None

def show_amazon_section():
    st.title("Amazon Submission")

    # Initialize session state variables
    initialize_session_state()

    # Selection type radio buttons
    selection_type = st.radio(
        "Select Submission Type:",
        ["Brand Name", "Company Name"],
        key="amazon_submission_type"
    )

    if selection_type == "Brand Name":
        # Create two columns for the interface
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Search Brands from HubSpot")
            # Search box for brand selection
            search_term = st.text_input(
                "Search Brand:",
                help="Type to search for available brands",
                key="amazon_brand_search"
            )
            
            if search_term:
                try:
                    search_results = search_items(search_term, "Brand Name")
                    st.session_state.amazon_search_results = search_results
                    
                    if search_results:
                        # Combine new search results with previously selected brands
                        all_brand_options = list(set(search_results + st.session_state.amazon_selected_brands))
                        selected_values = st.multiselect(
                            "Select Brand(s):",
                            options=all_brand_options,
                            default=st.session_state.amazon_selected_brands,
                            key="amazon_brand_select"
                        )
                        # Update session state with current selections
                        st.session_state.amazon_selected_brands = selected_values
                    else:
                        st.info("No brands found in search results.")
                except Exception as e:
                    st.error(f"Error searching brands: {str(e)}")
                    st.info("You can still add new brands manually.")
            else:
                # If no search term, show currently selected brands
                if st.session_state.amazon_selected_brands:
                    selected_values = st.multiselect(
                        "Select Brand(s):",
                        options=st.session_state.amazon_selected_brands,
                        default=st.session_state.amazon_selected_brands,
                        key="amazon_brand_select"
                    )
                    st.session_state.amazon_selected_brands = selected_values

        with col2:
            st.subheader("Add Brands not in HubSpot")
            st.info("For multiple brands, enter them separated by semicolons (e.g., brand1;brand2;brand3)")
            manual_brands = st.text_area(
                "Enter New Brand(s):",
                value=st.session_state.amazon_manual_brands,
                help="Enter brand name(s) separated by semicolons for multiple brands",
                key="amazon_manual_brands"
            )

        # Submit button for combined submission
        if st.button("Submit All Brands"):
            with st.spinner('Submitting brands...'):
                try:
                    # Collect all brands
                    all_brands = []
                    has_manual_brands = False
                    
                    # Add selected brands from dropdown
                    if st.session_state.amazon_selected_brands:
                        all_brands.extend(st.session_state.amazon_selected_brands)
                    
                    # Add manually entered brands
                    if manual_brands:  # Use the widget value directly
                        manual_brands_list = [brand.strip() for brand in manual_brands.split(";")]
                        all_brands.extend(manual_brands_list)
                        has_manual_brands = True
                    
                    if not all_brands:
                        st.error("Please select or enter at least one brand")
                    else:
                        # Generate a single GUID for all brands in this submission
                        req_guid = str(uuid.uuid4())
                        
                        # Separate brands into dropdown and manual entries
                        dropdown_brands = st.session_state.amazon_selected_brands
                        manual_brands = []
                        
                        # Get manual brands from the text area widget directly
                        manual_brands_text = st.session_state.get('amazon_manual_brands', '')
                        if manual_brands_text and manual_brands_text.strip():  # Check if there's any non-empty text
                            manual_brands = [brand.strip() for brand in manual_brands_text.split(";")]
                        
                        # Calculate total brands and set is_multiple
                        total_brands = len(dropdown_brands) + len(manual_brands)
                        is_multiple = "TRUE" if total_brands > 1 else "FALSE"  # Changed to uppercase TRUE/FALSE
                        
                        # Debug log
                        # st.write(f"Debug - Total brands: {total_brands}, is_multiple: {is_multiple}")
                        # st.write(f"Debug - Dropdown brands: {dropdown_brands}")
                        # st.write(f"Debug - Manual brands: {manual_brands}")
                        
                        # Handle dropdown brands first (Amazon Brand Name)
                        if dropdown_brands:
                            with st.spinner('Submitting existing brands...'):
                                # For each dropdown brand
                                for brand in dropdown_brands:
                                    update_multiple_brands(
                                        brands_list=[brand],  # Submit one at a time
                                        x_amazon_type=None,
                                        req_guid=req_guid,  # Use the same GUID
                                        request_type="Amazon Brand Name",
                                        is_multiple=is_multiple  # Use the same is_multiple for all submissions
                                    )
                                st.success(f"Successfully submitted brands from HubSpot: {', '.join(dropdown_brands)}")
                        
                        # Handle manual brands (Amazon Brand Name New)
                        if manual_brands:
                            with st.spinner('Submitting new brands...'):
                                # Set submission type for manual brands
                                st.session_state.submission_type = "Brand Not in HubSpot"
                                # For each manual brand
                                for brand in manual_brands:
                                    update_multiple_brands(
                                        brands_list=[brand],  # Submit one at a time
                                        x_amazon_type=None,
                                        req_guid=req_guid,  # Use the same GUID
                                        request_type="Amazon Brand Name New",
                                        is_multiple=is_multiple  # Use the same is_multiple for all submissions
                                    )
                                st.success(f"Successfully submitted new brands: {', '.join(manual_brands)}")
                        
                        # Store success message in session state
                        st.session_state.success_message = f"Successfully submitted {len(all_brands)} brand(s) with request GUID: {req_guid}"
                        
                        # Send email notification after successful submission
                        query_value = ", ".join(all_brands)  # Combine all brands into a single string
                        if send_email_notification(query_value, st.session_state.requestor_email):
                            st.success("Email notification sent successfully")
                        
                        # Clear the form after successful submission
                        st.session_state.amazon_search_results = None
                        st.session_state.amazon_selected_brands = []
                        st.session_state.submission_type = None
                        
                        # Display final success message
                        st.success(f"Successfully submitted {len(all_brands)} brand(s)")
                        
                        # Use rerun with a delay to keep the message visible
                        time.sleep(2)  # Wait for 2 seconds
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error submitting brands: {str(e)}")

        # Display current selections
        if st.session_state.amazon_selected_brands:
            st.info(f"Selected Brands from HubSpot: {', '.join(st.session_state.amazon_selected_brands)}")
        
        # Get manual brands from the text area widget
        manual_brands_text = st.session_state.amazon_manual_brands
        if manual_brands_text and manual_brands_text.strip():  # Check if there's any non-empty text
            st.info(f"New Brands to Add: {manual_brands_text}")

    elif selection_type == "Company Name":
        # Search box for company selection
        search_term = st.text_input(
            "Search Company:",
            help="Type to search for available companies",
            key="amazon_company_search"
        )
        
        if search_term:
            try:
                search_results = search_items(search_term, "Company Name")
                st.session_state.amazon_search_results = search_results
                
                if search_results:
                    # For company search, show company names in dropdown
                    company_names = [row[1] for row in search_results]
                    selected_company = st.selectbox(
                        "Select Company:",
                        options=company_names,
                        key="amazon_company_select"
                    )
                    
                    if st.button("Submit Selected Company"):
                        with st.spinner('Submitting company...'):
                            if selected_company:
                                update_selection("Company", selected_company)
                                st.success("Successfully submitted company to Amazon")
                                
                                # Send email notification for company submission
                                if send_email_notification(selected_company, st.session_state.requestor_email):
                                    st.success("Email notification sent successfully")
                            else:
                                st.warning("Please select a company.")
                else:
                    st.info("No companies found.")
            except Exception as e:
                st.error(f"Error searching companies: {str(e)}")

if __name__ == "__main__":
    show_amazon_section() 

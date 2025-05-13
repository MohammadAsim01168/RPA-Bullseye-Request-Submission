import streamlit as st
from shared_functions import (
    search_items, 
    update_multiple_brands, 
    update_selection,
    get_snowflake_connection,
    insert_into_keepa_table,
    update_bullseye_status
)
from config import RUN_TYPE
import re
import uuid

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

def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    return True, ""

def show_x_amazon_section():
    st.title("X-Amazon Submission")

    # Add a loading spinner while initializing
    with st.spinner('Initializing X-Amazon application...'):
        # Initialize session state for X-Amazon search results
        if 'x_amazon_search_results' not in st.session_state:
            st.session_state.x_amazon_search_results = None

        # Initialize messages lists
        success_messages = []
        error_messages = []

        # Create two columns for different retailer types
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Brand-based Retailers")
            
            # Walmart and Target Section
            st.write("### Walmart and Target")
            walmart_selected = st.checkbox("Walmart", key="walmart_checkbox")
            target_selected = st.checkbox("Target", key="target_checkbox")
            
            if walmart_selected or target_selected:
                # Single search box for both Walmart and Target
                search_term = st.text_input(
                    "Search Brand for Walmart/Target:",
                    help="Type to search for available brands",
                    key="walmart_target_search"
                )
                
                if search_term:
                    search_results = search_items(search_term, "Brand Name")
                    
                    if search_results:
                        selected_values = st.multiselect(
                            "Select Brand(s) for Walmart/Target:",
                            options=search_results,
                            key="walmart_target_brand_select"
                        )
                    else:
                        st.info("No brands found.")
                        error_messages.append("No brands found for Walmart/Target. Please try a different search term.")

        with col2:
            st.subheader("URL-based Retailers")
            homedepot_selected = st.checkbox("Home Depot")
            lowes_selected = st.checkbox("Lowes")

            if homedepot_selected or lowes_selected:
                if homedepot_selected:
                    st.write("### Home Depot")
                    homedepot_url = st.text_input(
                        "Enter Home Depot Brand URL:",
                        help="Enter the URL for the brand page (must start with http:// or https://)",
                        key="homedepot_url"
                    )
                
                if lowes_selected:
                    st.write("### Lowes")
                    lowes_url = st.text_input(
                        "Enter Lowes Brand URL:",
                        help="Enter the URL for the brand page (must start with http:// or https://)",
                        key="lowes_url"
                    )

        # Single submit button for all selected retailers
        if (walmart_selected or target_selected or homedepot_selected or lowes_selected) and st.button("Submit All Selected Retailers"):
            with st.spinner('Submitting to selected retailers...'):
                success_messages = []
                error_messages = []

                # Handle Walmart and Target submissions
                if walmart_selected or target_selected:
                    if 'selected_values' in locals() and selected_values:
                        # Handle multiple brands
                        if len(selected_values) > 1:
                            if walmart_selected:
                                update_multiple_brands(selected_values, "Walmart")
                                success_messages.append("Successfully submitted brands to Walmart")
                            if target_selected:
                                update_multiple_brands(selected_values, "Target")
                                success_messages.append("Successfully submitted brands to Target")
                        else:
                            if walmart_selected:
                                update_selection("Brand", selected_values[0], "Walmart")
                                success_messages.append("Successfully submitted brand to Walmart")
                            if target_selected:
                                update_selection("Brand", selected_values[0], "Target")
                                success_messages.append("Successfully submitted brand to Target")
                    else:
                        error_messages.append("Please select or enter brands for Walmart/Target")

                # Handle Home Depot submission
                if homedepot_selected:
                    if 'homedepot_url' in locals() and homedepot_url:
                        is_valid, error_message = validate_url(homedepot_url)
                        if is_valid:
                            update_selection("Brand", homedepot_url, "Home Depot")
                            success_messages.append("Successfully submitted Home Depot brand URL")
                        else:
                            error_messages.append(f"Home Depot URL error: {error_message}")
                    else:
                        error_messages.append("Please enter Home Depot URL")

                # Handle Lowes submission
                if lowes_selected:
                    if 'lowes_url' in locals() and lowes_url:
                        is_valid, error_message = validate_url(lowes_url)
                        if is_valid:
                            update_selection("Brand", lowes_url, "Lowes")
                            success_messages.append("Successfully submitted Lowes brand URL")
                        else:
                            error_messages.append(f"Lowes URL error: {error_message}")
                    else:
                        error_messages.append("Please enter Lowes URL")

                # Display success and error messages
                for msg in success_messages:
                    st.success(msg)
                for msg in error_messages:
                    st.error(msg)

        # Display current selections
        if 'selected_values' in locals() and selected_values:
            st.info(f"Current Walmart/Target Selection: {', '.join(selected_values)}")
        if 'homedepot_url' in locals() and homedepot_url:
            st.info(f"Current Home Depot URL: {homedepot_url}")
        if 'lowes_url' in locals() and lowes_url:
            st.info(f"Current Lowes URL: {lowes_url}")

def update_selection(selection_type, selection_value, x_amazon_type=None):
    """Update the selection in Snowflake"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Generate a unique GUID for the request
            req_guid = str(uuid.uuid4())
            
            # Get requestor from session state
            requestor = st.session_state.requestor_name
            
            # Use RUN_TYPE from config
            run_type = RUN_TYPE
            
            # Brand selection for X-Amazon retailers
            if x_amazon_type == "Home Depot":
                brand_name = "NOTSPECIFIEDUNUSED"
                company_name = "NOTSPECIFIEDUNUSED"
                concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                request_type = "HomeDepot Brand"
                status = "0"
                is_multiple = "False"  # Set to False for single brand submission
                url_value = selection_value  # Use URL for Home Depot
                requestor_email = st.session_state.requestor_email
            elif x_amazon_type == "Lowes":
                brand_name = "NOTSPECIFIEDUNUSED"
                company_name = "NOTSPECIFIEDUNUSED"
                concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                request_type = "Lowes Brand"
                status = "0"
                is_multiple = "False"  # Set to False for single brand submission
                url_value = selection_value  # Use URL for Lowes
                requestor_email = st.session_state.requestor_email
            elif x_amazon_type == "Target":
                brand_name = selection_value
                company_name = "NOTSPECIFIEDUNUSED"
                concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                request_type = "Target Brand"
                status = "0"
                is_multiple = "False"  # Set to False for single brand submission
                url_value = None
                requestor_email = st.session_state.requestor_email
            elif x_amazon_type == "Walmart":
                brand_name = selection_value
                company_name = "NOTSPECIFIEDUNUSED"
                concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                request_type = "Walmart Brand"
                status = "0"
                is_multiple = "False"  # Set to False for single brand submission
                url_value = None
                requestor_email = st.session_state.requestor_email
            else:
                st.error("Invalid X-Amazon type")
                return

            # Check if selection_value contains semicolons (multiple brands)
            if ";" in selection_value:
                # Split the brands and handle them as multiple submissions
                brands_list = [brand.strip() for brand in selection_value.split(";")]
                update_multiple_brands(brands_list, x_amazon_type)
                return

            # Insert into the BULLSEYE_REQUEST table
            query = """
            INSERT INTO BOABD.POWERAPP.BULLSEYE_REQUEST (
                BRANDNAME,
                COMPANYNAME,
                CONCAT_LEAD_LIST_NAME,
                REQUEST_SUBMISSION_TIME,
                REQUEST_TYPE,
                REQUESTOR,
                REQUESTOR_EMAIL,
                STATUS,
                ISMULTIPLEBRANDSUBMISSION,
                REQ_GUID,
                RUN_TYPE,
                URL
            ) VALUES (
                %s,
                %s,
                %s,
                CURRENT_TIMESTAMP,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """
            
            try:
                cursor.execute(query, (
                    brand_name,
                    company_name,
                    concat_lead_list_name,
                    request_type,
                    requestor,
                    requestor_email,
                    status,
                    is_multiple,
                    req_guid,
                    run_type,
                    url_value
                ))
                conn.commit()
                st.success(f"✅ Record Added to Request Table: {selection_value}")
            except Exception as e:
                st.error(f"Failed to insert into BULLSEYE_REQUEST: {str(e)}")
                return

            # Insert into Echo Table and update status
            try:
                if insert_into_keepa_table(None, req_guid, "Brand", selection_value, x_amazon_type):
                    st.success(f"✅ Sent to Echo Table: {selection_value}")
                    if update_bullseye_status(req_guid, "2"):
                        st.success(f"✅ Successfully Submitted: {selection_value}")
                    else:
                        st.error(f"❌ Failed to update status for: {selection_value}")
                else:
                    st.error(f"❌ Failed to process {x_amazon_type} request. The request was not added to the processing queue. Please try again or contact support.")
            except Exception as e:
                st.error(f"❌ Error processing request: {str(e)}")

            cursor.close()
            conn.close()

        except Exception as e:
            st.error(f"Error submitting request: {str(e)}")

def update_multiple_brands(brands_list, x_amazon_type):
    """Handle multiple brand submissions with the same REQ_GUID"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            req_guid = str(uuid.uuid4())
            # Get requestor from session state
            requestor = st.session_state.requestor_name
            run_type = RUN_TYPE  # Use RUN_TYPE from config
            requestor_email = st.session_state.requestor_email  # Add requestor email
            
            # Determine request type based on submission type and X-Amazon type
            if x_amazon_type == "Home Depot":
                request_type = "HomeDepot Brand"
            elif x_amazon_type == "Lowes":
                request_type = "Lowes Brand"
            elif x_amazon_type == "Target":
                request_type = "Target Brand"
            elif x_amazon_type == "Walmart":
                request_type = "Walmart Brand"
            else:
                request_type = "Amazon Brand Name New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Amazon Brand Name"
            
            # Set ISMULTIPLEBRANDSUBMISSION based on number of brands
            is_multiple = 'True' if len(brands_list) > 1 else 'False'
            
            for brand in brands_list:
                query = """
                INSERT INTO BOABD.POWERAPP.BULLSEYE_REQUEST (
                    BRANDNAME,
                    COMPANYNAME,
                    CONCAT_LEAD_LIST_NAME,
                    REQUEST_SUBMISSION_TIME,
                    REQUEST_TYPE,
                    REQUESTOR,
                    REQUESTOR_EMAIL,
                    STATUS,
                    ISMULTIPLEBRANDSUBMISSION,
                    REQ_GUID,
                    RUN_TYPE,
                    URL
                ) VALUES (
                    %s,
                    'NOTSPECIFIEDUNUSED',
                    'NOTSPECIFIEDUNUSED',
                    CURRENT_TIMESTAMP,
                    %s,
                    %s,
                    %s,
                    '0',
                    %s,
                    %s,
                    %s,
                    %s
                )
                """
                
                # Set URL value based on x_amazon_type
                url_value = brand if x_amazon_type in ["Home Depot", "Lowes"] else None
                
                cursor.execute(query, (
                    brand,  # brand is already a string
                    request_type,
                    requestor,
                    requestor_email,
                    is_multiple,
                    req_guid,
                    run_type,
                    url_value
                ))
            
            conn.commit()
            cursor.close()
            conn.close()

            # Insert all brands into Echo Table and update status
            keepa_success = True
            for brand in brands_list:
                if not insert_into_keepa_table(None, req_guid, "Brand", brand, x_amazon_type):
                    keepa_success = False
                    break
            
            if keepa_success:
                if update_bullseye_status(req_guid, "2"):
                    st.success(f"✅ Record Added to Request Table: {', '.join(brands_list)}")
                    st.success(f"✅ Sent to Echo Table: {', '.join(brands_list)}")
                    st.success(f"✅ Successfully Submitted: {', '.join(brands_list)}")
                else:
                    st.error(f"❌ Failed to update status for: {', '.join(brands_list)}")
            else:
                st.error(f"❌ Failed to process brands. The request was not added to the processing queue. Please try again or contact support.")
        except Exception as e:
            st.error(f"Error submitting multiple brand requests: {str(e)}") 

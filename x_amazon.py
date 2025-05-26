import streamlit as st
from shared_functions import (
    search_items, 
    update_multiple_brands, 
    update_selection,
    get_snowflake_connection,
    insert_into_keepa_table,
    update_bullseye_status
)
from send_email import send_email_notification
from config import RUN_TYPE
import re
import uuid
from datetime import datetime

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
        # Initialize session state for X-Amazon search results and selected brands
        if 'x_amazon_search_results' not in st.session_state:
            st.session_state.x_amazon_search_results = None
        if 'walmart_selected_brands' not in st.session_state:
            st.session_state.walmart_selected_brands = []
        if 'target_selected_brands' not in st.session_state:
            st.session_state.target_selected_brands = []

        # Initialize messages lists
        success_messages = []
        error_messages = []

        # Create two columns for different retailer types
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Brand-based Retailers")
            
            # Walmart Section
            st.write("### Walmart")
            walmart_selected = st.checkbox("Walmart", key="walmart_checkbox")
            
            if walmart_selected:
                # Search box for Walmart
                walmart_search = st.text_input(
                    "Search Brand for Walmart:",
                    help="Type to search for available brands",
                    key="walmart_search"
                )
                
                if walmart_search:
                    walmart_results = search_items(walmart_search, "Brand Name")
                    
                    if walmart_results:
                        # Combine new search results with previously selected brands
                        all_walmart_options = list(set(walmart_results + st.session_state.walmart_selected_brands))
                        walmart_selected_values = st.multiselect(
                            "Select Brand(s) for Walmart:",
                            options=all_walmart_options,
                            default=st.session_state.walmart_selected_brands,
                            key="walmart_brand_select"
                        )
                        # Update session state with current selections
                        st.session_state.walmart_selected_brands = walmart_selected_values
                    else:
                        st.info("No brands found for Walmart.")
                        # Enable Brand Not in HubSpot option when no brands are found
                        walmart_not_in_hubspot = st.text_input(
                            "Walmart Brand Not in HubSpot",
                            help="Enter brand name(s) separated by semicolons for multiple brands",
                            key="walmart_not_in_hubspot"
                        )

            # Target Section
            st.write("### Target")
            target_selected = st.checkbox("Target", key="target_checkbox")
            
            if target_selected:
                # Search box for Target
                target_search = st.text_input(
                    "Search Brand for Target:",
                    help="Type to search for available brands",
                    key="target_search"
                )
                
                if target_search:
                    target_results = search_items(target_search, "Brand Name")
                    
                    if target_results:
                        # Combine new search results with previously selected brands
                        all_target_options = list(set(target_results + st.session_state.target_selected_brands))
                        target_selected_values = st.multiselect(
                            "Select Brand(s) for Target:",
                            options=all_target_options,
                            default=st.session_state.target_selected_brands,
                            key="target_brand_select"
                        )
                        # Update session state with current selections
                        st.session_state.target_selected_brands = target_selected_values
                    else:
                        st.info("No brands found for Target.")
                        # Enable Brand Not in HubSpot option when no brands are found
                        target_not_in_hubspot = st.text_input(
                            "Target Brand Not in HubSpot",
                            help="Enter brand name(s) separated by semicolons for multiple brands",
                            key="target_not_in_hubspot"
                        )

        with col2:
            st.subheader("URL-based Retailers")
            homedepot_selected = st.checkbox("Home Depot", key="homedepot_checkbox")
            lowes_selected = st.checkbox("Lowes", key="lowes_checkbox")

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

                # Handle Walmart submission
                if walmart_selected:
                    if 'walmart_selected_values' in locals() and walmart_selected_values:
                        # Reset submission type for dropdown selection
                        st.session_state.submission_type = None
                        # Handle multiple brands
                        if len(walmart_selected_values) > 1:
                            update_multiple_brands(walmart_selected_values, "Walmart")
                            success_messages.append("Successfully submitted brands to Walmart")
                        else:
                            update_selection("Brand", walmart_selected_values[0], "Walmart")
                            success_messages.append("Successfully submitted brand to Walmart")
                    elif 'walmart_not_in_hubspot' in locals() and walmart_not_in_hubspot:
                        # Handle Brand Not in HubSpot submissions
                        st.session_state.submission_type = "Brand Not in HubSpot"
                        if ";" in walmart_not_in_hubspot:
                            brands_list = [brand.strip() for brand in walmart_not_in_hubspot.split(";")]
                            update_multiple_brands(brands_list, "Walmart")
                            success_messages.append("Successfully submitted new brands to Walmart")
                        else:
                            update_selection("Brand", walmart_not_in_hubspot, "Walmart")
                            success_messages.append("Successfully submitted new brand to Walmart")
                    else:
                        error_messages.append("Please select or enter brands for Walmart")

                # Handle Target submission
                if target_selected:
                    if 'target_selected_values' in locals() and target_selected_values:
                        # Reset submission type for dropdown selection
                        st.session_state.submission_type = None
                        # Handle multiple brands
                        if len(target_selected_values) > 1:
                            update_multiple_brands(target_selected_values, "Target")
                            success_messages.append("Successfully submitted brands to Target")
                        else:
                            update_selection("Brand", target_selected_values[0], "Target")
                            success_messages.append("Successfully submitted brand to Target")
                    elif 'target_not_in_hubspot' in locals() and target_not_in_hubspot:
                        # Handle Brand Not in HubSpot submissions
                        st.session_state.submission_type = "Brand Not in HubSpot"
                        if ";" in target_not_in_hubspot:
                            brands_list = [brand.strip() for brand in target_not_in_hubspot.split(";")]
                            update_multiple_brands(brands_list, "Target")
                            success_messages.append("Successfully submitted new brands to Target")
                        else:
                            update_selection("Brand", target_not_in_hubspot, "Target")
                            success_messages.append("Successfully submitted new brand to Target")
                    else:
                        error_messages.append("Please select or enter brands for Target")

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

                # Send email notification if there were successful submissions
                if success_messages:
                    # Collect all submitted values for email notification
                    submitted_values = []
                    
                    # Helper function to format submissions
                    def format_retailer_submissions(retailer, values):
                        if not values:
                            return None
                        # Handle both list and string inputs
                        if isinstance(values, str):
                            values = [values]
                        # Remove any empty strings
                        values = [v.strip() for v in values if v and v.strip()]
                        if not values:
                            return None
                        return f"{retailer}: {', '.join(values)}"
                    
                    # Collect submissions for each retailer
                    walmart_submissions = format_retailer_submissions(
                        "Walmart", 
                        walmart_selected_values if 'walmart_selected_values' in locals() and walmart_selected_values 
                        else [walmart_not_in_hubspot] if 'walmart_not_in_hubspot' in locals() and walmart_not_in_hubspot 
                        else None
                    )
                    
                    target_submissions = format_retailer_submissions(
                        "Target", 
                        target_selected_values if 'target_selected_values' in locals() and target_selected_values 
                        else [target_not_in_hubspot] if 'target_not_in_hubspot' in locals() and target_not_in_hubspot 
                        else None
                    )
                    
                    homedepot_submission = format_retailer_submissions(
                        "Home Depot", 
                        [homedepot_url] if 'homedepot_url' in locals() and homedepot_url 
                        else None
                    )
                    
                    lowes_submission = format_retailer_submissions(
                        "Lowes", 
                        [lowes_url] if 'lowes_url' in locals() and lowes_url 
                        else None
                    )
                    
                    # Combine all submissions, filtering out None values
                    all_submissions = [s for s in [walmart_submissions, target_submissions, homedepot_submission, lowes_submission] if s]
                    query_value = " | ".join(all_submissions) if all_submissions else ""
                    
                    # Only send email if we have a non-empty query value
                    if query_value:
                        if send_email_notification(query_value, st.session_state.requestor_email):
                            st.success("Email notification sent successfully")

        # Display current selections
        if 'walmart_selected_values' in locals() and walmart_selected_values:
            st.info(f"Current Walmart Selection: {', '.join(walmart_selected_values)}")
        if 'target_selected_values' in locals() and target_selected_values:
            st.info(f"Current Target Selection: {', '.join(target_selected_values)}")
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
                # Set request type based on submission type
                request_type = "Target Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Target Brand"
                status = "0"
                is_multiple = "False"  # Set to False for single brand submission
                url_value = None
                requestor_email = st.session_state.requestor_email
            elif x_amazon_type == "Walmart":
                brand_name = selection_value
                company_name = "NOTSPECIFIEDUNUSED"
                concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                # Set request type based on submission type
                request_type = "Walmart Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Walmart Brand"
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

            # For brand submissions, also insert into Keepa Table and update status
            if insert_into_keepa_table(None, req_guid, selection_type, selection_value, x_amazon_type):
                st.success(f"✅ Sent to Keepa/Echo Table: {selection_value}")
                if update_bullseye_status(req_guid, "2"):
                    st.success(f"✅ Successfully Submitted: {selection_value}")
                else:
                    st.error(f"❌ Failed to update status for: {selection_value}")
            else:
                st.error(f"❌ Failed to process brand '{selection_value}'. The request was not added to the processing queue. Please try again or contact support.")

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
                request_type = "Target Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Target Brand"
            elif x_amazon_type == "Walmart":
                request_type = "Walmart Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Walmart Brand"
            else:
                request_type = "Amazon Brand Name New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Amazon Brand Name"
            
            # Set ISMULTIPLEBRANDSUBMISSION based on number of brands
            is_multiple = 'Yes' if len(brands_list) > 1 else 'No'
            
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

            # Insert all brands into Keepa Table and update status
            keepa_success = True
            for brand in brands_list:
                if not insert_into_keepa_table(None, req_guid, "Brand", brand, x_amazon_type):
                    keepa_success = False
                    break
            
            if keepa_success:
                if update_bullseye_status(req_guid, "2"):
                    st.success(f"Successfully submitted {len(brands_list)} brand requests")
                else:
                    st.warning(f"Brand requests submitted but status update failed")
            else:
                st.warning(f"Brand requests submitted but Keepa Table insertion failed for some brands")
        except Exception as e:
            st.error(f"Error submitting multiple brand requests: {str(e)}") 
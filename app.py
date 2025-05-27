import streamlit as st
import snowflake.connector
import os
import pandas as pd
import uuid
from config import SNOWFLAKE_CONFIG, KEEPA_QUERIES_TABLE, RUN_TYPE, ENV_TYPE
from x_amazon import show_x_amazon_section
from shared_functions import (
    get_snowflake_connection,
    get_keepa_connection,
    search_items,
    insert_into_keepa_table,
    update_bullseye_status,
    update_selection,
    update_multiple_brands
)
import re
import getpass
from amazon import show_amazon_section

def is_valid_url(url):
    """Validate if the input is a valid URL"""
    url_pattern = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'  # domain
        r'[a-zA-Z]{2,}'  # TLD
        r'(/[a-zA-Z0-9-._~:/?#[\]@!$&\'()*+,;=]*)?$'  # path
    )
    return bool(url_pattern.match(url))

def get_user_name():
    """Get the current user's name from the system"""
    try:
        # Try to get the user's full name from environment variables
        user_name = os.getenv('USERNAME') or os.getenv('USER')
        if user_name:
            return user_name
        # Fallback to getpass if environment variables are not available
        return getpass.getuser()
    except:
        return "RPA Bot"

# Global requestor variable
REQUESTOR = "RPA Bot"

# Initialize session state for selection tracking
if 'selected_type' not in st.session_state:
    st.session_state.selected_type = None
if 'selected_value' not in st.session_state:
    st.session_state.selected_value = None
if 'requestor_name' not in st.session_state:
    st.session_state.requestor_name = REQUESTOR

# Initialize session state variables
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'submission_type' not in st.session_state:
    st.session_state.submission_type = None

def get_brands():
    """Fetch brands from Snowflake"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT brand as brand_name
                FROM boabd.hubspot.company_brand_associations
                ORDER BY brand_name
            """)
            brands = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return brands
        except Exception as e:
            st.error(f"Error fetching brands: {str(e)}")
    return []

def get_companies():
    """Fetch companies from Snowflake"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cmp1.company_id, cmp1.company_name, cmp1.concat_lead_list_name, 
                       cmp2.concat_lead_list_name as concat_lead_list_name_final 
                FROM boabd.hubspot.company_data cmp1
                INNER JOIN boabd.hubspot.COMPANY_LEADLISTID_ASSOCIATIONS cmp2
                ON cmp1.company_id = cmp2.company_id
                ORDER BY cmp1.company_name
            """)
            companies = cursor.fetchall()
            cursor.close()
            conn.close()
            # Return list of tuples (company_name, concat_lead_list_name_final)
            return [(row[1], row[3]) for row in companies]
        except Exception as e:
            st.error(f"Error fetching companies: {str(e)}")
    return []

def insert_into_keepa_table(company_data, req_guid, selection_type, brand_name=None, x_amazon_type=None):
    """Insert data into the Keepa Table or Echo Queries Table based on submission type"""
    conn = get_keepa_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Set query type and value based on selection type and X-Amazon type
        if x_amazon_type:
            # For X-Amazon submissions, use ECHO_QUERIES table
            query_type = "homedepot_brand" if x_amazon_type == "Home Depot" else "lowes_brand" if x_amazon_type == "Lowes" else f"{x_amazon_type.lower()}_brand"
            query_value = brand_name if x_amazon_type.lower() in ['homedepot', 'lowes'] else brand_name
            table_name = "BOABD.INPUTDATA.ECHO_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.ECHO_QUERIES"
            st.write(f"Debug - Using ECHO_QUERIES table for {x_amazon_type} submission")  # Debug log
        else:
            # For Amazon submissions, use KEEPA_QUERIES table
            query_type = "manufacturer_only" if selection_type == "Company" else "brand"
            query_value = company_data[3] if selection_type == "Company" else brand_name
            table_name = "BOABD.INPUTDATA.KEEPA_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.KEEPA_QUERIES"
            st.write(f"Debug - Using KEEPA_QUERIES table for Amazon {selection_type} submission")  # Debug log
        
        st.write(f"Debug - ENV_TYPE: {ENV_TYPE}")  # Debug log for ENV_TYPE
        st.write(f"Debug - Using table: {table_name}")  # Debug log for table selection
        
        query = f"""
        INSERT INTO {table_name} (
            QUERY_TYPE,
            QUERY_VALUE,
            WRITE_TIME,
            REQUEST_GUID,
            STATUS
        ) VALUES (
            %s,
            %s,
            CURRENT_TIMESTAMP,
            %s,
            %s
        )
        """
        
        cursor.execute(query, (
            query_type,
            query_value,
            req_guid,
            "0"  # STATUS
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error inserting into {table_name}: {str(e)}")
        return False

def update_bullseye_status(req_guid, status):
    """Update the status in BULLSEYE_REQUEST table"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        query = """
        UPDATE BOABD.POWERAPP.BULLSEYE_REQUEST
        SET STATUS = %s
        WHERE REQ_GUID = %s
        """
        
        cursor.execute(query, (status, req_guid))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error updating BULLSEYE_REQUEST status: {str(e)}")
        return False

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
            
            # Prepare values based on selection type
            if selection_type == "Company":
                # Check if search results exist
                if not st.session_state.amazon_search_results:
                    st.error("No search results available. Please search for a company first.")
                    return
                
                # Find the company data from search results
                company_data = next((row for row in st.session_state.amazon_search_results if row[1] == selection_value), None)
                if company_data:
                    company_name = company_data[1]  # Use company_name from row[1]
                    concat_lead_list_name = company_data[3]  # Use concat_lead_list_name from row[3]
                    brand_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Amazon Company Name"
                    status = "0"
                    is_multiple = "False"  # Single entry for company name
                    url_value = None  # URL is blank for company name
                    requestor_email = st.session_state.requestor_email  # Capture requestor email
                    st.write(f"Debug - Company Data: {company_data}")  # Debug log
                else:
                    st.error(f"Company data not found for: {selection_value}")
                    st.write(f"Debug - Available search results: {st.session_state.amazon_search_results}")  # Debug log
                    return
            else:  # Brand selection
                if x_amazon_type == "Home Depot":
                    brand_name = "NOTSPECIFIEDUNUSED"
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "HomeDepot Brand"
                    status = "0"
                    is_multiple = "Yes"  # Assume multiple brands for Home Depot
                    url_value = selection_value  # Use URL for Home Depot
                    requestor_email = st.session_state.requestor_email
                elif x_amazon_type == "Lowes":
                    brand_name = "NOTSPECIFIEDUNUSED"
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Lowes Brand"
                    status = "0"
                    is_multiple = "Yes"  # Assume multiple brands for Lowes
                    url_value = selection_value  # Use URL for Lowes
                    requestor_email = st.session_state.requestor_email
                elif x_amazon_type == "Target":
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Target Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Target Brand"
                    status = "0"
                    is_multiple = "Yes"  # Assume multiple brands for Target
                    url_value = None
                    requestor_email = st.session_state.requestor_email
                elif x_amazon_type == "Walmart":
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Walmart Brand New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Walmart Brand"
                    status = "0"
                    is_multiple = "Yes"  # Assume multiple brands for Walmart
                    url_value = None
                    requestor_email = st.session_state.requestor_email
                else:
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    # Set request type based on submission type
                    request_type = "Amazon Brand Name New" if st.session_state.submission_type == "Brand Not in HubSpot" else "Amazon Brand Name"
                    status = "0"
                    is_multiple = "Yes"  # Assume multiple brands for general brand submissions
                    url_value = None
                    requestor_email = st.session_state.requestor_email

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
                    requestor_email,  # Include requestor email
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

            # For company submissions, insert into Keepa Table and update status
            if selection_type == "Company":
                st.write(f"Debug - Attempting to insert company data: {company_data}")  # Debug log
                if not company_data:  # Additional check
                    st.error("Company data is missing. Cannot proceed with submission.")
                    return
                    
                if insert_into_keepa_table(company_data, req_guid, selection_type):
                    st.success(f"✅ Sent to Keepa/Echo Table: {selection_value}")
                    if update_bullseye_status(req_guid, "2"):
                        st.success(f"✅ Successfully Submitted: {selection_value}")
                    else:
                        st.error(f"❌ Failed to update status for: {selection_value}")
                else:
                    st.error(f"❌ Failed to process company '{selection_value}'. The request was not added to the processing queue. Please try again or contact support.")
            else:
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

# Add new function to handle multiple brand submissions
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
                    st.session_state.requestor_email,  # Add requestor email
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

def validate_email(email):
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    return True, ""

def main():
    st.set_page_config(
        page_title="Amazon Submission App",
        page_icon="🛍️",
        layout="wide"
    )

    # Initialize session state variables
    if 'requestor_name' not in st.session_state:
        st.session_state.requestor_name = "RPA Bot"
    if 'requestor_email' not in st.session_state:
        st.session_state.requestor_email = "mohammad.asim@spreetail.com"
    if 'amazon_search_results' not in st.session_state:
        st.session_state.amazon_search_results = None
    if 'amazon_submission_type' not in st.session_state:
        st.session_state.amazon_submission_type = None

    # Requestor Information Section
    st.subheader("Requestor Information")
    col1, col2 = st.columns(2)
    
    with col1:
        requestor_name = st.text_input(
            "Requestor Name:",
            value=st.session_state.requestor_name,
            help="Name of the person making the request"
        )
        st.session_state.requestor_name = requestor_name
    
    with col2:
        requestor_email = st.text_input(
            "Requestor Email:",
            value=st.session_state.requestor_email,
            help="Email address of the requestor (required)",
            placeholder="Enter your email address"
        )
        if not requestor_email:
            st.error("Email is required")
        else:
            is_valid_email, email_error = validate_email(requestor_email)
            if not is_valid_email:
                st.error(email_error)
            else:
                st.session_state.requestor_email = requestor_email

    # Only proceed if email is valid
    if requestor_email and validate_email(requestor_email)[0]:
        # Create tabs for Amazon and X-Amazon sections
        tab1, tab2 = st.tabs(["Amazon Submission", "X-Amazon Submission"])
        
        with tab1:
            show_amazon_section()
        
        with tab2:
            show_x_amazon_section()

if __name__ == "__main__":
    main() 

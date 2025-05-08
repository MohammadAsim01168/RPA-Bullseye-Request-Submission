import streamlit as st
import snowflake.connector
from dotenv import load_dotenv
import os
import pandas as pd
import uuid
from config import SNOWFLAKE_CONFIG, KEEPA_QUERIES_TABLE, RUN_TYPE
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

# Load environment variables
load_dotenv(override=True)  # Force override existing variables

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
            # Convert "Home Depot" to "homedepot" and "Lowes" to "lowes" for query_type
            query_type = "homedepot_brand" if x_amazon_type == "Home Depot" else "lowes_brand" if x_amazon_type == "Lowes" else f"{x_amazon_type.lower()}_brand"
            # For Home Depot and Lowes, use the URL as query value
            query_value = brand_name if x_amazon_type.lower() in ['homedepot', 'lowes'] else brand_name
            table_name = "BOABD.INPUTDATA.ECHO_QUERIES_DEV" if RUN_TYPE == "Test" else "BOABD.INPUTDATA.ECHO_QUERIES"
        else:
            # For Amazon submissions, use KEEPA_QUERIES table
            query_type = "manufacturer_only" if selection_type == "Company" else "brand"
            query_value = company_data[3] if selection_type == "Company" else brand_name
            table_name = KEEPA_QUERIES_TABLE
        
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
            req_guid,  # Use REQUEST_GUID from BULLSEYE_REQUEST
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
                # Find the company data from search results
                company_data = next((row for row in st.session_state.search_results if row[1] == selection_value), None)
                if company_data:
                    company_name = company_data[1]  # Use company_name from row[1]
                    concat_lead_list_name = company_data[3]  # Use concat_lead_list_name from row[3]
                    brand_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Amazon Company Name"
                    status = "0"
                else:
                    st.error("Company data not found")
                    return
            else:  # Brand selection
                if x_amazon_type == "Home Depot":
                    brand_name = "NOTSPECIFIEDUNUSED"
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "HomeDepot Brand"
                    status = "0"
                elif x_amazon_type == "Lowes":
                    brand_name = "NOTSPECIFIEDUNUSED"
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Lowes Brand"
                    status = "0"
                elif x_amazon_type == "Target":
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Target Brand"
                    status = "0"
                elif x_amazon_type == "Walmart":
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Walmart Brand"
                    status = "0"
                else:
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    # Set request type based on submission type
                    request_type = "Amazon Brand Name New" if st.session_state.submission_type == "Missing Brand" else "Amazon Brand Name"
                    status = "0"

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
                'No',
                %s,
                %s,
                %s
            )
            """
            
            # Set URL value based on x_amazon_type
            url_value = selection_value if x_amazon_type in ["Home Depot", "Lowes"] else None
            
            cursor.execute(query, (
                brand_name,
                company_name,
                concat_lead_list_name,
                request_type,
                requestor,
                status,
                req_guid,
                run_type,
                url_value
            ))
            
            conn.commit()
            cursor.close()
            conn.close()

            # For company submissions, insert into Keepa Table and update status
            if selection_type == "Company":
                if insert_into_keepa_table(company_data, req_guid, selection_type):
                    if update_bullseye_status(req_guid, "2"):
                        st.success(f"Successfully submitted company request and updated status: {selection_value}")
                    else:
                        st.warning(f"Company request submitted but status update failed: {selection_value}")
                else:
                    st.warning(f"Company request submitted but Keepa Table insertion failed: {selection_value}")
            else:
                # For brand submissions, also insert into Keepa Table and update status
                if insert_into_keepa_table(None, req_guid, selection_type, selection_value, x_amazon_type):
                    if update_bullseye_status(req_guid, "2"):
                        st.success(f"Successfully submitted {selection_type} request: {selection_value}")
                    else:
                        st.warning(f"Brand request submitted but status update failed: {selection_value}")
                else:
                    st.warning(f"Brand request submitted but Keepa Table insertion failed: {selection_value}")

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
                request_type = "Amazon Brand Name New" if st.session_state.submission_type == "Missing Brand" else "Amazon Brand Name"
            
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

# Main app
app_type = st.radio(
    "Select Application Type:",
    ["Amazon Submission", "X-Amazon Submission"],
    key="app_type"
)

# Add requestor name input field at the top level with system username as default
requestor_name = st.text_input(
    "Enter Your Name:",
    value=st.session_state.requestor_name,
    help="Please enter your name for tracking purposes"
)

# Update session state with the input value
if requestor_name and requestor_name.strip():
    st.session_state.requestor_name = requestor_name
else:
    st.session_state.requestor_name = REQUESTOR

# Initialize session state variables
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'submission_type' not in st.session_state:
    st.session_state.submission_type = None

if app_type == "Amazon Submission":
    st.title("Amazon Submission")

    # Add a loading spinner while initializing
    with st.spinner('Initializing application...'):
        # Selection type radio buttons
        submission_type = st.radio(
            "Select Submission Type:",
            ["Brand Name", "Missing Brand", "Company Name"],
            key="submission_type"
        )

        # Handle different submission types
        if submission_type == "Brand Name":
            # Search box for brand selection
            search_term = st.text_input(
                "Search Brand:",
                help="Type to search for available options"
            )
            
            if search_term:
                search_results = search_items(search_term, "Brand Name")
                st.session_state.search_results = search_results
                
                if search_results:
                    # For brand search, results are already just brand names
                    selected_values = st.multiselect(
                        "Select Brand(s):",
                        options=search_results,
                        key="brand_select"
                    )
                    
                    if st.button("Submit Selected Brands"):
                        with st.spinner('Submitting brands...'):
                            if selected_values:
                                if len(selected_values) > 1:
                                    update_multiple_brands(selected_values, None)
                                else:
                                    update_selection("Brand", selected_values[0], None)
                            else:
                                st.warning("Please select at least one brand.")
                else:
                    st.info("No brands found.")
        
        elif submission_type == "Missing Brand":
            # Manual brand entry
            brand_name = st.text_input(
                "Enter Brand Name:",
                help="Type the brand name manually"
            )
            
            # Add note about multiple brands
            st.info("For multiple brands, enter them separated by semicolons (e.g., brand1;brand2;brand3)")
            
            if st.button("Submit Missing Brand"):
                with st.spinner('Submitting missing brand...'):
                    if brand_name:
                        update_selection("Brand", brand_name)
                    else:
                        st.warning("Please enter a brand name.")
        
        elif submission_type == "Company Name":
            # Search box for company selection
            search_term = st.text_input(
                "Search Company:",
                help="Type to search for available options"
            )
            
            if search_term:
                search_results = search_items(search_term, "Company Name")
                st.session_state.search_results = search_results
                
                if search_results:
                    # For company search, show company names in dropdown
                    company_names = [row[1] for row in search_results]
                    selected_company = st.selectbox(
                        "Select Company:",
                        options=company_names,
                        key="company_select"
                    )
                    
                    if st.button("Submit Selected Company"):
                        with st.spinner('Submitting company...'):
                            if selected_company:
                                update_selection("Company", selected_company)
                            else:
                                st.warning("Please select a company.")
                else:
                    st.info("No companies found.")

        # Display current selection
        if submission_type in ["Brand Name", "Company Name"] and 'selected_values' in locals() and selected_values:
            # Convert to list if it's a tuple and ensure all items are strings
            display_values = [str(val) for val in selected_values]
            st.info(f"Current Selection: {', '.join(display_values)}")

else:  # X-Amazon Submission
    show_x_amazon_section() 
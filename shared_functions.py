import streamlit as st
import snowflake.connector
from config import SNOWFLAKE_CONFIG, KEEPA_QUERIES_TABLE, RUN_TYPE, ENV_TYPE
import uuid

# Global requestor variable
REQUESTOR = "RPA Bot"

def get_snowflake_connection():
    """Create and return a Snowflake connection"""
    try:
        # Create connection parameters dictionary
        conn_params = {
            'user': SNOWFLAKE_CONFIG['user'],
            'password': SNOWFLAKE_CONFIG['password'],
            'account': SNOWFLAKE_CONFIG['account'],
            'warehouse': SNOWFLAKE_CONFIG['warehouse'],
            'database': SNOWFLAKE_CONFIG['database'],
            'schema': SNOWFLAKE_CONFIG['schema'],
            'role': SNOWFLAKE_CONFIG['role'],
            'protocol': 'https',
            'host': f"{SNOWFLAKE_CONFIG['account']}.snowflakecomputing.com",
            'port': 443,
            'timeout': 60,
            'retry_count': 3,
            'retry_delay': 5
        }
        
        conn = snowflake.connector.connect(**conn_params)
        return conn
    except Exception as e:
        st.error(f"Error connecting to Snowflake: {str(e)}")
        return None

def get_keepa_connection():
    """Create and return a connection to the Keepa Queries Table"""
    try:
        conn = snowflake.connector.connect(
            user=SNOWFLAKE_CONFIG['user'],
            password=SNOWFLAKE_CONFIG['password'],
            account=SNOWFLAKE_CONFIG['account'],
            warehouse=SNOWFLAKE_CONFIG['warehouse'],
            database=SNOWFLAKE_CONFIG['database'],
            schema=SNOWFLAKE_CONFIG['schema'],
            role=SNOWFLAKE_CONFIG['role'],
            timeout=30  # Increase timeout to 30 seconds
        )
        # Test the connection
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        cursor.close()
        return conn
    except Exception as e:
        st.error(f"Error connecting to Keepa Queries Table: {str(e)}")
        return None

def search_items(search_term, item_type):
    """Search for brands or companies in Snowflake"""
    with st.spinner(f'Searching {item_type.lower()}s...'):
        conn = get_snowflake_connection()
        if conn:
            try:
                cursor = conn.cursor()
                if item_type == "Brand Name":
                    # Convert search term to uppercase for matching
                    search_term = search_term.upper()
                    query = """
                    SELECT DISTINCT brand as brand_name
                    FROM boabd.hubspot.company_brand_associations
                    WHERE UPPER(brand) LIKE %s
                    ORDER BY brand_name
                    LIMIT 100
                    """
                    cursor.execute(query, (f'%{search_term}%',))
                    results = [row[0] for row in cursor.fetchall()]
                else:  # Company Name
                    query = """
                    SELECT cmp1.company_id, cmp1.company_name, cmp1.concat_lead_list_name, 
                           cmp2.concat_lead_list_name as concat_lead_list_name_final 
                    FROM boabd.hubspot.company_data cmp1
                    INNER JOIN boabd.hubspot.COMPANY_LEADLISTID_ASSOCIATIONS cmp2
                    ON cmp1.company_id = cmp2.company_id
                    WHERE UPPER(cmp1.company_name) LIKE UPPER(%s)
                    ORDER BY cmp1.company_name
                    LIMIT 100
                    """
                    cursor.execute(query, (f'%{search_term}%',))
                    results = cursor.fetchall()
                cursor.close()
                conn.close()
                return results
            except Exception as e:
                st.error(f"Error searching {item_type.lower()}s: {str(e)}")
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
            # Use ENV_TYPE from config
            table_name = "BOABD.INPUTDATA.ECHO_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.ECHO_QUERIES"
            st.write(f"Debug - Using {table_name} for {x_amazon_type} submission")  # Debug log
        else:
            # For Amazon submissions, use KEEPA_QUERIES table
            query_type = "manufacturer_only" if selection_type == "Company" else "brand"
            query_value = company_data[3] if selection_type == "Company" else brand_name
            # Use ENV_TYPE from config
            table_name = "BOABD.INPUTDATA.KEEPA_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.KEEPA_QUERIES"
            st.write(f"Debug - Using {table_name} for Amazon {selection_type} submission")  # Debug log
        
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
        
        try:
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
            
    except Exception as e:
        st.error(f"Error in database operation: {str(e)}")
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
                else:
                    st.error(f"Company data not found for: {selection_value}")
                    return
            else:  # Brand selection
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
                    st.write(f"Debug - Processing Target brand submission: {selection_value}")  # Debug log
                elif x_amazon_type == "Walmart":
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    request_type = "Walmart Brand"
                    status = "0"
                    is_multiple = "False"  # Set to False for single brand submission
                    url_value = None
                    requestor_email = st.session_state.requestor_email
                    st.write(f"Debug - Processing Walmart brand submission: {selection_value}")  # Debug log
                else:
                    brand_name = selection_value
                    company_name = "NOTSPECIFIEDUNUSED"
                    concat_lead_list_name = "NOTSPECIFIEDUNUSED"
                    # Determine request type based on submission type and X-Amazon type
                    if hasattr(st.session_state, 'submission_type') and st.session_state.submission_type == "Brand Not in HubSpot":
                        request_type = "Amazon Brand Name New"
                    else:
                        request_type = "Amazon Brand Name"
                    status = "0"
                    is_multiple = "False"  # Set to False for single brand submission
                    url_value = None
                    requestor_email = st.session_state.requestor_email

            # Check if selection_value contains semicolons (multiple brands)
            if ";" in selection_value:
                # Split the brands and handle them as multiple submissions
                brands_list = [brand.strip() for brand in selection_value.split(";")]
                st.write(f"Debug - Multiple brands detected: {brands_list}")  # Debug log
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
                st.write(f"Debug - Added to BULLSEYE_REQUEST: {selection_value} with is_multiple={is_multiple}")  # Debug log
            except Exception as e:
                st.error(f"Failed to insert into BULLSEYE_REQUEST: {str(e)}")
                return

            # For company submissions, insert into Keepa Table and update status
            if selection_type == "Company":
                if not company_data:
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

def update_multiple_brands(brands_list, x_amazon_type=None, req_guid=None, request_type=None, is_multiple=None):
    """Handle multiple brand submissions with the same REQ_GUID"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            if not req_guid:
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
            
            # Only set is_multiple if not provided
            if is_multiple is None:
                is_multiple = "TRUE" if len(brands_list) > 1 else "FALSE"
            
            # Debug log
            st.write(f"Debug - update_multiple_brands: is_multiple={is_multiple}, brands_list={brands_list}")
            
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
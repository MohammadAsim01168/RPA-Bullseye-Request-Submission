import streamlit as st
import snowflake.connector
from config import SNOWFLAKE_CONFIG, KEEPA_QUERIES_TABLE, RUN_TYPE
import uuid

# Global requestor variable
REQUESTOR = "RPA Bot"

def get_snowflake_connection():
    """Create and return a Snowflake connection"""
    try:
        conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Error connecting to Snowflake: {str(e)}")
        return None

def get_keepa_connection():
    """Create and return a connection to the Keepa Queries Table"""
    try:
        conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
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
            
            # Get requestor from session state or use global default
            requestor = st.session_state.get('requestor_name', REQUESTOR)
            
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

def update_multiple_brands(brands_list, x_amazon_type):
    """Handle multiple brand submissions with the same REQ_GUID"""
    conn = get_snowflake_connection()
    if conn:
        try:
            cursor = conn.cursor()
            req_guid = str(uuid.uuid4())
            # Get requestor from session state or use global default
            requestor = st.session_state.get('requestor_name', REQUESTOR)
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
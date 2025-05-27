import os
import streamlit as st

# =============================================
# Environment Configuration
# Change this value to switch between environments:
# ENV_TYPE = "Prod"  # For Production
# ENV_TYPE = "Test"  # For Testing
ENV_TYPE = "Test"  # Hardcoded to Test environment
# =============================================

# Table configurations based on environment
KEEPA_QUERIES_TABLE = "BOABD.INPUTDATA.KEEPA_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.KEEPA_QUERIES"
ECHO_QUERIES_TABLE = "BOABD.INPUTDATA.ECHO_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.ECHO_QUERIES"

# Run type configuration - Use same value as ENV_TYPE
RUN_TYPE = ENV_TYPE

# Try to get credentials from Streamlit secrets first (for cloud deployment)
# If not found, fall back to environment variables (for local development)
def get_snowflake_config():
    """Get Snowflake configuration from Streamlit secrets or environment variables"""
    if 'SNOWFLAKE_CONFIG' in st.secrets:
        return st.secrets['SNOWFLAKE_CONFIG']
    
    return {
        'user': os.getenv('RPA_BULLSEYE_SNOWFLAKE_USER'),
        'password': os.getenv('RPA_BULLSEYE_SNOWFLAKE_PASSWORD'),
        'account': os.getenv('RPA_BULLSEYE_SNOWFLAKE_ACCOUNT'),
        'warehouse': os.getenv('RPA_BULLSEYE_SNOWFLAKE_WAREHOUSE'),
        'database': os.getenv('RPA_BULLSEYE_SNOWFLAKE_DATABASE'),
        'schema': os.getenv('RPA_BULLSEYE_SNOWFLAKE_SCHEMA'),
        'role': os.getenv('RPA_BULLSEYE_SNOWFLAKE_ROLE')
    }

# Get the configuration
SNOWFLAKE_CONFIG = get_snowflake_config()

# Keepa Queries Table Snowflake configuration
KEEPA_SNOWFLAKE_CONFIG = {
    'user': os.getenv('RPA_BULLSEYE_SNOWFLAKE_USER'),
    'password': os.getenv('RPA_BULLSEYE_SNOWFLAKE_PASSWORD'),
    'account': os.getenv('RPA_BULLSEYE_SNOWFLAKE_ACCOUNT'),
    'warehouse': os.getenv('RPA_BULLSEYE_SNOWFLAKE_WAREHOUSE'),
    'database': os.getenv('RPA_BULLSEYE_SNOWFLAKE_DATABASE'),
    'schema': os.getenv('RPA_BULLSEYE_SNOWFLAKE_SCHEMA'),
    'role': os.getenv('RPA_BULLSEYE_SNOWFLAKE_ROLE')
}

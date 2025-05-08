import os
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file (for local development)
load_dotenv(override=True)

# Environment configuration
def get_env_type():
    """Get environment type from Streamlit secrets or environment variables"""
    if 'RPA_BULLSEYE_ENV_TYPE' in st.secrets:
        return st.secrets['RPA_BULLSEYE_ENV_TYPE']
    return os.getenv('RPA_BULLSEYE_ENV_TYPE', 'Test')

# Get environment type
ENV_TYPE = get_env_type()

# Table configurations based on environment
KEEPA_QUERIES_TABLE = "BOABD.INPUTDATA.KEEPA_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.KEEPA_QUERIES"
ECHO_QUERIES_TABLE = "BOABD.INPUTDATA.ECHO_QUERIES_DEV" if ENV_TYPE == "Test" else "BOABD.INPUTDATA.ECHO_QUERIES"

# Run type configuration
RUN_TYPE = "Test" if ENV_TYPE == "Test" else "Prod"

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

# Debug information (only in development)
if ENV_TYPE == 'Test':
    print(f"Debug - Environment Type: {ENV_TYPE}")
    print(f"Debug - Using Tables:")
    print(f"- KEEPA_QUERIES_TABLE: {KEEPA_QUERIES_TABLE}")
    print(f"- ECHO_QUERIES_TABLE: {ECHO_QUERIES_TABLE}")
    print("Debug - Environment Variables:")
    print(f"RPA_BULLSEYE_ENV_TYPE: {os.getenv('RPA_BULLSEYE_ENV_TYPE')}")
    print(f"RPA_BULLSEYE_SNOWFLAKE_USER: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_USER')}")
    print("RPA_BULLSEYE_SNOWFLAKE_PASSWORD: [MASKED]")
    print(f"RPA_BULLSEYE_SNOWFLAKE_ACCOUNT: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_ACCOUNT')}")
    print(f"RPA_BULLSEYE_SNOWFLAKE_WAREHOUSE: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_WAREHOUSE')}")
    print(f"RPA_BULLSEYE_SNOWFLAKE_DATABASE: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_DATABASE')}")
    print(f"RPA_BULLSEYE_SNOWFLAKE_SCHEMA: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_SCHEMA')}")
    print(f"RPA_BULLSEYE_SNOWFLAKE_ROLE: {os.getenv('RPA_BULLSEYE_SNOWFLAKE_ROLE')}")

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
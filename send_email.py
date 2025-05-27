import requests
import streamlit as st

def clean_query_value(query_value):
    """
    Clean and format the query value for email notification
    
    Args:
        query_value (str): The raw query value containing brands/companies/URLs
    
    Returns:
        str: Cleaned and formatted query value
    """
    try:
        # Split by retailer separator if present
        if " | " in query_value:
            # Split into retailer sections
            retailer_sections = query_value.split(" | ")
            cleaned_sections = []
            
            for section in retailer_sections:
                if ":" in section:
                    retailer, values = section.split(":", 1)
                    # Clean values (remove extra spaces, handle URLs)
                    values = values.strip()
                    if "http" in values:
                        # For URLs, just keep the domain
                        urls = values.split(", ")
                        cleaned_urls = []
                        for url in urls:
                            if "http" in url:
                                # Extract domain from URL
                                domain = url.split("//")[-1].split("/")[0]
                                cleaned_urls.append(domain)
                            else:
                                cleaned_urls.append(url)
                        values = ", ".join(cleaned_urls)
                    cleaned_sections.append(f"{retailer}: {values}")
                else:
                    cleaned_sections.append(section.strip())
            
            return " | ".join(cleaned_sections)
        else:
            # For single retailer submissions, just clean the values
            if "http" in query_value:
                # Handle URLs
                urls = query_value.split(", ")
                cleaned_urls = []
                for url in urls:
                    if "http" in url:
                        domain = url.split("//")[-1].split("/")[0]
                        cleaned_urls.append(domain)
                    else:
                        cleaned_urls.append(url)
                return ", ".join(cleaned_urls)
            else:
                # For regular brand/company submissions
                return query_value.strip()
    except Exception as e:
        st.warning(f"Error cleaning query value: {str(e)}")
        return query_value

def send_email_notification(query_value, requestor_email):
    """
    Send email notification for brand submissions using Azure Logic App
    
    Args:
        query_value (str): The brand(s) or company being submitted
        requestor_email (str): Email address of the requestor
    """
    try:
        # Clean and format the query value
        cleaned_query = clean_query_value(query_value)
        
        # Apply 250 character limit
        MAX_QUERY_LENGTH = 250
        if len(cleaned_query) > MAX_QUERY_LENGTH:
            original_length = len(cleaned_query)
            cleaned_query = cleaned_query[:MAX_QUERY_LENGTH] + "..."
            st.warning(f"Query value was truncated from {original_length} to {MAX_QUERY_LENGTH} characters")
        
        # Azure Logic App URL
        url = "https://prod-25.westus.logic.azure.com:443/workflows/8374cfcac0a24a5da20079e6d373b7be/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=RD2GsB_9fQFXD1CGJX_UiLUO-nT-0p1nTI7anvclNyg"
        
        # Prepare payload
        payload = {
            "email": requestor_email,
            "query_value": cleaned_query
        }
        
        # Set headers
        headers = {"Content-Type": "application/json"}
        
        # Send request to Azure Logic App
        response = requests.post(url, json=payload, headers=headers)
        
        # Check response - 200 and 202 are both success codes
        if response.status_code in [200, 202]:
            st.success("Email notification sent successfully")
            return True
        else:
            st.error(f"Failed to send email notification. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        st.error(f"Error sending email notification: {str(e)}")
        return False 

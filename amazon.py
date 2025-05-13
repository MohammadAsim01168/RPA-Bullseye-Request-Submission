import streamlit as st
from shared_functions import search_items, update_multiple_brands, update_selection

def show_amazon_section():
    st.title("Amazon Submission")

    # Add a loading spinner while initializing
    with st.spinner('Initializing Amazon application...'):
        # Initialize session state for Amazon search results
        if 'amazon_search_results' not in st.session_state:
            st.session_state.amazon_search_results = None

        # Selection type radio button
        selection_type = st.radio(
            "Select Type:",
            ["Company Name", "Brand Name"],
            key="amazon_selection_type"
        )

        if selection_type == "Company Name":
            # Search box for company selection
            search_term = st.text_input(
                "Search Company:",
                help="Type to search for available companies",
                key="amazon_company_search"
            )
            
            if search_term:
                search_results = search_items(search_term, "Company Name")
                st.session_state.amazon_search_results = search_results
                
                if search_results:
                    # For company search, results are tuples (company_id, company_name, concat_lead_list_name, concat_lead_list_name_final)
                    selected_company = st.selectbox(
                        "Select Company:",
                        options=[row[1] for row in search_results],  # Use company_name from row[1]
                        key="amazon_company_select"
                    )
                    
                    if st.button("Submit Company"):
                        with st.spinner('Submitting company...'):
                            # Verify search results exist and are not None
                            if not st.session_state.amazon_search_results:
                                st.error("Search results not available. Please search for a company first.")
                                return
                            
                            # Find the company data from search results
                            company_data = next((row for row in st.session_state.amazon_search_results if row[1] == selected_company), None)
                            if not company_data:
                                st.error(f"Company data not found for: {selected_company}")
                                return
                                
                            update_selection("Company", selected_company)
                            st.success(f"Successfully submitted company: {selected_company}")
                else:
                    st.info("No companies found.")

        else:  # Brand Name selection
            # Search box for brand selection
            search_term = st.text_input(
                "Search Brand:",
                help="Type to search for available brands",
                key="amazon_brand_search"
            )
            
            if search_term:
                search_results = search_items(search_term, "Brand Name")
                st.session_state.amazon_search_results = search_results
                
                if search_results:
                    # For brand search, results are already just brand names
                    selected_values = st.multiselect(
                        "Select Brand(s):",
                        options=search_results,
                        key="amazon_brand_select"
                    )
                    
                    if st.button("Submit Selected Brands"):
                        with st.spinner('Submitting Amazon brands...'):
                            if selected_values:
                                if len(selected_values) > 1:
                                    update_multiple_brands(selected_values, None)
                                else:
                                    update_selection("Brand", selected_values[0])
                                st.success("Successfully submitted brands to Amazon")
                            else:
                                st.warning("Please select at least one brand.")
                else:
                    st.info("No brands found.")
                    # Enable Brand Not in HubSpot option when no brands are found
                    st.info("For multiple brands, enter them separated by semicolons (e.g., brand1;brand2;brand3)")
                    brand_not_in_hubspot = st.text_input(
                        "Brand Not in HubSpot",
                        help="Enter brand name(s) separated by semicolons for multiple brands",
                        key="amazon_not_in_hubspot"
                    )
                    if brand_not_in_hubspot and st.button("Submit Brand Not in HubSpot"):
                        with st.spinner('Submitting brand(s) not in HubSpot...'):
                            # Set the submission type before processing
                            st.session_state.submission_type = "Brand Not in HubSpot"
                            if ";" in brand_not_in_hubspot:
                                # Split the brands and handle them as multiple submissions
                                brands_list = [brand.strip() for brand in brand_not_in_hubspot.split(";")]
                                update_multiple_brands(brands_list, None)
                            else:
                                update_selection("Brand", brand_not_in_hubspot)
                            st.success("Successfully submitted brand(s) to Amazon")

    # Display Amazon current selection
    if selection_type == "Brand Name" and 'selected_values' in locals() and selected_values:
        # Convert to list if it's a tuple and ensure all items are strings
        display_values = [str(val) for val in selected_values]
        st.info(f"Current Amazon Brand Selection: {', '.join(display_values)}")
    elif selection_type == "Company Name" and 'selected_company' in locals() and selected_company:
        st.info(f"Current Amazon Company Selection: {selected_company}") 
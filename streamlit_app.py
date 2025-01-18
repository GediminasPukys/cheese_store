import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
from urllib.parse import parse_qs

# Page configuration
st.set_page_config(
    page_title="Vieno prancūzo sandėliokas",
    layout="wide",
    initial_sidebar_state="collapsed"  # Start with collapsed sidebar for hamburger menu
)

# Custom CSS for French Provençal style and hamburger menu
st.markdown("""
    <style>
        /* Main theme colors */
        :root {
            --lavender: #E6E6FA;
            --sage: #BCB88A;
            --cream: #FFFDD0;
            --dusty-blue: #B0C4DE;
        }

        /* Typography */
        .main-title {
            font-family: 'Playfair Display', serif;
            color: #2C3E50;
            font-size: 2.5rem;
            text-align: center;
            margin-bottom: 2rem;
        }

        .product-title {
            font-family: 'Lora', serif;
            color: #34495E;
            font-size: 1.8rem;
            margin-bottom: 1rem;
        }

        .product-description {
            font-family: 'Open Sans', sans-serif;
            color: #2C3E50;
            line-height: 1.6;
            background-color: var(--cream);
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid var(--sage);
        }

        /* Navigation */
        .sidebar .sidebar-content {
            background-color: var(--lavender);
            padding: 1rem;
        }

        /* Category headers */
        .category-header {
            font-family: 'Playfair Display', serif;
            color: #34495E;
            font-size: 1.3rem;
            padding: 0.5rem;
            border-radius: 4px;
            margin: 0.5rem 0;
            cursor: pointer;
        }

        /* Product links */
        .product-link {
            padding: 0.5rem 1rem;
            margin-left: 1rem;
            color: #2C3E50;
            text-decoration: none;
            display: block;
            transition: background-color 0.3s;
        }

        .product-link:hover {
            background-color: var(--dusty-blue);
            border-radius: 4px;
        }

        /* Hamburger menu custom styling */
        .stButton button {
            background-color: transparent;
            border: none;
            color: #2C3E50;
            padding: 0.5rem;
            width: 100%;
            text-align: left;
        }

        .stButton button:hover {
            background-color: var(--dusty-blue);
        }

        /* Hide Streamlit default menu button */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)


# Extract spreadsheet ID from URL in secrets
def extract_spreadsheet_id(url):
    pattern = r'/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


# Get query parameters
current_product_id = st.query_params.get("product", None)

# Get spreadsheet URL from secrets
sheet_url = st.secrets["gcs"]["content_doc_address"]
spreadsheet_id = extract_spreadsheet_id(sheet_url)

if not spreadsheet_id:
    st.error("Could not extract spreadsheet ID from the URL in secrets.")
    st.stop()

try:
    # Create credentials from service account info in secrets
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )

    # Initialize Google Sheets API service with credentials
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range='A:D'
    ).execute()

    values = result.get('values', [])

    if not values:
        st.error('No data found in the spreadsheet.')
        st.stop()

    # Convert to DataFrame
    df = pd.DataFrame(values[1:], columns=values[0])

    # Remove empty rows
    df = df.dropna(how='all')

    # Create sidebar navigation with hamburger menu
    st.sidebar.markdown('<h1 class="main-title">Menu</h1>', unsafe_allow_html=True)

    # Group products by category
    categories = df['category'].unique()

    # Create navigation structure with collapsible categories
    for category in sorted(categories):
        # Create expander for each category
        with st.sidebar.expander(category, expanded=False):
            category_products = df[df['category'] == category]

            for _, product in category_products.iterrows():
                if st.button(
                        product['product_name'],
                        key=f"btn_{product['id']}",
                        help=f"View {product['product_name']}"
                ):
                    # Update URL parameters when product is selected
                    st.query_params["product"] = product['id']
                    current_product_id = product['id']

    # Main content area
    st.markdown('<h1 class="main-title">Vieno prancūzo sandėliokas</h1>', unsafe_allow_html=True)

    # Display product content based on URL parameter
    if current_product_id:
        product = df[df['id'] == current_product_id].iloc[0]

        st.markdown(f'<h2 class="product-title">{product["product_name"]}</h2>', unsafe_allow_html=True)
        st.markdown(f'<div class="product-description">{product["description"]}</div>', unsafe_allow_html=True)

        # Display shareable URL
        st.markdown(f"Shareable URL: ?product={current_product_id}")
    else:
        st.markdown("""
            <div class="product-description">
                Welcome to Vieno prancūzo sandėliokas! Please select a product from the menu.
            </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
        <div style="text-align: center; margin-top: 3rem; padding: 1rem; background-color: var(--lavender);">
            <p style="font-family: 'Open Sans', sans-serif; color: #2C3E50;">
                © 2025 Vieno prancūzo sandėliokas
            </p>
        </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
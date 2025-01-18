import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
import qrcode
from PIL import Image
import io
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image as RLImage, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Page configuration
st.set_page_config(
    page_title="Vieno prancūzo sandėliukas",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
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

        /* QR code table */
        .dataframe {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            background-color: var(--cream);
        }

        .dataframe th {
            background-color: var(--dusty-blue);
            color: #2C3E50;
            padding: 0.75rem;
            text-align: left;
        }

        .dataframe td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--sage);
            vertical-align: middle;
        }

        /* Hide Streamlit default menu button */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)


# QR Code generation functions
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    return qr_image, qr.get_matrix()


def create_svg(matrix):
    width = len(matrix) * 10
    height = len(matrix) * 10
    svg = [f'''<?xml version="1.0" encoding="UTF-8"?>
    <svg xmlns="http://www.w3.org/2000/svg" height="{height}" width="{width}">
    <rect width="100%" height="100%" fill="white"/>''']

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                svg.append(
                    f'<rect x="{x * 10}" y="{y * 10}" '
                    f'width="10" height="10" fill="black"/>'
                )

    svg.append('</svg>')
    return '\n'.join(svg)


def create_qr_pdf(df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Product QR Codes", styles['Title']))
    elements.append(Spacer(1, 20))

    # Create table data
    table_data = [["Category", "Product", "QR Code", "URL"]]

    for _, row in df.iterrows():
        if 'url' in row and row['url']:
            # Generate QR code
            qr_image, _ = generate_qr_code(row['url'])

            # Convert PIL image to reportlab image
            img_buffer = io.BytesIO()
            qr_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            qr = RLImage(img_buffer, width=60, height=60)

            table_data.append([
                row['category'],
                row['product_name'],
                qr,
                row['url']
            ])

    # Create and style the table
    table = Table(table_data, colWidths=[100, 150, 70, 180])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# Extract spreadsheet ID from URL in secrets
def extract_spreadsheet_id(url):
    pattern = r'/d/([a-zA-Z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None


# Create tabs
tab1, tab2 = st.tabs(["Products", "QR Codes"])

# Get spreadsheet URL from secrets
sheet_url = st.secrets["gcs"]["content_doc_address"]
spreadsheet_id = extract_spreadsheet_id(sheet_url)

if not spreadsheet_id:
    st.error("Could not extract spreadsheet ID from the URL in secrets.")
    st.stop()

try:
    # Initialize Google Sheets API with service account
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)

    # Get spreadsheet data
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range='A:F'
    ).execute()

    values = result.get('values', [])
    if not values:
        st.error('No data found in the spreadsheet.')
        st.stop()

    # Convert to DataFrame
    df = pd.DataFrame(values[1:], columns=values[0])
    df = df.dropna(how='all')

    with tab1:
        # Products tab content
        st.markdown('<h1 class="main-title">Vieno prancūzo sandėliukas</h1>', unsafe_allow_html=True)

        # Create navigation structure with collapsible categories
        for category in sorted(df['category'].unique()):
            with st.sidebar.expander(category, expanded=False):
                category_products = df[df['category'] == category]
                for _, product in category_products.iterrows():
                    if st.button(
                            product['product_name'],
                            key=f"btn_{product['id']}",
                            help=f"View {product['product_name']}"
                    ):
                        st.query_params["product"] = product['id']

        # Display product content based on URL parameter
        current_product_id = st.query_params.get("product", None)
        if current_product_id:
            product = df[df['id'] == current_product_id].iloc[0]
            st.markdown(f'<h2 class="product-title">{product["product_name"]}</h2>', unsafe_allow_html=True)
            st.markdown(f'<div class="product-description">{product["description"]}</div>', unsafe_allow_html=True)
            st.markdown(f"Shareable URL: ?product={current_product_id}")
        else:
            st.markdown("""
                <div class="product-description">
                    Welcome to Vieno prancūzo sandėliukas! Please select a product from the menu.
                </div>
            """, unsafe_allow_html=True)

    with tab2:
        st.markdown('<h1 class="main-title">QR Codes for Products</h1>', unsafe_allow_html=True)

        # PDF download button
        pdf_data = create_qr_pdf(df)
        st.download_button(
            label="Download All QR Codes (PDF)",
            data=pdf_data,
            file_name="product_qr_codes.pdf",
            mime="application/pdf",
        )

        # Create DataFrame display with QR codes
        data_for_table = []
        for _, row in df.iterrows():
            if 'url' in row and row['url']:
                # Generate QR code
                qr_image, qr_matrix = generate_qr_code(row['url'])

                # Convert to SVG for download
                svg_content = create_svg(qr_matrix)

                # Convert QR image to base64 for display
                img_buffer = io.BytesIO()
                qr_image.save(img_buffer, format='PNG')
                img_str = base64.b64encode(img_buffer.getvalue()).decode()

                # Create download button for SVG
                download_button = st.download_button(
                    label="SVG",
                    data=svg_content,
                    file_name=f"qr_{row['id']}.svg",
                    mime="image/svg+xml",
                    key=f"qr_{row['id']}"
                )

                data_for_table.append({
                    "Category": row['category'],
                    "Product": row['product_name'],
                    "QR Code": f'<img src="data:image/png;base64,{img_str}" width="100">',
                    "URL": f'<a href="{row["url"]}" target="_blank">{row["url"]}</a>',
                    "Download": download_button
                })

        # Convert to DataFrame for display
        if data_for_table:
            df_display = pd.DataFrame(data_for_table)
            st.write(df_display.to_html(escape=False), unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
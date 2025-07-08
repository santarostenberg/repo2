import streamlit as st
import requests
import io
import PyPDF2
import openai
from bs4 import BeautifulSoup

# Set OpenAI key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- Fetch NICE guidance PDF by scraping the page ---
def fetch_pdf_via_scraping(code):
    base_url = f"https://www.nice.org.uk/guidance/{code}"
    try:
        resp = requests.get(base_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find link with exact PDF guidance
        link = soup.find("a", string=lambda text: text and "Download guidance (PDF)" in text)

        if not link:
            return None

        href = link.get("href")
        if href.startswith("/"):
            href = "https://www.nice.org.uk" + href

        pdf_resp = requests.get(href)
        pdf_resp.raise_for_status()

        if 'application/pdf' not in pdf_resp.headers.get('Content-Type', ''):
            return None

        return io.BytesIO(pdf_resp.content)

    except Exception as e:
        st.error(f"Error fetching PDF: {str(e)}")
        return None

# --- Extract text and summarize using OpenAI ---
def summarize_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    truncated_text = text[:10_000]

    prompt = (
        "You are a healthcare policy expert. Summarise and analyse the following NICE guidance document:\n\n"
        + truncated_text
    )

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a healthcare policy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

# --- Extract NICE code from full URL or direct input ---
def extract_code(input_text):
    input_text = input_text.strip().lower()
    if input_text.startswith("http"):
        return input_text.rstrip("/").split("/")[-1]
    return input_text

# --- Streamlit UI ---
st.title("NICE Guidance Summarizer")

user_input = st.text_input("Enter NICE guidance code or full URL")

if st.button("Analyze"):
    if not user_input:
        st.error("Please enter a guidance code or URL.")
    else:
        code = extract_code(user_input)
        st.write(f"Processing guidance code: `{code}`")

        pdf_file = fetch_pdf_via_scraping(code)
        if pdf_file:
            with st.spinner("Extracting and summarizing..."):
                summary = summarize_pdf(pdf_file)
            st.subheader("Summary Result")
            st.write(summary)
        else:
            st.error(f"Could not fetch PDF for code '{code}'.")

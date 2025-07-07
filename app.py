import streamlit as st
import requests
import io
import PyPDF2
import openai

# Set your OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

def fetch_pdf(code):
    # List of possible PDF URL patterns to try
    urls = [
        f"https://www.nice.org.uk/guidance/{code}/download-pdf",
        f"https://www.nice.org.uk/guidance/{code}/pdf",
        f"https://www.nice.org.uk/guidance/{code}/resources/{code}-pdf",
        # Add other URL patterns you find from inspecting the page
    ]
    for url in urls:
        try:
            r = requests.get(url)
            if r.status_code == 200 and 'application/pdf' in r.headers.get('Content-Type', ''):
                return io.BytesIO(r.content)
        except Exception:
            pass
    return None

def summarize_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    truncated_text = text[:10000]

    prompt = (
        "You are a healthcare policy expert. Summarise and analyse the following NICE guidance document:\n\n"
        + truncated_text
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a healthcare policy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

def extract_code(input_text):
    input_text = input_text.strip().lower()
    # If input looks like a URL, extract the last path segment as code
    if input_text.startswith("http"):
        return input_text.rstrip("/").split("/")[-1]
    return input_text

st.title("NICE Guidance Summarizer")

user_input = st.text_input("Enter NICE guidance code or full URL")

if st.button("Analyze"):
    if not user_input:
        st.error("Please enter a guidance code or URL.")
    else:
        code = extract_code(user_input)
        st.write(f"Processing guidance code: {code}")

        pdf_file = fetch_pdf(code)
        if pdf_file:
            summary = summarize_pdf(pdf_file)
            st.subheader("Summary Result")
            st.write(summary)
        else:
            st.error(f"Could not fetch PDF for code '{code}'. Tried multiple URL patterns.")


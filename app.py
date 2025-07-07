import streamlit as st
import requests
from bs4 import BeautifulSoup
import io
import PyPDF2
import openai
import os

# Set your OpenAI API key here or as environment variable OPENAI_API_KEY
openai.api_key = os.getenv("OPENAI_API_KEY", "your_openai_api_key_here")

def get_pdf_text(code):
    base_url = f"https://www.nice.org.uk/guidance/{code}"
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    pdf_link = soup.find('a', string="Download guidance (PDF)")
    if not pdf_link:
        raise Exception("Could not find PDF download link for this code.")
    pdf_url = pdf_link['href']
    if not pdf_url.startswith("http"):
        pdf_url = "https://www.nice.org.uk" + pdf_url
    pdf_resp = requests.get(pdf_url)
    pdf_resp.raise_for_status()
    pdf_file = io.BytesIO(pdf_resp.content)
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text[:10000]

def summarize_text(text):
    prompt = (
        "You are a healthcare policy expert. Summarize the following NICE guidance document:\n\n" + text
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

def main():
    st.title("NICE Guidance Summarizer")
    code = st.text_input("Enter NICE guidance code (e.g., ta1044):")
    if st.button("Summarize"):
        if not code:
            st.error("Please enter a NICE guidance code.")
            return
        try:
            with st.spinner("Downloading and reading PDF..."):
                pdf_text = get_pdf_text(code.strip())
            with st.spinner("Generating summary..."):
                summary = summarize_text(pdf_text)
            st.subheader(f"Summary of guidance {code.upper()}:")
            st.write(summary)
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()

import streamlit as st
import requests
import io
import PyPDF2
import openai
import re

openai.api_key = st.secrets["OPENAI_API_KEY"]

def extract_code(user_input):
    # Extract guidance code like ta1044, msac123, etc.
    user_input = user_input.strip().lower()
    # If input is a URL, extract the last path segment
    match = re.search(r'nice\.org\.uk/guidance/([a-z0-9]+)', user_input)
    if match:
        return match.group(1)
    else:
        return user_input  # assume direct code

def get_pdf_text(code):
    pdf_url = f"https://www.nice.org.uk/guidance/{code}/download-pdf"
    resp = requests.get(pdf_url)
    if resp.status_code != 200:
        raise ValueError(f"Could not fetch PDF for code '{code}'. Status: {resp.status_code}")
    pdf_file = io.BytesIO(resp.content)
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text[:10000]  # limit to first 10k chars

def summarize_text(text):
    prompt = f"You are a healthcare policy expert. Summarise and analyse the following NICE guidance document:\n\n{text}"
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
    user_input = st.text_input("Enter NICE guidance code or full URL", "")
    if st.button("Summarize"):
        if not user_input.strip():
            st.error("Please enter a guidance code or URL.")
            return
        try:
            code = extract_code(user_input)
            st.info(f"Processing guidance code: **{code}**")
            pdf_text = get_pdf_text(code)
            summary = summarize_text(pdf_text)
            st.subheader("Summary:")
            st.write(summary)
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()

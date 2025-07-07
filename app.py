import streamlit as st
import requests
import PyPDF2
import io
import openai
import os

# Set your OpenAI API key in environment variable before running this
openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_nice_guidance(code):
    pdf_url = f"https://www.nice.org.uk/guidance/{code}/download-pdf"
    r = requests.get(pdf_url)
    r.raise_for_status()
    pdf_file = io.BytesIO(r.content)

    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    prompt = "You are a healthcare policy expert. Summarise the following NICE guidance:\n\n" + text[:10000]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a healthcare policy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )

    return response.choices[0].message.content

st.title("NICE Guidance Summarizer")

code = st.text_input("Enter NICE guidance code (e.g., ta1044):")

if st.button("Summarize"):
    with st.spinner("Summarizing..."):
        try:
            summary = summarize_nice_guidance(code)
            st.write(summary)
        except Exception as e:
            st.error(f"Error: {str(e)}")

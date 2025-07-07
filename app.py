import streamlit as st
import requests
import io
import PyPDF2
import openai
from bs4 import BeautifulSoup

openai.api_key = st.secrets["OPENAI_API_KEY"]

def extract_text_from_pdf(pdf_bytes):
    reader = PyPDF2.PdfReader(pdf_bytes)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text[:10000]

def summarize_text(text):
    prompt = (
        "You are a healthcare policy expert. Summarise and analyse the following guidance document:\n\n"
        + text
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

def fetch_nice_pdf(code):
    urls = [
        f"https://www.nice.org.uk/guidance/{code}/download-pdf",
        f"https://www.nice.org.uk/guidance/{code}/pdf",
    ]
    for url in urls:
        try:
            r = requests.get(url)
            if r.status_code == 200 and 'application/pdf' in r.headers.get('Content-Type', ''):
                return io.BytesIO(r.content)
        except:
            pass
    return None

def fetch_gba_pdfs(url):
    base_url = "https://www.g-ba.de"
    try:
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        pdf_links = []
        # Find links for Resolution and Justification PDFs
        for a_tag in soup.select("a.download-helper"):
            href = a_tag.get("href", "")
            if "Resolution" in a_tag.text or "Justification" in a_tag.text or "Resolution" in href or "Justification" in href:
                pdf_links.append(base_url + href if href.startswith("/") else href)
        # If above doesn't work well, fallback: gather first 2 pdfs in downloads section
        if not pdf_links:
            downloads = soup.select("ul.gba-download-list li div.gba-download--big a.download-helper")
            for a in downloads[:2]:
                href = a.get("href")
                if href:
                    pdf_links.append(base_url + href if href.startswith("/") else href)
        pdf_contents = []
        for link in pdf_links:
            r = requests.get(link)
            if r.status_code == 200 and 'application/pdf' in r.headers.get('Content-Type', ''):
                pdf_contents.append(io.BytesIO(r.content))
        return pdf_contents
    except Exception as e:
        st.error(f"Failed to fetch PDFs from G-BA site: {e}")
        return []

def main():
    st.title("NICE & G-BA Guidance Summarizer")

    user_input = st.text_input("Enter NICE or G-BA guidance code or full URL")

    if st.button("Analyze"):
        if not user_input:
            st.error("Please enter a guidance code or URL.")
            return

        input_lower = user_input.strip().lower()

        # Detect NICE or G-BA
        if "nice.org.uk" in input_lower:
            # Extract NICE code from URL or accept code directly
            code = input_lower.rstrip("/").split("/")[-1]
            st.write(f"Processing NICE guidance code: {code}")
            pdf_file = fetch_nice_pdf(code)
            if pdf_file:
                text = extract_text_from_pdf(pdf_file)
                summary = summarize_text(text)
                st.subheader("Summary Result")
                st.write(summary)
            else:
                st.error(f"Could not fetch PDF for NICE code '{code}'.")
        elif "g-ba.de" in input_lower:
            st.write(f"Processing G-BA guidance URL: {user_input}")
            pdf_files = fetch_gba_pdfs(user_input)
            if pdf_files:
                combined_text = ""
                for pdf in pdf_files:
                    combined_text += extract_text_from_pdf(pdf) + "\n\n"
                summary = summarize_text(combined_text)
                st.subheader("Summary Result")
                st.write(summary)
            else:
                st.error("Could not fetch PDFs from G-BA site.")
        else:
            st.error("Input does not appear to be a valid NICE or G-BA guidance URL or code.")

if __name__ == "__main__":
    main()

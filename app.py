import streamlit as st
import requests
import io
import PyPDF2
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Initialize OpenAI client
client = openai.OpenAI()

# Set your API key via Streamlit secrets or environment variable
openai.api_key = st.secrets.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

def fetch_pdf_from_uk(code):
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

def fetch_pdfs_from_de(url):
    """For German site, scrape the page and fetch 'Resolution' and 'Justification' PDFs"""
    try:
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        pdf_links = []
        for a in soup.select("a.download-helper"):
            href = a.get('href', '')
            if href.endswith(".pdf"):
                full_url = requests.compat.urljoin(url, href)
                pdf_links.append(full_url)

        # Download PDFs and return list of BytesIO
        pdf_files = []
        for pdf_url in pdf_links:
            resp = requests.get(pdf_url)
            if resp.status_code == 200:
                pdf_files.append(io.BytesIO(resp.content))
        return pdf_files
    except Exception as e:
        st.error(f"Error fetching German PDFs: {str(e)}")
        return []

def extract_text_from_pdfs(pdf_files):
    full_text = ""
    for pdf_file in pdf_files:
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                full_text += page.extract_text() or ""
        except:
            continue
    return full_text[:10000]  # Truncate to first 10,000 chars

def summarize_text(text):
    prompt = (
        "You are a healthcare policy expert. Summarise and analyse the following guidance document:\n\n"
        + text
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a healthcare policy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

def extract_code_or_url(input_text):
    input_text = input_text.strip().lower()
    if input_text.startswith("http"):
        return input_text
    else:
        return input_text

def main():
    st.title("NICE/G-BA Guidance Summarizer")

    user_input = st.text_input("Enter NICE guidance code, or full UK/German guidance URL:")

    if st.button("Analyze"):
        if not user_input:
            st.error("Please enter a guidance code or URL.")
            return

        input_value = extract_code_or_url(user_input)

        if input_value.startswith("http"):
            parsed = urlparse(input_value)
            domain = parsed.netloc.lower()

            if "nice.org.uk" in domain:
                # UK site: extract last part as code
                code = parsed.path.strip("/").split("/")[-1]
                st.write(f"Detected UK NICE code: {code}")
                pdf_file = fetch_pdf_from_uk(code)
                if not pdf_file:
                    st.error(f"Could not fetch PDF for code '{code}' from NICE UK.")
                    return
                text = extract_text_from_pdfs([pdf_file])

            elif "g-ba.de" in domain:
                # German site
                st.write("Detected German G-BA site")
                pdf_files = fetch_pdfs_from_de(input_value)
                if not pdf_files:
                    st.error("Could not fetch PDFs from German site.")
                    return
                text = extract_text_from_pdfs(pdf_files)

            else:
                st.error("Unsupported URL domain. Please enter a UK NICE code or URL, or a German G-BA URL.")
                return
        else:
            # Assume UK code
            code = input_value
            st.write(f"Assuming UK NICE code: {code}")
            pdf_file = fetch_pdf_from_uk(code)
            if not pdf_file:
                st.error(f"Could not fetch PDF for code '{code}' from NICE UK.")
                return
            text = extract_text_from_pdfs([pdf_file])

        if not text.strip():
            st.error("Failed to extract text from PDF(s).")
            return

        st.info("Summarizing the guidance document...")
        summary = summarize_text(text)
        st.subheader("Summary Result")
        st.write(summary)

if __name__ == "__main__":
    main()

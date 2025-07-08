import streamlit as st
import requests
import io
import PyPDF2
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Initialize OpenAI client
client = openai.OpenAI()

# Set your API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- NICE UK PDF fetcher ---
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

# --- G-BA German PDF fetcher ---
def fetch_pdfs_from_de(url):
    try:
        url = url.split('#')[0]
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        pdf_links = []
        for a in soup.find_all("a", class_="download-helper"):
            href = a.get("href", "")
            filename = href.split("/")[-1].lower()
            if href.endswith(".pdf") and (
                "resolution" in filename or "justification" in filename or "rl-xii" in filename
            ):
                full_url = requests.compat.urljoin(url, href)
                pdf_links.append(full_url)

        if not pdf_links:
            st.warning("No relevant German PDFs found.")
        else:
            for i, link in enumerate(pdf_links, 1):
                st.markdown(f"{i}. [Download PDF]({link})")

        pdf_files = []
        for pdf_url in pdf_links:
            resp = requests.get(pdf_url)
            if resp.status_code == 200:
                pdf_files.append(io.BytesIO(resp.content))

        return pdf_files
    except Exception as e:
        st.error(f"Error fetching German PDFs: {str(e)}")
        return []

# --- HAS France PDF fetcher ---
def fetch_pdfs_from_fr(url):
    try:
        from urllib.parse import urljoin
        import time

        url = url.split("#")[0]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        pdf_links = []
        for a in soup.find_all("a", href=True):
            if a["href"].endswith(".pdf"):
                full_url = urljoin(url, a["href"])
                pdf_links.append(full_url)

        if not pdf_links:
            st.warning("No PDFs found on the HAS page.")
            return []

        st.markdown("### PDFs found on the HAS page:")
        for i, link in enumerate(pdf_links, 1):
            st.markdown(f"{i}. [Download PDF]({link})")

        pdf_files = []
        for pdf_url in pdf_links:
            try:
                resp = requests.get(pdf_url, headers=headers, timeout=15)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/pdf"):
                    pdf_files.append(io.BytesIO(resp.content))
                else:
                    st.warning(f"Failed to fetch: {pdf_url} (status {resp.status_code})")
            except Exception as e:
                st.warning(f"Download failed: {pdf_url}\nReason: {e}")
                time.sleep(1)  # be nice to HAS servers

        return pdf_files
    except Exception as e:
        st.error(f"General error fetching from HAS: {str(e)}")
        return []



# --- PDF text extractor ---
def extract_text_from_pdfs(pdf_files):
    full_text = ""
    success_count = 0
    for pdf_file in pdf_files:
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                full_text += page.extract_text() or ""
            success_count += 1
        except Exception as e:
            st.warning(f"Failed to parse a PDF: {e}")
    st.info(f"Parsed {success_count}/{len(pdf_files)} PDFs.")
    return full_text[:10_000]  # Truncate

# --- GPT-4 summarizer ---
def summarize_text(text):
    prompt = (
        "You are a healthcare policy expert. The following documents are from a French government healthcare site. "
        "If any English summary is included, focus on that. Otherwise, attempt to summarise key content in English:\n\n"
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

# --- Input handler ---
def extract_code_or_url(input_text):
    return input_text.strip().lower()

# --- Streamlit UI ---
def main():
    st.title("NICE / G-BA / HAS Guidance Summarizer")

    user_input = st.text_input("Enter NICE guidance code, or full UK/German/French guidance URL:")

    if st.button("Analyze"):
        if not user_input:
            st.error("Please enter a guidance code or URL.")
            return

        input_value = extract_code_or_url(user_input)

        if input_value.startswith("http"):
            parsed = urlparse(input_value)
            domain = parsed.netloc.lower()

            if "nice.org.uk" in domain:
                code = parsed.path.strip("/").split("/")[-1]
                st.write(f"Detected UK NICE code: `{code}`")
                pdf_file = fetch_pdf_from_uk(code)
                if not pdf_file:
                    st.error("Could not fetch PDF from NICE UK.")
                    return
                text = extract_text_from_pdfs([pdf_file])

            elif "g-ba.de" in domain:
                st.write("Detected German G-BA site")
                pdf_files = fetch_pdfs_from_de(input_value)
                if not pdf_files:
                    st.error("Could not fetch PDFs from G-BA.")
                    return
                text = extract_text_from_pdfs(pdf_files)

            elif "has-sante.fr" in domain:
                st.write("Detected French HAS site")
                pdf_files = fetch_pdfs_from_fr(input_value)
                if not pdf_files:
                    st.error("Could not fetch PDFs from HAS.")
                    return
                text = extract_text_from_pdfs(pdf_files)

            else:
                st.error("Unsupported domain. Please use NICE, G-BA or HAS links.")
                return

        else:
            code = input_value
            st.write(f"Assuming UK NICE code: `{code}`")
            pdf_file = fetch_pdf_from_uk(code)
            if not pdf_file:
                st.error(f"Could not fetch PDF for code '{code}' from NICE UK.")
                return
            text = extract_text_from_pdfs([pdf_file])

        if not text.strip():
            st.error("Failed to extract any text from the document.")
            return

        with st.spinner("Summarizing with GPT-4..."):
            summary = summarize_text(text)

        st.subheader("Summary Result")
        st.write(summary)

if __name__ == "__main__":
    main()

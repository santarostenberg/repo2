import streamlit as st
import requests
import io
import PyPDF2
import openai
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- NICE UK PDF fetcher ---
def fetch_pdf_from_nice(code):
    base_url = f"https://www.nice.org.uk/guidance/{code}"
    try:
        resp = requests.get(base_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("a", string=lambda t: t and "Download guidance (PDF)" in t)
        if not link:
            return None
        href = link.get("href")
        if href.startswith("/"):
            href = "https://www.nice.org.uk" + href
        pdf_resp = requests.get(href)
        pdf_resp.raise_for_status()
        if "application/pdf" not in pdf_resp.headers.get("Content-Type", ""):
            return None
        return io.BytesIO(pdf_resp.content)
    except Exception as e:
        st.error(f"Error fetching NICE PDF: {str(e)}")
        return None

# --- G-BA Germany PDF fetcher ---
def fetch_pdfs_from_gba(url):
    try:
        url = url.split("#")[0]
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        pdf_links = []
        for a in soup.find_all("a", class_="download-helper", href=True):
            href = a["href"]
            filename = href.split("/")[-1].lower()
            if (
                href.endswith(".pdf")
                and ("resolution" in filename or "justification" in filename or "rl-xii" in filename)
            ):
                full_url = urljoin(url, href)
                pdf_links.append(full_url)

        st.markdown("### G-BA PDFs found:")
        for i, link in enumerate(pdf_links, 1):
            st.markdown(f"{i}. [Download PDF]({link})")

        pdf_files = []
        for pdf_url in pdf_links:
            r = requests.get(pdf_url)
            if r.status_code == 200:
                pdf_files.append(io.BytesIO(r.content))

        return pdf_files
    except Exception as e:
        st.error(f"Error fetching G-BA PDFs: {e}")
        return []

# --- HAS France PDF fetcher ---
def fetch_pdfs_from_has(url):
    import requests
    import io
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    import streamlit as st

    headers = {"User-Agent": "Mozilla/5.0"}
    valid_pdfs = []
    skipped_links = []

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        all_links = soup.find_all("a", href=True)


# --- Extract text from PDF(s) ---
def extract_text_from_pdfs(pdf_files):
    full_text = ""
    for pdf_file in pdf_files:
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                full_text += page.extract_text() or ""
        except Exception as e:
            st.warning(f"Error reading PDF: {e}")
    return full_text[:10_000]

# --- GPT-4 summarizer ---
def summarize_text(text, source_label="guidance"):
    prompt = f"You are a healthcare policy expert. Summarise and analyse the following {source_label} document(s):\n\n{text}"
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a healthcare policy expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

# --- Streamlit app ---
st.title("NICE, G-BA & HAS Healthcare Guidance Summarizer")

user_input = st.text_input("Enter NICE code, or full NICE / G-BA / HAS URL")

if st.button("Analyze"):
    if not user_input:
        st.error("Please enter a guidance code or URL.")
    else:
        input_val = user_input.strip().lower()
        text = ""

        if input_val.startswith("http"):
            domain = urlparse(input_val).netloc
            if "g-ba.de" in domain:
                st.write("Detected G-BA (Germany) guidance link.")
                pdf_files = fetch_pdfs_from_gba(input_val)
                if not pdf_files:
                    st.error("No valid PDFs found.")
                else:
                    text = extract_text_from_pdfs(pdf_files)

            elif "nice.org.uk" in domain:
                code = input_val.rstrip("/").split("/")[-1]
                st.write(f"Detected NICE code: `{code}`")
                pdf_file = fetch_pdf_from_nice(code)
                if not pdf_file:
                    st.error("Could not fetch PDF.")
                else:
                    text = extract_text_from_pdfs([pdf_file])

            elif "has-sante.fr" in domain:
                st.write("Detected HAS (France) guidance link.")
                pdf_files = fetch_pdfs_from_has(input_val)
                if not pdf_files:
                    st.error("No valid PDFs found.")
                else:
                    text = extract_text_from_pdfs(pdf_files)

            else:
                st.error("Unsupported domain. Only NICE, G-BA, and HAS are supported.")
        else:
            code = input_val
            st.write(f"Assuming NICE code: `{code}`")
            pdf_file = fetch_pdf_from_nice(code)
            if not pdf_file:
                st.error("Could not fetch PDF.")
            else:
                text = extract_text_from_pdfs([pdf_file])

        if not text:
            st.error("Failed to extract any text.")
        else:
            with st.spinner("Summarizing..."):
                summary = summarize_text(text)
            st.subheader("Summary")
            st.write(summary)

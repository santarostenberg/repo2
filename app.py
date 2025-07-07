import streamlit as st
import os
import time
import PyPDF2
import openai
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Set OpenAI key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def analyze_guidance(code):
    url = f"https://www.nice.org.uk/guidance/{code}"

    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(DOWNLOAD_DIR),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    })
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")

    chrome_binary_path = "/usr/bin/chromium-browser"
    if os.path.exists(chrome_binary_path):
        chrome_options.binary_location = chrome_binary_path

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(url)

    try:
        driver.execute_script("""
            var panel = document.getElementById('cc-panel');
            if (panel) panel.style.display = 'none';
            var content = document.getElementById('ccc-content');
            if (content) content.style.display = 'none';
        """)
    except:
        pass

    wait = WebDriverWait(driver, 10)
    button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Download guidance (PDF)")))
    driver.execute_script("arguments[0].click();", button)

    timeout = 15
    downloaded_file = None
    for _ in range(timeout):
        for f in os.listdir(DOWNLOAD_DIR):
            if f.endswith(".pdf"):
                downloaded_file = os.path.join(DOWNLOAD_DIR, f)
                break
        if downloaded_file:
            break
        time.sleep(1)

    driver.quit()

    if not downloaded_file:
        return "PDF download failed."

    with open(downloaded_file, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()

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


# Streamlit UI

st.title("NICE Guidance Summarizer")

guidance_code = st.text_input("Enter NICE guidance code or URL (e.g., ta1044):")

if st.button("Analyze"):
    if guidance_code:
        with st.spinner("Downloading and analyzing guidance..."):
            # Extract code if user entered full URL
            code = guidance_code.strip().split("/")[-1]
            try:
                summary = analyze_guidance(code)
                st.subheader("Summary:")
                st.write(summary)
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.error("Please enter a guidance code or URL.")

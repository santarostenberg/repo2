from flask import Flask, request, render_template
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

app = Flask(__name__)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Use environment variable for OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

def analyze_guidance(code):
    url = f"https://www.nice.org.uk/guidance/{code}"

    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
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

    # Specify chromium binary location (adjust if different)
    chrome_binary_path = "/usr/bin/chromium-browser"  # or "/usr/bin/chromium"
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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    url_input = request.form.get("guidance")
    code = url_input.strip().split("/")[-1]  # Extracts 'ta1044' from full URL

    try:
        summary = analyze_guidance(code)
    except Exception as e:
        summary = f"Error: {str(e)}"

    return render_template("result.html", summary=summary, code=code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

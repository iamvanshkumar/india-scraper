import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import json
import urllib.parse
import re
import requests
from pathlib import Path
from datetime import datetime
import os

# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
st.set_page_config(page_title="Companies House India Scraper", layout="wide")
st.title("Companies House India Scraper (Last 5 Filings)")
st.markdown("**Searches `india` → Overview + Officers + Last 5 Filings + PDF Download**")

st.sidebar.header("Settings")
max_pages = st.sidebar.slider("Max pages to scan (0 = no limit)", 0, 200, 0)
delay_min = st.sidebar.slider("Min delay between search pages (s)", 1, 5, 2)
delay_max = st.sidebar.slider("Max delay between search pages (s)", 2, 10, 4)
profile_delay = st.sidebar.slider("Delay between company pages (s)", 2, 8, 4)
download_pdfs = st.sidebar.checkbox("Download PDFs (last 5 filings)", value=True)

# ----------------------------------------------------------------------
# DRIVER SETUP – Docker Ready
# ----------------------------------------------------------------------
def start_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install(), log_path="/tmp/chromedriver.log")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver, WebDriverWait(driver, 30)

# ----------------------------------------------------------------------
# PDF DOWNLOADER
# ----------------------------------------------------------------------
def download_pdf(pdf_url: str, dest_path: Path) -> str:
    try:
        st.write(f"📥 Downloading to: {dest_path}")
        resp = requests.get(pdf_url, timeout=90, stream=True)
        resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(resp.content)
        st.write(f"✅ Saved: {dest_path.name} ({len(resp.content)} bytes)")
        return "OK"
    except Exception as e:
        st.error(f"❌ PDF download failed: {e}")
        return f"Failed: {e}"

# ----------------------------------------------------------------------
# MAIN SCRAPING
# ----------------------------------------------------------------------
if st.sidebar.button("Start Scraping"):
    with st.spinner("Starting Chrome…"):
        base_url = "https://find-and-update.company-information.service.gov.uk"
        filings_dir = Path("filings")
        filings_dir.mkdir(exist_ok=True)
        st.info(f"📁 Filings directory: {filings_dir.resolve()}")
        st.info(f"🔐 Directory writable: {os.access(filings_dir, os.W_OK)}")

        driver, wait = start_driver()
        st.success("Chrome started!")

        def rand_sleep():
            time.sleep(random.uniform(delay_min, delay_max))

        # ------------------ SEARCH COMPANIES ------------------
        search_query = "india"
        st.info(f"Searching: **{search_query}**")
        page = 1
        company_links = []

        while True:
            url = f"{base_url}/search/companies?q={urllib.parse.quote(search_query)}&page={page}"
            st.info(f"Page {page}")

            driver.get(url)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul#results")))
            except TimeoutException:
                st.warning("No results or timeout")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.select("ul#results > li")
            if not items:
                st.info("No more results")
                break

            for li in items:
                a = li.select_one("h3 a")
                if not a:
                    continue
                href = a["href"]
                name = a.get_text(strip=True)
                num = href.split("/")[-1]
                addr_p = li.select_one("p:nth-of-type(2)")
                address = addr_p.get_text(strip=True) if addr_p else ""
                company_links.append({"Company Name": name, "Company Number": num, "Address": address})

            st.success(f"Page {page}: +{len(items)} companies")
            rand_sleep()

            if max_pages and page >= max_pages:
                break
            page += 1

        driver.quit()
        if not company_links:
            st.error("No companies found")
            st.stop()

        st.success(f"Found **{len(company_links)}** companies")

        # ------------------ DEEP SCRAPE ------------------
        driver, wait = start_driver()
        progress = st.progress(0)

        results = []
        for idx, c in enumerate(company_links):
            num = c["Company Number"]
            name = c["Company Name"]
            st.info(f"[{idx+1}/{len(company_links)}] {name}")

            row = {
                "Company Name": name,
                "Company Number": num,
                "Address (Search)": c["Address"],
                "Registered Office": "",
                "Company Status": "",
                "Company Type": "",
                "Incorporation Date": "",
                "People": [],
                "Filing History": []
            }

            try:
                # Overview
                driver.get(f"{base_url}/company/{num}")
                time.sleep(profile_delay)
                soup = BeautifulSoup(driver.page_source, "html.parser")

                def get_text(selector):
                    el = soup.select_one(selector)
                    return el.get_text(strip=True) if el else "N/A"

                row["Registered Office"] = " | ".join([s.get_text(strip=True) for s in soup.select("#company-address span")]) or "N/A"
                row["Company Status"] = get_text("dt:-soup-contains('Company status') + dd")
                row["Company Type"] = get_text("dt:-soup-contains('Company type') + dd")
                row["Incorporation Date"] = get_text("dt:-soup-contains('Incorporated on') + dd")

                # Officers
                driver.get(f"{base_url}/company/{num}/officers")
                time.sleep(profile_delay)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                officers = []
                for app in soup.select("div[class^='appointment-']"):
                    name_tag = app.select_one("h2 a")
                    name = name_tag.get_text(strip=True) if name_tag else "N/A"
                    officers.append({"Name": name})
                row["People"] = officers

                # Last 5 Filings + PDFs
                driver.get(f"{base_url}/company/{num}/filing-history")
                time.sleep(profile_delay)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                rows = soup.select("#fhTable tbody tr")[:5]
                filings = []
                company_folder = filings_dir / num
                company_folder.mkdir(exist_ok=True)

                for tr in rows:
                    cols = tr.find_all("td")
                    if len(cols) < 4:
                        continue
                    date_td, type_td, desc_td, link_td = cols
                    filing = {
                        "Date": date_td.get_text(strip=True),
                        "Type": type_td.get_text(strip=True),
                        "Description": desc_td.get_text(strip=True),
                        "PDF Link": "",
                        "Local PDF Path": ""
                    }
                    pdf_a = link_td.select_one("a[href*='format=pdf']")
                    if pdf_a:
                        pdf_url = "https://find-and-update.company-information.service.gov.uk" + pdf_a["href"]
                        filing["PDF Link"] = pdf_url
                        if download_pdfs:
                            safe_name = re.sub(r'[<>:"/\\|?*]', '_', filing["Description"][:60])
                            filename = f"{num}_{filing['Date'].replace(' ', '_')}_{safe_name}.pdf"
                            dest = company_folder / filename
                            if not dest.exists():
                                status = download_pdf(pdf_url, dest)
                                filing["Local PDF Path"] = str(dest) if status == "OK" else status
                            else:
                                filing["Local PDF Path"] = str(dest)
                    filings.append(filing)
                row["Filing History"] = filings

            except Exception as e:
                st.error(f"Failed {num}: {e}")
                driver.quit()
                driver, wait = start_driver()

            results.append(row)
            progress.progress((idx + 1) / len(company_links))

        driver.quit()

        # ------------------ DISPLAY ------------------
        for r in results:
            r["People"] = json.dumps(r["People"])
            r["Filing History"] = json.dumps(r["Filing History"], ensure_ascii=False)

        df = pd.DataFrame(results)
        st.success(f"Done! {len(df)} companies scraped")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, f"india_companies_{len(df)}.csv", "text/csv")

        st.info(f"PDFs saved to: `{filings_dir.resolve()}`")

st.markdown("---")
st.caption("Docker-ready • Chrome 129 • Fixed all errors • Nov 17, 2025")

import os
import zipfile
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class CMSScraper:
    def __init__(self, download_dir="downloads", extract_dir="extracted"):
        self.base_url = "https://www.cms.gov/medicare/payment/fee-schedules/dmepos/dmepos-fee-schedule"
        self.download_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), download_dir)
        self.extract_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), extract_dir)
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.extract_dir, exist_ok=True)

    def _extract_year(self, url):
        """Extracts the calendar year from the CMS filename patterns."""
        filename = os.path.basename(url).lower()
        
        match_4d = re.search(r'20(24|25|26)', filename)
        if match_4d:
            return int(f"20{match_4d.group(1)}")
            
        match_dme = re.search(r'(?:dme|d)(24|25|26)', filename)
        if match_dme:
            return 2000 + int(match_dme.group(1))
            
        return None 

    def _recursive_unzip(self, target_dir):
        """Finds any nested ZIP archives inside the extracted folders and unzips them."""
        for root, _, files in os.walk(target_dir):
            for f in files:
                if f.lower().endswith('.zip'):
                    n_zip = os.path.join(root, f)
                    extract_to = n_zip.lower().replace('.zip', '_nested')
                    os.makedirs(extract_to, exist_ok=True)
                    try:
                        with zipfile.ZipFile(n_zip, 'r') as z_ref:
                            z_ref.extractall(extract_to)
                        os.remove(n_zip)
                        self._recursive_unzip(extract_to)
                    except Exception as e:
                        print(f"⚠️ Could not extract nested archive: {e}")

    def fetch_all_zip_files(self):
        """Scrapes and downloads files ONLY matching 2024, 2025, and 2026."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            print(f"🔗 Connecting to CMS Portal: {self.base_url}...")
            response = requests.get(self.base_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            target_urls = set()
            
            # Find direct links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '.zip' in href.lower() and ('dme' in href.lower() or 'puf' in href.lower()):
                    target_urls.add(urljoin(self.base_url, href))
            
            # Scan subpages
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'dme' in href.lower() and ('fee' in href.lower() or 'schedule' in href.lower()) and not '.zip' in href.lower():
                    subpage_url = urljoin(self.base_url, href)
                    try:
                        sub_res = requests.get(subpage_url, headers=headers, timeout=5)
                        if sub_res.status_code == 200:
                            sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                            for sub_link in sub_soup.find_all('a', href=True):
                                sub_href = sub_link['href']
                                if '.zip' in sub_href.lower():
                                    target_urls.add(urljoin(subpage_url, sub_href))
                    except Exception:
                        continue

            # Apply strict 2024-2026 filter
            filtered_urls = [url for url in target_urls if self._extract_year(url) in [2024, 2025, 2026]]
            
            print(f"🎯 Strict Filter Applied: Isolated {len(filtered_urls)} ZIP packages containing 2024-2026 datasets.")
            downloaded_paths = []
            
            for index, zip_url in enumerate(filtered_urls, start=1):
                file_name = os.path.basename(zip_url)
                target_path = os.path.join(self.download_dir, file_name)
                
                print(f"📥 [{index}/{len(filtered_urls)}] Downloading targeted window: {file_name}")
                try:
                    file_res = requests.get(zip_url, headers=headers, stream=True, timeout=30)
                    with open(target_path, 'wb') as f:
                        for chunk in file_res.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    specific_extract_dir = os.path.join(self.extract_dir, file_name.replace('.zip', ''))
                    os.makedirs(specific_extract_dir, exist_ok=True)
                    
                    with zipfile.ZipFile(target_path, 'r') as zip_ref:
                        zip_ref.extractall(specific_extract_dir)
                    
                    self._recursive_unzip(specific_extract_dir)
                    downloaded_paths.append(specific_extract_dir)
                    
                except Exception as e:
                    print(f"⚠️ Failed to process package {file_name}: {e}")
                    
            return downloaded_paths
            
        except Exception as e:
            print(f"❌ Scraper encountered an error: {e}")
            return []
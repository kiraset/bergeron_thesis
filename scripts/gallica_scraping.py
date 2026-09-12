import requests
import shutil
import os
import time

def download_book(base_id, start_page, end_page):
    base_url = "https://gallica.bnf.fr/iiif/ark:/"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    folder = "bignon"
    os.makedirs(folder, exist_ok=True)

    for i, page in enumerate(range(start_page, end_page + 1), start=1):
        page_id = f"{base_id}/f{page}"
        url = f"{base_url}{page_id}/full/full/0/native.jpg"
        filename = os.path.join(folder, f"leblanc_official_page{i}.jpg")

        print(f"Downloading f{page} → page{i}")

        try:
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()

            with open(filename, "wb") as f:
                shutil.copyfileobj(response.raw, f)
                
            time.sleep(12)

        except requests.exceptions.RequestException as e:
            print(f"Error on page {page}: {e}")
            continue

    print("Done!")


download_book("12148/bpt6k8726107z", 17, 539)
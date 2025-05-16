from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import requests
from urllib.parse import urljoin
import os
import time


def setup_driver():

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")

    chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver")
    if os.name == "nt":
        chromedriver_path += ".exe"  # Windows
    return webdriver.Chrome(
        service = Service(executable_path=chromedriver_path),
        options=options,
        seleniumwire_options={
            'disable_encoding': True,  # Accélère un peu
            'request_storage_base_dir': '/tmp/selenium',  # Réduit I/O
            'request_storage': 'memory',  # Pas d'écriture disque
        }
    )


def accept_cookies(driver):
    try:
        WebDriverWait(driver, 5 ).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept')]"))
        ).click()
    except:
        pass


def download_file(url, folder_path, filename, headers=None):
    """Télécharge un fichier et le sauvegarde dans le dossier spécifié"""
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()

        # Vérifie que c'est bien un fichier audio (pas une page HTML)
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type:
            print(f"Erreur: L'URL {url} retourne du HTML au lieu d'un fichier audio")
            return False

        file_path = os.path.join(folder_path, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Erreur lors du téléchargement de {url}: {str(e)}")
        return False


def get_first_product_link(driver, query):
    driver.get("https://www.deejay.de")
    accept_cookies(driver)

    search_box = WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input#ftAutocomplete"))
    )
    search_box.send_keys(query + Keys.RETURN)


    iframe = WebDriverWait(driver, 3).until(
        EC.presence_of_element_located((By.XPATH, "//iframe[@id='myIframe']"))
    )
    driver.switch_to.frame(iframe)

    try:
        first_product = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.product:first-of-type a[href^='/']"))
        )
        product_link = first_product.get_attribute('href')
    except:
        product_link = None

    driver.switch_to.default_content()
    return product_link

def create_reference_folder(reference):
    """Crée un dossier pour la référence si inexistant"""
    folder_path = os.path.join(os.getcwd(), reference)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path

def extract_main_product_details(driver, product_url,ref):
    driver.get(product_url)


    try:
        iframe = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//iframe[@id='myIframe']"))
        )
        driver.switch_to.frame(iframe)

        # Cibler spécifiquement le PREMIER article seulement
        main_article = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.single_product"))
        )
        folder_path = create_reference_folder(ref)

        image_elements = main_article.find_elements(By.CSS_SELECTOR, "div.cover img[src]")
        for i, img in enumerate(image_elements, 1):
            img_url = img.get_attribute('src')
            if 'l2' in img_url:  # Version basse résolution
                hi_res_url = img_url.replace('l2', 'xl')  # Version haute résolution
                download_file(hi_res_url,folder_path ,f"image_{i}.jpg")

        track_elements = main_article.find_elements(By.CSS_SELECTOR, "ul.playtrack li a[href^='play/']")
        audio_urls = []

        for i, track in enumerate(track_elements, 1):


            # Nettoyer les requêtes précédentes
            driver.requests.clear()

            # Clic via JavaScript pour déclencher le player
            driver.execute_script("arguments[0].click();", track)
            time.sleep(3)  # Attendre que le son se charge et que les requêtes soient faites



            # Filtrer toutes les requêtes MP3 faites après le clic
            mp3_requests = [r for r in driver.requests if r.response and r.url.endswith(".mp3")]

            if mp3_requests:
                last_mp3 = mp3_requests[-1].url
                audio_urls.append(last_mp3)

                success = download_file(last_mp3, folder_path,  os.path.basename(last_mp3))
                if not success:
                    print(f"Échec du téléchargement de la piste {i}")
            else:
                print(f" Aucun MP3 détecté pour la piste {i}")


        description_elem = main_article.find_elements(By.CSS_SELECTOR, "div.description p")
        description = description_elem[0].text if description_elem else ""
        details = {
            'artist': main_article.find_element(By.CSS_SELECTOR, "div.artist").text,
            'title': main_article.find_element(By.CSS_SELECTOR, "div.title").text,
            'price': main_article.find_element(By.CSS_SELECTOR, "span.price").text,
            "tracks": [t.text for t in main_article.find_elements(By.CSS_SELECTOR, "ul.playtrack li")],
            'description': description,
            'url': product_url,
            'image' : image_elements is not None,
            'audio' : track_elements is not None,
        }


        driver.switch_to.default_content()
        return details

    except Exception as e:
        print(f"Erreur extraction article principal: {str(e)}")
        driver.switch_to.default_content()
        return None


def main():
    start_time = time.time()
    driver = setup_driver()
    try:
        references = ["POSS-012C_"]

        for ref in references:
            print(f"\n=== TRAITEMENT DE {ref} ===")

            product_url = "https://www.deejay.de/Various_Various_Artists_2_-_EP3_POSS-012C_Vinyl__1149100"

            if not product_url:
                print(f"Aucun produit trouvé pour {ref}")
                continue

            product_data = extract_main_product_details(driver, product_url,ref)

            if product_data:
                print(f"Artiste***Titre: {product_data['artist']}***{product_data['title']}")
                print(f"Description: {product_data['description']}")
                print("")
                for i, track in enumerate(product_data['tracks'], 1):
                    print(f"{i}. {track}")
            else:
                print("Échec extraction article principal")

            print("=" * 60)

    finally:
        driver.quit()

    end_time = time.time()  # Capturer le temps à la fin
    execution_time = end_time - start_time  # Calculer la durée d'exécution
    print(f"\nTemps d'exécution total : {execution_time:.2f} secondes")


if __name__ == "__main__":
    main()
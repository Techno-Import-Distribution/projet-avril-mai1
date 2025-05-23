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

    # Utiliser ChromeDriverManager pour gérer le chemin du chromedriver
    # C'est plus robuste que de gérer le chemin manuellement
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), # Utilisation de ChromeDriverManager
        options=options,
        seleniumwire_options={
            'disable_encoding': True,  # Accélère un peu
            'request_storage_base_dir': '/tmp/selenium',  # Réduit I/O
            'request_storage': 'memory',  # Pas d'écriture disque
        }
    )


def accept_cookies(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept')]"))
        ).click()
    except:
        pass


def download_file(url, folder_path, filename, headers=None):
    """Télécharge un fichier et le sauvegarde dans le dossier spécifié"""
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()

        # Vérifie que c'est bien un fichier (pas une page HTML)
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type:
            print(f"Erreur: L'URL {url} retourne du HTML au lieu d'un fichier attendu.")
            return False

        file_path = os.path.join(folder_path, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Erreur lors du téléchargement de {url}: {str(e)}")
        return False


def create_product_folder(product_name):
    """Crée un dossier pour le produit en utilisant son nom, si inexistant.
       Nettoie le nom du produit pour un chemin de fichier valide."""
    # Nettoyer le nom du produit pour le rendre compatible avec les noms de dossiers
    clean_product_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    if not clean_product_name: # Au cas où le nom serait vide après nettoyage
        clean_product_name = "unknown_product"

    folder_path = os.path.join(os.getcwd(), clean_product_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path


def extract_main_product_details_undergroundtekno(driver, product_url):
    driver.get(product_url)
    time.sleep(2) # Laisser le temps au JS statique de charger et aux éléments d'apparaître

    try:
        # Extraction du titre du vinyl (H1)
        # On suppose que le H1 est le titre du vinyl, comme "Access Violation 03"
        vinyl_title = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
        if not vinyl_title: # Fallback si le titre est vide
            vinyl_title = "Unknown_Vinyl"

        # Création du dossier basée sur le titre du vinyl
        folder_path = create_product_folder(vinyl_title)

        # Extraction de l'artiste
        artists_elements = driver.find_elements(By.CSS_SELECTOR, "h5 a.ajaxify")
        artists = [artist_el.text.strip() for artist_el in artists_elements]
        artist_name = " & ".join(artists) if artists else "Artiste inconnu"


        # Description
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, "div.description p")
            description = description_element.text.strip()
        except:
            description = ""

        # Images
        images = driver.find_elements(By.CSS_SELECTOR, "div.col-md-4.col-left img.img-product")
        for i, img in enumerate(images, 1):
            src = img.get_attribute("src")
            if src:
                download_file(src, folder_path, f"image_{i}.jpg")


        # Track titles (pour l'affichage et pour nommer les fichiers audio)
        track_titles = [] # Pour l'affichage dans la console
        track_names_for_files = [] # Pour les noms de fichiers audio
        track_rows = driver.find_elements(By.CSS_SELECTOR, "div.row-table-tracks")
        for row in track_rows:
            try:
                track_name_element = row.find_element(By.CSS_SELECTOR, "div.col-track-name")
                track_name_raw = track_name_element.text.strip()
                track_titles.append(track_name_raw)

                # Nettoyer le nom de piste pour le nom de fichier
                clean_track_name = "".join(c for c in track_name_raw if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                track_names_for_files.append(clean_track_name if clean_track_name else f"track_{len(track_names_for_files) + 1}")
            except Exception as e:
                print(f"Erreur lors de l'extraction du nom de piste dans une ligne : {e}")
                track_titles.append(f"Piste {len(track_titles) + 1} (Nom inconnu)")
                track_names_for_files.append(f"track_{len(track_names_for_files) + 1}")


        # Audios - Scoping to the main product's content area
        audio_urls = []
        main_product_content = driver.find_element(By.CSS_SELECTOR, "div.col-md-8.col-right.order-sm-12")
        audio_buttons = main_product_content.find_elements(By.CSS_SELECTOR, "button.btn-play-link")

        num_tracks_to_process = min(len(audio_buttons), len(track_names_for_files))

        for i in range(num_tracks_to_process):
            button = audio_buttons[i]
            track_name_for_file = track_names_for_files[i]

            src = button.get_attribute("data-href")
            if src:
                full_url = urljoin(product_url, src)
                audio_urls.append(full_url)
                filename = f"{track_name_for_file}.mp3"
                download_file(full_url, folder_path, filename)
            else:
                print(f"URL audio non trouvée pour la piste {i+1}.")

        details = {
            "artist": artist_name,
            "title": vinyl_title,
            "description": description,
            "tracks": track_titles,
            "url": product_url,
            "image": len(images) > 0,
            "audio": len(audio_urls) > 0
        }

        return details

    except Exception as e:
        print(f"Erreur générale lors de l'extraction des détails du produit depuis {product_url}: {str(e)}")
        return None


def main():
    start_time = time.time()
    driver = setup_driver()
    try:
        # Liste des URLs des produits à scraper
        product_urls_to_scrape = [
            "https://www.undergroundtekno.com/fr/product/mental-core-02/12180",
            "https://www.undergroundtekno.com/fr/product/tekno-for-breakfast-01/13442",
            "https://www.undergroundtekno.com/fr/product/tekno-4-breakfast-02/15483",
            "https://www.undergroundtekno.com/fr/product/tekno-trip-01/11474",
            "https://www.undergroundtekno.com/fr/product/tekno-trip-08/14680",
            "https://www.undergroundtekno.com/fr/product/u-cant-stop-the-rave/9092",
            "https://www.undergroundtekno.com/fr/product/warning-shots/10179"
        ]

        for url in product_urls_to_scrape:
            print(f"\n=== TRAITEMENT DE L'URL : {url} ===")

            product_data = extract_main_product_details_undergroundtekno(driver, url)

            if product_data:
                print(f"Titre: {product_data['artist']}***{product_data['title']}")
                print(f"Description: {product_data['description']}")
                print("\nPistes:")
                for i, track in enumerate(product_data['tracks'], 1):
                    print(f"{i}. {track}")
            else:
                print(f"Échec de l'extraction des détails pour {url}")

            print("=" * 60)

    finally:
        driver.quit()

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\nTemps d'exécution total : {execution_time:.2f} secondes")


if __name__ == "__main__":
    main()
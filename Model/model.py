import os
import time
import requests
from urllib.parse import urljoin

# Importations spécifiques à Selenium
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class ScraperModel:
    """
    Gère la logique de scraping et la persistance des données.
    """

    def __init__(self):
        self.driver = None

    def setup_driver(self):
        """
        Configure et retourne une instance de Selenium WebDriver.
        Utilise seleniumwire pour intercepter les requêtes.
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")  # Exécute le navigateur en arrière-plan
        options.add_argument("--disable-blink-features=AutomationControlled")  # Évite la détection comme bot
        options.add_argument("--window-size=1920,1080")  # Définit la taille de la fenêtre
        options.add_argument("--start-maximized")  # Maximise la fenêtre au démarrage
        options.add_argument(
            "--disable-dev-shm-usage")  # Contourne les problèmes de mémoire partagée dans certains environnements (Docker)

        # Assure que chromedriver est dans le même répertoire ou accessible via PATH
        # ChromeDriverManager.install() télécharge et gère le driver automatiquement
        service = Service(ChromeDriverManager().install())

        # Options spécifiques à seleniumwire
        seleniumwire_options = {
            'disable_encoding': True,  # Peut accélérer un peu
            'request_storage_base_dir': '/tmp/selenium',  # Réduit l'utilisation I/O sur disque
            'request_storage': 'memory',  # Stocke les requêtes en mémoire au lieu du disque
        }

        self.driver = webdriver.Chrome(
            service=service,
            options=options,
            seleniumwire_options=seleniumwire_options
        )
        return self.driver

    def quit_driver(self):
        """Ferme le WebDriver si il est actif."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def download_file(self, url, folder_path, filename, headers=None):
        """
        Télécharge un fichier depuis une URL et le sauvegarde dans un dossier spécifié.
        Vérifie le Content-Type pour s'assurer que c'est un fichier audio.
        """
        try:
            response = requests.get(url, stream=True, headers=headers)
            response.raise_for_status()  # Lève une exception pour les codes d'état HTTP d'erreur

            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print(f"Erreur: L'URL {url} retourne du HTML au lieu d'un fichier audio.")
                return False

            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):  # Télécharge le fichier par morceaux
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"Erreur lors du téléchargement de {url}: {str(e)}")
            return False

    def get_first_product_link(self, query):
        """
        Navigue vers deejay.de, effectue une recherche et retourne le lien
        du premier produit trouvé.
        """
        self.driver.get("https://www.deejay.de")


        try:
            search_box = WebDriverWait(self.driver, 10).until(  # Augmenté le temps d'attente
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#ftAutocomplete"))
            )
            search_box.send_keys(query + Keys.RETURN)  # Entre la requête et appuie sur Entrée

            # Attente de l'iframe de résultats
            iframe = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='myIframe']"))
            )
            self.driver.switch_to.frame(iframe)  # Bascule vers l'iframe

            # Attente du premier produit dans l'iframe
            first_product = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.product:first-of-type a[href^='/']"))
            )
            product_link = first_product.get_attribute('href')  # Récupère l'URL du produit
        except Exception as e:
            print(f"Aucun produit trouvé ou erreur lors de la recherche pour '{query}': {e}")
            product_link = None
        finally:
            self.driver.switch_to.default_content()  # Revient au contenu principal de la page
        return product_link

    def create_reference_folder(self, reference):
        """Crée un dossier pour la référence donnée si il n'existe pas."""
        folder_path = os.path.join(os.getcwd(), reference)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        return folder_path

    def extract_main_product_details(self, product_url, ref):
        """
        Navigue vers la page d'un produit, extrait les détails (images, audio, texte)
        et les sauvegarde.
        """
        self.driver.get(product_url)
        details = {}  # Dictionnaire pour stocker les détails du produit

        try:
            iframe = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[@id='myIframe']"))
            )
            self.driver.switch_to.frame(iframe)  # Bascule vers l'iframe du produit

            main_article = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.single_product"))
            )
            folder_path = self.create_reference_folder(ref)  # Crée le dossier pour la référence

            # Extraction et téléchargement des images
            image_elements = main_article.find_elements(By.CSS_SELECTOR, "div.cover img[src]")
            for i, img in enumerate(image_elements, 1):
                img_url = img.get_attribute('src')
                if 'l2' in img_url:
                    hi_res_url = img_url.replace('l2', 'xl')  # Tente de récupérer la version haute résolution
                    self.download_file(hi_res_url, folder_path, f"image_{i}.jpg")
            details['image_downloaded'] = bool(image_elements)  # Indique si des images ont été traitées

            # Extraction et téléchargement des pistes audio
            track_elements = main_article.find_elements(By.CSS_SELECTOR, "ul.playtrack li a[href^='play/']")
            audio_urls = []
            for i, track in enumerate(track_elements, 1):
                self.driver.requests.clear()  # Nettoie les requêtes précédentes de seleniumwire
                self.driver.execute_script("arguments[0].click();", track)  # Clique via JS pour déclencher le lecteur
                time.sleep(3)  # Attente pour que la requête MP3 soit faite

                mp3_requests = [r for r in self.driver.requests if r.response and r.url.endswith(".mp3")]
                if mp3_requests:
                    last_mp3 = mp3_requests[-1].url  # Prend la dernière requête MP3
                    audio_urls.append(last_mp3)
                    success = self.download_file(last_mp3, folder_path, os.path.basename(last_mp3))
                    if not success:
                        print(f"Échec du téléchargement de la piste {i}")
                else:
                    print(f"Aucun MP3 détecté pour la piste {i}")
            details['audio_downloaded'] = bool(track_elements)  # Indique si des pistes audio ont été traitées

            # Extraction des détails textuels
            description_elem = main_article.find_elements(By.CSS_SELECTOR, "div.description p")
            description = description_elem[0].text if description_elem else ""

            details.update({
                'artist': main_article.find_element(By.CSS_SELECTOR, "div.artist").text,
                'title': main_article.find_element(By.CSS_SELECTOR, "div.title").text,
                "tracks": [t.text for t in main_article.find_elements(By.CSS_SELECTOR, "ul.playtrack li")],
                'description': description
            })

        except Exception as e:
            print(f"Erreur lors de l'extraction des détails du produit pour {product_url}: {str(e)}")
            details = None  # En cas d'erreur majeure, retourne None
        finally:
            self.driver.switch_to.default_content()  # Revient au contenu principal
        return details

    def scrape_references(self, references, progress_callback=None):
        """
        Fonction principale pour scraper une liste de références.
        Prend un callback pour rapporter la progression à l'interface.
        """
        start_time = time.time()
        self.setup_driver()  # Initialise le driver
        results = []  # Liste pour stocker les résultats de chaque référence

        try:
            for i, ref in enumerate(references):
                if progress_callback:
                    progress_callback(f"Traitement de la référence : {ref} ({i + 1}/{len(references)})")

                print(f"\n=== TRAITEMENT DE {ref} ===")
                product_url = self.get_first_product_link(ref)

                if not product_url:
                    print(f"Aucun produit trouvé pour {ref}")
                    results.append({'reference': ref, 'status': 'Aucun produit trouvé'})
                    continue

                product_data = self.extract_main_product_details(product_url, ref)

                if product_data:
                    print(f"Artiste***Titre: {product_data['artist']}***{product_data['title']}")
                    print(f"Description: {product_data['description']}")
                    for j, track in enumerate(product_data['tracks'], 1):
                        print(f"{j}. {track}")
                    results.append({'reference': ref, 'status': 'Succès', 'data': product_data})
                else:
                    print("Échec de l'extraction des détails du produit.")
                    results.append({'reference': ref, 'status': 'Échec de l\'extraction'})
                print("=" * 60)

        finally:
            self.quit_driver()  # S'assure que le driver est fermé même en cas d'erreur
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"\nTemps d'exécution total : {execution_time:.2f} secondes")
            if progress_callback:
                progress_callback(f"Scraping terminé en {execution_time:.2f} secondes.")
        return results


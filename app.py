from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time


def get_vinyl_info(reference):
    # Configuration du navigateur
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # 1. Accéder à la page
        driver.get(f"https://www.deejay.de/{reference.lower()}")

        # 2. Attendre le chargement de l'iframe
        time.sleep(3)  # Attente nécessaire pour le chargement

        # 3. Basculer vers l'iframe de contenu
        iframe = driver.find_element(By.XPATH, "//iframe[@id='myIframe']")
        driver.switch_to.frame(iframe)

        # 4. Détection des éléments dans l'iframe
        product = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.product, #theList"))
        )

        # 5. Extraction des données
        data = {
            "artist": product.find_element(By.CSS_SELECTOR, "h2.artist").text,
            "title": product.find_element(By.CSS_SELECTOR, "h3.title").text,
            "price": product.find_element(By.CSS_SELECTOR, "span.price").text,
            "tracks": [t.text for t in product.find_elements(By.CSS_SELECTOR, "ul.playtrack li")],
            "sku": reference.upper()
        }

        return data

    except Exception as e:
        print(f"Erreur: {str(e)}")
        driver.save_screenshot(f"error_{reference}.png")
        return None
    finally:
        driver.quit()


if __name__ == "__main__":
    references = ["SK11X031", "PTYF001", "TRESOR337"]

    for ref in references:
        print(f"\n=== TRAITEMENT DE {ref} ===")
        start_time = time.time()
        result = get_vinyl_info(ref)
        elapsed = time.time() - start_time

        if result:
            print(f"\nRÉSULTAT ({round(elapsed, 2)}s):")
            print(f"Artiste: {result['artist']}")
            print(f"Titre: {result['title']}")
            print(f"Prix: {result['price']}")
            print(f"Réf: {result['sku']}")
            print("Pistes:")
            for i, track in enumerate(result['tracks'], 1):
                print(f"{i}. {track}")
        else:
            print(f"ÉCHEC pour {ref} après {round(elapsed, 2)}s")

        print("=" * 60)
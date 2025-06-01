import re
import time
import requests
import xml.etree.ElementTree as ET
import os


API_KEY         = '938DHC7VE22UDGZF3T1NI46TS8J3VZ1P'
BASE_URL        = 'https://www.techno-import.fr/shop/api'
DEFAULT_LANG_ID = '4'   # Français

session = requests.Session()
session.auth = (API_KEY, '')

def slugify(text):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9]+', '-', t)
    return re.sub(r'-+', '-', t).strip('-')

def fetch_blank_product_schema():
    url = f'{BASE_URL}/products?schema=blank'
    r = session.get(url, timeout=10); r.raise_for_status()
    return r.content

def fill_product_schema(schema_xml, data):
    root    = ET.fromstring(schema_xml)
    prod    = root.find('product')

    # Champs principaux
    prod.find('reference').text = data['reference']
    prod.find('price').text     = str(data['price'])
    prod.find('weight').text    = str(data['weight'])
    prod.find('active').text    = '1'
    # Catégorie par défaut (2)
    prod.find('id_category_default').text = str(data.get('category_id', 2))

    # Multilingue
    for tag, value in (
        ('name', data['name']),
        ('link_rewrite', slugify(data['name'])),
        ('description', data['description'])
    ):
        elem = prod.find(tag)
        for lang in elem.findall('language'):
            if lang.get('id') == DEFAULT_LANG_ID:
                lang.text = value

    # Associations : on laisse tel quel, ou supprime tags inutiles si présents
    assoc = prod.find('associations')
    if assoc is not None:
        old_tags = assoc.find('tags')
        if old_tags is not None:
            assoc.remove(old_tags)

    # Stock (quantité)
    stock_block = assoc.find('stock_availables')
    stock       = stock_block.find('stock_available')
    stock.find('id_product_attribute').text = '0'
    qty = stock.find('quantity')
    if qty is None:
        qty = ET.SubElement(stock, 'quantity')
    qty.text = str(data['quantity'])

    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def create_product_prestashop(data):
    """
    Crée un produit PrestaShop à partir des données fournies (fusion scraping + GUI).
    Retourne l'ID du produit créé (ou None en cas d'échec).
    """
    try:
        # 1. Récupère le schéma vierge
        schema = fetch_blank_product_schema()
        # 2. Remplit avec les données
        payload = fill_product_schema(schema, data)
        # 3. Envoie à l'API
        url     = f'{BASE_URL}/products'
        headers = {'Content-Type': 'application/xml'}
        r       = session.post(url, data=payload, headers=headers, timeout=10)
        r.raise_for_status()

        # Récupère l'ID du produit
        loc = r.headers.get('Location') or r.headers.get('location')
        if loc:
            return loc.rstrip('/').rsplit('/', 1)[-1]
        # Fallback par recherche de la référence
        ref = data['reference']
        params = {
            'filter[reference]': f'[{ref}]',
            'sort':             '[id_DESC]',
            'limit':            '1',
            'display':          '[id]'
        }
        r2 = session.get(f'{BASE_URL}/products', params=params, timeout=10)
        r2.raise_for_status()
        root2 = ET.fromstring(r2.content)
        return root2.findtext('.//product/id')
    except Exception as e:
        print(f"[PrestaShop API] Erreur création produit : {e}")
        return None

def get_stock_available_id(xml_content):
    root = ET.fromstring(xml_content)
    for stock in root.findall('.//stock_available'):
        stock_id = stock.get('id')
        if stock_id:
            return stock_id
    return None

def update_quantity(product_id, quantity):
    url = f"{BASE_URL}/stock_availables?filter[id_product]={product_id}"
    r = session.get(url, timeout=10)
    r.raise_for_status()
    stock_id = get_stock_available_id(r.text)
    if not stock_id:
        raise Exception("Impossible de trouver le stock_available pour le produit !")

    # Récupère le XML complet du stock_available
    url2 = f"{BASE_URL}/stock_availables/{stock_id}"
    r2 = session.get(url2, timeout=10)
    r2.raise_for_status()
    root2 = ET.fromstring(r2.content)
    stock_avail = root2.find('stock_available')
    stock_avail.find('quantity').text = str(quantity)
    # Correction : force id_product_attribute à "0"
    stock_avail.find('id_product_attribute').text = '0'

    # Génère le XML complet (avec <prestashop>)
    xml_data = ET.tostring(root2, encoding='utf-8', xml_declaration=True)
    print("Payload envoyé pour PUT :")
    print(xml_data.decode("utf-8"))

    r3 = session.put(url2, data=xml_data, headers={'Content-Type': 'application/xml'}, timeout=10)
    print("Réponse du PUT :")
    print(r3.text)
    r3.raise_for_status()
    print(f"Quantité mise à jour pour produit {product_id} : {quantity}")

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

def upload_product_image(product_id, image_path):
    """
    Upload une image sur le produit PrestaShop spécifié.
    """
    url = f"{BASE_URL}/images/products/{product_id}"
    params = {'detect_image_type': '1'}

    with open(image_path, 'rb') as img_file:
        files = {'image': img_file}
        resp = session.post(url, params=params, files=files, timeout=30)

    print(f"→ Statut HTTP : {resp.status_code}")
    print(f"→ Upload de {image_path} terminé")
    resp.raise_for_status()

    # Petite pause pour éviter de spammer l'API
    time.sleep(0.3)

    # Optionnel : récupération de l'ID de l'image uploadée
    latest_id = get_latest_image_id(product_id)
    if latest_id:
        print(f"→ Image '{os.path.basename(image_path)}' uploadée, ID détecté : {latest_id}")
    else:
        print(f"⚠️ Impossible de trouver l’ID de l’image uploadée pour '{image_path}'.")
    return latest_id

def get_latest_image_id(product_id):
    """
    Récupère l'ID de la dernière image uploadée pour ce produit.
    """
    url = f"{BASE_URL}/images/products/{product_id}"
    params = {'display': '[id]'}
    resp = session.get(url, params=params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ids = []
    for img in root.findall('.//image'):
        iid = img.get('id')
        if iid and iid.isdigit():
            ids.append(int(iid))
    if not ids:
        return None
    return str(max(ids))

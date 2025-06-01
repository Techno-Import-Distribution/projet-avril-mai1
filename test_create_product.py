import re
import time
import requests
import xml.etree.ElementTree as ET

# Configuration de l’API
API_KEY         = '938DHC7VE22UDGZF3T1NI46TS8J3VZ1P'
BASE_URL        = 'https://www.techno-import.fr/shop/api'
DEFAULT_LANG_ID = '4'   # Français

session = requests.Session()
session.auth = (API_KEY, '')

def fetch_blank_product_schema():
    url = f'{BASE_URL}/products?schema=blank'
    r = session.get(url, timeout=10); r.raise_for_status()
    return r.content

def slugify(text):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9]+', '-', t)
    return re.sub(r'-+', '-', t).strip('-')

def fill_product_schema(schema_xml, data):
    root    = ET.fromstring(schema_xml)
    prod    = root.find('product')

    # 1) Champs de base
    prod.find('reference').text         = data['reference']
    prod.find('price').text             = str(data['price'])
    prod.find('weight').text            = str(data['weight'])
    prod.find('active').text            = '1'

    # 2) Catégorie par défaut = premier de la liste
    default_cat = data['category_ids'][0]
    prod.find('id_category_default').text = str(default_cat)

    # 3) Multilingue
    for tag, value in (
        ('name', data['name']),
        ('link_rewrite', slugify(data['name'])),
        ('description', data['description'])
    ):
        elem = prod.find(tag)
        for lang in elem.findall('language'):
            if lang.get('id') == DEFAULT_LANG_ID:
                lang.text = value

    # 4) Associations → catégories
    assoc = prod.find('associations')
    # on vire l’ancien bloc si existant
    old = assoc.find('categories')
    if old is not None:
        assoc.remove(old)
    # on reconstruit
    cat_block = ET.SubElement(assoc, 'categories')
    for cid in data['category_ids']:
        cat = ET.SubElement(cat_block, 'category')
        ET.SubElement(cat, 'id').text       = str(cid)
        ET.SubElement(cat, 'position').text = '0'      # <--- c’est la clé

    # 5) Supprime tags si inutile
    old_tags = assoc.find('tags')
    if old_tags is not None:
        assoc.remove(old_tags)

    # 6) Stock
    stock_block = assoc.find('stock_availables')
    stock       = stock_block.find('stock_available')
    stock.find('id_product_attribute').text = '0'
    qty = stock.find('quantity')
    if qty is None:
        qty = ET.SubElement(stock, 'quantity')
    qty.text = str(data['quantity'])

    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def create_product(xml_payload):
    url     = f'{BASE_URL}/products'
    headers = {'Content-Type': 'application/xml'}
    r       = session.post(url, data=xml_payload, headers=headers, timeout=10)
    r.raise_for_status()

    # 1) Si PrestaShop renvoie un header Location, on l’utilise :
    loc = r.headers.get('Location') or r.headers.get('location')
    if loc:
        return loc.rstrip('/').rsplit('/', 1)[-1]

    # 2) Sinon, fallback trié et limité à 1
    ref = ET.fromstring(xml_payload).findtext('product/reference')
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

def get_stock_available_id(xml_content):
    root = ET.fromstring(xml_content)
    for stock in root.findall('.//stock_available'):
        stock_id = stock.get('id')
        if stock_id:
            return stock_id
    return None

if __name__ == "__main__":
    # 1) Générer une référence unique à chaque exécution
    unique_ref = f"TEST{int(time.time())}"

    # 2) Construire test_data en utilisant cette référence dynamique
    test_data = {
        'name':         "Test Vinyl Product",
        'reference':    unique_ref,
        'description':  "Produit test.",
        'price':        15.99,
        'weight':       0.30,
        # Spécifie ici toutes les cases à cocher dans l'UI :
        # par exemple Home=2, VINYLS=6, Techno/Electro=59
        'category_ids': [59],
        'quantity':     10
    }

    print("1) Blank schema…")
    schema  = fetch_blank_product_schema()

    print("2) Fill…")
    payload = fill_product_schema(schema, test_data)
    print(payload.decode('utf-8'))

    print("3) Create…")
    new_id = create_product(payload)
    print("DEBUG: Recherche du stock_available pour le produit ID =", new_id)
    url = f"{BASE_URL}/stock_availables?filter[id_product]=[{new_id}]"
    r = session.get(url)
    print("Statut HTTP:", r.status_code)    
    print(r.text)

    print("Produit ID =", new_id)

    print("4) MAJ quantité…")
    update_quantity(new_id, test_data['quantity'])

import re
import time
import requests
import xml.etree.ElementTree as ET
import os

XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace('xlink', XLINK_NS)

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
    r = session.get(url, timeout=10)
    r.raise_for_status()
    return r.content

def fill_product_schema(schema_xml, data):
    """
    Remplit le XML blank du produit avec data. On suppose que data contient
    notamment :
      - 'reference'   (str)
      - 'price'       (float ou str)
      - 'weight'      (float ou str)
      - 'quantity'    (int ou str)
      - 'name'        (str)
      - 'description' (str)
      - 'category_ids' (list[int])  ← **Nouvelle liste de catégories** à cocher.
    """
    try:
        root = ET.fromstring(schema_xml)
    except ET.ParseError as e:
        print("[Error] Impossible de parser le XML blank :", e)
        return schema_xml

    prod = root.find('product')
    if prod is None:
        print("[Error] Balise <product> introuvable dans le XML blank !")
        return schema_xml

    # ─── 1) Champs principaux ────────────────────────────────────────────────
    try:
        prod.find('reference').text = data['reference']
        prod.find('price').text     = str(data['price'])
        prod.find('weight').text    = str(data['weight'])
        prod.find('active').text    = '1'
    except Exception as e:
        print(f"[Warning] Impossible de remplir reference/price/weight/active : {e}")

    # available_for_order
    if prod.find('available_for_order') is None:
        ET.SubElement(prod, 'available_for_order').text = '1'
    else:
        prod.find('available_for_order').text = '1'

    # show_price
    if prod.find('show_price') is None:
        ET.SubElement(prod, 'show_price').text = '1'
    else:
        prod.find('show_price').text = '1'

    # ─── 2) id_category_default ← Premier élément de category_ids, ou 1 en fallback ──
    cat_ids = data.get('category_ids', [])
    if isinstance(cat_ids, list) and cat_ids:
        default_cat = str(cat_ids[0])
    else:
        default_cat = '1'
    node_id_default = prod.find('id_category_default')
    if node_id_default is not None:
        node_id_default.text = default_cat
    else:
        ET.SubElement(prod, 'id_category_default').text = default_cat

    # ─── 3) Multilingue (name, link_rewrite, description) ────────────────────
    for tag, value in (
        ('name', data['name']),
        ('link_rewrite', slugify(data['name'])),
        ('description', data['description'])
    ):
        elem = prod.find(tag)
        if elem is not None:
            for lang in elem.findall('language'):
                if lang.get('id') == DEFAULT_LANG_ID:
                    lang.text = value

    # ─── 4) Associations : suppression de <tags>, puis injection de category_ids ──
    assoc = prod.find('associations')
    if assoc is None:
        print("[Warning] Aucun nœud <associations> trouvé, impossibilité de gérer les catégories.")
    else:
        # Retirer <tags> s'il existe
        old_tags = assoc.find('tags')
        if old_tags is not None:
            assoc.remove(old_tags)

        # Récupérer (ou créer) le nœud <categories>
        cats_node = assoc.find('categories')
        if cats_node is None:
            cats_node = ET.SubElement(assoc, 'categories')

        # Mettre les bons attributs nodeType/api pour Presta
        cats_node.set('nodeType', 'category')
        cats_node.set('api', 'categories')

        # Supprimer tout enfant existant
        for child in list(cats_node):
            cats_node.remove(child)

        # Insérer chaque ID depuis data['category_ids']
        for cid in cat_ids:
            cat_el = ET.SubElement(cats_node, 'category')
            id_el  = ET.SubElement(cat_el, 'id')
            id_el.text = str(cid)
        print(f"[Debug] Injection des catégories depuis GUI : {cat_ids}")

    # ─── 5) Stock (quantité) ──────────────────────────────────────────────────
    if assoc is not None:
        stock_block = assoc.find('stock_availables')
        if stock_block is not None:
            stock = stock_block.find('stock_available')
            if stock is not None:
                # Forcer id_product_attribute à 0
                node_attr = stock.find('id_product_attribute')
                if node_attr is not None:
                    node_attr.text = '0'
                else:
                    ET.SubElement(stock, 'id_product_attribute').text = '0'

                qty = stock.find('quantity')
                if qty is None:
                    qty = ET.SubElement(stock, 'quantity')
                qty.text = str(data['quantity'])
            else:
                print("[Warning] <stock_available> introuvable sous <stock_availables>.")
        else:
            print("[Warning] Aucun nœud <stock_availables> dans <associations>.")

    # ─── 6) Réinjection du namespace xlink (nécessaire pour Presta) ───────────
    root.set('xmlns:xlink', XLINK_NS)

    # ─── 7) Sérialiser en chaîne et renvoyer ─────────────────────────────────
    try:
        new_xml = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        print("[Debug] XML final généré:")
        print(new_xml.decode('utf-8'))
        return new_xml
    except Exception as e:
        print(f"[Error] Impossible de convertir l’arbre XML en chaîne : {e}")
        return schema_xml

def create_product_prestashop(data):
    """
    Crée un produit PrestaShop via l’API à partir de data.
    data doit contenir au moins 'reference','price','weight','quantity',
    'name','description','category_ids'.
    Retourne l’ID du produit créé, ou None.
    """
    try:
        schema = fetch_blank_product_schema()
        payload = fill_product_schema(schema, data)

        url     = f'{BASE_URL}/products'
        headers = {'Content-Type': 'application/xml'}
        print("[Debug] Envoi POST /products:")
        print(payload.decode('utf-8'))

        r = session.post(url, data=payload, headers=headers, timeout=10)
        print(f"[Debug] Réponse HTTP POST /products : {r.status_code}")
        print(r.text)
        r.raise_for_status()

        # Extraire l’ID du header Location
        loc = r.headers.get('Location') or r.headers.get('location')
        if loc:
            return loc.rstrip('/').rsplit('/', 1)[-1]

        # Fallback : rechercher par référence
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
        new_id = root2.findtext('.//product/id')
        print(f"[Debug] Produit recherché par ref → ID = {new_id}")
        return new_id

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
        raise Exception("Impossible de trouver le stock_available !")

    url2  = f"{BASE_URL}/stock_availables/{stock_id}"
    r2   = session.get(url2, timeout=10)
    r2.raise_for_status()

    root2       = ET.fromstring(r2.content)
    stock_avail = root2.find('stock_available')
    stock_avail.find('quantity').text = str(quantity)
    stock_avail.find('id_product_attribute').text = '0'

    xml_data = ET.tostring(root2, encoding='utf-8', xml_declaration=True)
    print("Payload PUT (update stock) :")
    print(xml_data.decode('utf-8'))

    r3 = session.put(url2, data=xml_data, headers={'Content-Type': 'application/xml'}, timeout=10)
    print("Réponse PUT (update stock) :")
    print(r3.text)
    r3.raise_for_status()
    print(f"Quantité mise à jour pour produit {product_id} : {quantity}")

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

def upload_product_image(product_id, image_path):
    url = f"{BASE_URL}/images/products/{product_id}"
    params = {'detect_image_type': '1'}

    with open(image_path, 'rb') as img_file:
        files = {'image': img_file}
        resp = session.post(url, params=params, files=files, timeout=30)

    print(f"→ Statut HTTP Upload image : {resp.status_code}")
    print(f"→ Upload de {image_path} terminé")
    resp.raise_for_status()
    time.sleep(0.3)

    latest_id = get_latest_image_id(product_id)
    if latest_id:
        print(f"→ Image '{os.path.basename(image_path)}' uploadée, ID détecté : {latest_id}")
    else:
        print(f"⚠️ Impossible de trouver l’ID de l’image uploadée pour '{image_path}'.")
    return latest_id

def get_latest_image_id(product_id):
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
    return str(max(ids)) if ids else None

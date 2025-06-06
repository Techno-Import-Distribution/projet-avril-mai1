import threading
import sys
import os
import re  # Pour la validation des références

# On ajoute le répertoire courant au path Python pour pouvoir importer localement
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import des classes Model et View
from Model.model import ScraperModel
from View.view import ScraperView
from Model.prestashop_api import create_product_prestashop, update_quantity, upload_product_image

# ─────────────────────────────────────────────────────────────────────────────
# Dictionnaire de correspondance "Type GUI" → "ID de catégorie enfant" PrestaShop
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_MAP = {
    "Techno / Electro"              : 59,
    "Drum & Bass / Jungle / Dubstep" : 33,
    "House / Deep House"            : 29,
    "Hardtek / Acidcore / Tribe"    : 35,
    "Hardcore / Gabber"             : 30,
    "Minimal / Micro House"         : 28
}


class ScraperController:
    """
    Contrôleur pour l'application de scraping de vinyles.
    Gère les interactions entre la Vue (interface utilisateur) et le Modèle (logique de scraping).
    """

    def __init__(self, root):
        self.root = root
        self.model = ScraperModel()               # Instancie le modèle
        self.view = ScraperView(root)             # Instancie la vue
        self.view.set_controller(self)            # Lie la vue au contrôleur
        self.view._create_widgets()               # Initialise les composants de l'interface

    def generate_lines_command(self):
        """
        Commande exécutée lorsque le bouton 'Générer' est cliqué.
        Demande à la vue de générer des lignes d'entrée pour les produits.
        """
        nb_products = self.view.get_num_products()
        if nb_products is None:  # get_num_products affiche déjà l'erreur
            return

        self.view.clear_product_rows()  # Nettoie les anciennes lignes
        self.view.add_product_headers()  # Ajoute les en-têtes
        for i in range(1, nb_products + 1):
            self.view.add_product_row(i)  # Ajoute chaque ligne de produit

        self.validate_all_inputs()  # Valide immédiatement après la génération

    def validate_all_inputs(self):
        """
        Valide tous les champs d'entrée (fournisseur et lignes de produits)
        et met à jour l'état du bouton 'Lancer'.
        """
        # Validation du champ Fournisseur
        supplier = self.view.get_supplier()
        valid_supplier = bool(supplier) and len(supplier) <= 100
        self.view.highlight_entry(self.view.get_supplier_entry(), valid_supplier)

        all_product_rows_valid = True
        product_data = self.view.get_references_data()  # Récupère les données brutes pour validation

        # Validation des lignes de produits
        for i, row_data in enumerate(product_data):
            # Récupère les widgets Entry pour la ligne courante
            row_entries = self.view.rows[i]

            # Validation de la référence: non vide et alphanumérique
            valid_ref = bool(row_data['référence']) and re.fullmatch(r'^[a-zA-Z0-9\-.]+$', row_data['référence']) is not None
            self.view.highlight_entry(row_entries[0], valid_ref)

            # Validation du prix: non vide et convertible en float
            valid_prix = row_data['prix'] is not None
            self.view.highlight_entry(row_entries[1], valid_prix)

            # Validation de la quantité: non vide et convertible en int
            valid_qte = row_data['quantité'] is not None
            self.view.highlight_entry(row_entries[2], valid_qte)

            # Validation du poids: non vide et convertible en float
            valid_poids = row_data['poids'] is not None
            self.view.highlight_entry(row_entries[3], valid_poids)

            # Validation du type: doit être l’une des 6 options
            t = row_data.get('type', "")
            valid_type = t in [
                "Techno / Electro",
                "Drum & Bass / Jungle / Dubstep",
                "House / Deep House",
                "Hardtek / Acidcore / Tribe",
                "Hardcore / Gabber",
                "Minimal / Micro House"
            ]
            self.view.highlight_entry(row_entries[4], valid_type)

            if not (valid_ref and valid_prix and valid_qte and valid_poids and valid_type):
                all_product_rows_valid = False

        # Le bouton 'Lancer' est activé si le fournisseur est valide, toutes les lignes sont valides
        # et s'il y a au moins une ligne générée.
        can_launch = valid_supplier and all_product_rows_valid and bool(self.view.rows)
        self.view.set_launch_button_state('normal' if can_launch else 'disabled')

    def launch_script_command(self):
        """
        Commande exécutée lorsque le bouton 'Lancer' est cliqué.
        Récupère les références et lance le scraping dans un thread séparé.
        """
        product_data = self.view.get_references_data()

        # Extrait seulement les références valides pour le scraping
        references_to_scrape = [
            item['référence'] for item in product_data
            if item['référence'] and re.fullmatch(r'^[a-zA-Z0-9\-.]+$', item['référence']) is not None
        ]

        if not references_to_scrape:
            self.view.show_warning("Attention", "Aucune référence valide à scraper n'a été trouvée.")
            return

        self.view.show_message("Lancement", f"Lancement du scraping pour {len(references_to_scrape)} référence(s).")
        self.view.set_launch_button_state('disabled')  # Désactive le bouton pendant le scraping

        # Lance le scraping dans un thread séparé pour ne pas bloquer l'interface
        threading.Thread(target=self._run_scraper_in_thread, args=(references_to_scrape,)).start()

    def _run_scraper_in_thread(self, references):
        """
        Exécute le script de scraping (modèle) dans un thread séparé.
        Pour chaque scraping réussi, crée le produit sur PrestaShop.
        """
        try:
            results = self.model.scrape_references(references, progress_callback=self._update_progress)
            # Récupère les infos GUI pour faire la fusion
            product_data_gui = self.view.get_references_data()

            # Boucle sur chaque résultat du scraping
            for res in results:
                if res.get('status') == 'Succès' and res.get('data'):
                    # Trouve la ligne correspondante dans la GUI (par la référence)
                    ref = res['reference']
                    gui_line = next((item for item in product_data_gui if item['référence'] == ref), None)
                    if not gui_line:
                        print(f"Impossible de faire correspondre la référence {ref} avec les données GUI.")
                        continue

                    # Récupère le titre/artiste depuis le scraping
                    artist = res['data'].get('artist', '')
                    title  = res['data'].get('title', '')

                    # ─── Partie clé : construction des catégories dynamiques ────────────
                    type_label = gui_line.get('type', '')
                    # On récupère l’ID enfant correspondant, fallback à 1 (Home) si introuvable
                    cat_child_id = CATEGORY_MAP.get(type_label, 1)
                    # Toujours cocher Home (1) + VINYLS (26) + la catégorie enfant choisie
                    cats_to_send = [1, 26, cat_child_id]

                    # Prépare les données à envoyer à PrestaShop, dont la liste 'category_ids'
                    data_api = {
                        'reference'   : ref,
                        'price'       : gui_line['prix'],
                        'weight'      : gui_line['poids'],
                        'quantity'    : gui_line['quantité'],
                        'name'        : f"{artist}***{title}",
                        'description' : res['data'].get('description', ''),
                        'category_ids': cats_to_send
                    }

                    # Appel API création produit
                    new_id = create_product_prestashop(data_api)
                    if new_id:
                        print(f"Produit PrestaShop créé avec ID {new_id} pour référence {ref}")
                        try:
                            update_quantity(new_id, gui_line['quantité'])
                        except Exception as e:
                            print(f"Erreur lors de la mise à jour du stock pour {ref}: {e}")

                        # ─── Upload des images associées à la référence ────────────────
                        images_folder = os.path.join(os.getcwd(), ref)
                        if os.path.isdir(images_folder):
                            for filename in os.listdir(images_folder):
                                filepath = os.path.join(images_folder, filename)
                                _, ext = os.path.splitext(filename.lower())
                                if os.path.isfile(filepath) and ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}:
                                    try:
                                        print(f"Upload de l'image '{filename}' pour le produit {new_id}…")
                                        upload_product_image(new_id, filepath)
                                    except Exception as e:
                                        print(f"Erreur lors de l'upload de '{filename}' pour {ref} : {e}")
                                else:
                                    print(f"Ignoré (extension non prise en charge ou non fichier) : '{filename}'")
                        else:
                            print(f"Pas de dossier d'images pour la référence {ref}.")
                    else:
                        print(f"Échec de la création du produit PrestaShop pour référence {ref}")

            # Quand tout est fini, on appelle le callback pour mettre à jour le GUI
            self.root.after(0, self._on_scraping_complete, results)

        except Exception as e:
            # En cas d’erreur globale, on affiche un message et on réactive le bouton
            self.root.after(0, self.view.show_error, "Erreur Scraping+API",
                            f"Une erreur est survenue lors du scraping+API : {e}")
            self.root.after(0, self.view.set_launch_button_state, 'normal')

    def _on_scraping_complete(self, results):
        """
        Gère la fin du processus de scraping.
        Affiche un message de succès et réactive le bouton 'Lancer'.
        """
        success_count = sum(1 for r in results if r.get('status') == 'Succès')
        total_count = len(results)
        self.view.show_message("Scraping Terminé", f"Scraping terminé pour {success_count}/{total_count} références.")
        self.view.set_launch_button_state('normal')
        print("Résultats du scraping :", results)

    def _update_progress(self, message):
        """
        Callback pour mettre à jour la progression du scraping/API.
        Actuellement affiche dans la console.
        """
        print(f"Progression: {message}")
        # Si vous voulez afficher la progression dans l'interface, vous pouvez mettre à jour un Label ici

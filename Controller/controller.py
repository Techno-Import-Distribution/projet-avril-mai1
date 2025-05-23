import threading
import sys
import os
import re  # Pour la validation des références

# Ajoute le répertoire courant au chemin Python pour les importations locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importe les classes Model et View
from Model.model import ScraperModel
from View.view import ScraperView


class ScraperController:
    """
    Contrôleur pour l'application de scraping de vinyles.
    Gère les interactions entre la Vue (interface utilisateur) et le Modèle (logique de scraping).
    """

    def __init__(self, root):
        self.root = root
        self.model = ScraperModel()  # Instancie le modèle
        self.view = ScraperView(root)  # Instancie la vue
        self.view.set_controller(self)  # Lie la vue au contrôleur
        self.view._create_widgets()  # Initialise les composants de l'interface

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
            # Récupération des widgets Entry pour la ligne courante
            row_entries = self.view.rows[i]

            # Validation de la référence: non vide et alphanumérique
            valid_ref = bool(row_data['référence']) and re.fullmatch(r'^[a-zA-Z0-9]+$',
                                                                     row_data['référence']) is not None
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

            if not (valid_ref and valid_prix and valid_qte and valid_poids):
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
            if item['référence'] and re.fullmatch(r'^[a-zA-Z0-9]+$', item['référence']) is not None
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
        Met à jour l'interface utilisateur une fois le scraping terminé.
        """
        try:
            # Passe une fonction de callback au modèle pour les mises à jour de progression
            results = self.model.scrape_references(references, progress_callback=self._update_progress)

            # Utilise root.after pour s'assurer que les mises à jour de l'interface se font dans le thread principal
            self.root.after(0, self._on_scraping_complete, results)
        except Exception as e:
            self.root.after(0, self.view.show_error, "Erreur Scraping",
                            f"Une erreur est survenue lors du scraping : {e}")
            self.root.after(0, self.view.set_launch_button_state, 'normal')  # Réactive le bouton en cas d'erreur

    def _update_progress(self, message):
        """
        Callback pour mettre à jour l'interface avec la progression du scraping.
        Doit être appelé via root.after si appelé depuis un thread secondaire.
        """
        # Pour l'instant, nous affichons simplement dans la console.
        # Pour une interface plus riche, on pourrait mettre à jour un Label ou une barre de progression.
        print(f"Progression: {message}")
        # Exemple de mise à jour de l'interface (nécessiterait un Label de statut dans la vue)
        # self.root.after(0, lambda: self.view.update_status_label(message))

    def _on_scraping_complete(self, results):
        """
        Gère la fin du processus de scraping.
        Affiche un message de succès et réactive le bouton 'Lancer'.
        """
        success_count = sum(1 for r in results if r.get('status') == 'Succès')
        total_count = len(results)
        self.view.show_message("Scraping Terminé", f"Scraping terminé pour {success_count}/{total_count} références.")
        self.view.set_launch_button_state('normal')  # Réactive le bouton
        # Ici, vous pourriez aussi afficher les résultats détaillés dans l'interface si désiré
        print("Résultats du scraping :", results)


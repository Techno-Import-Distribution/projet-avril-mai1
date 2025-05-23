import tkinter as tk
from tkinter import messagebox

N_MAX = 50  # Nombre maximum de lignes de produits
HIGHLIGHT_BG = '#ffcdd2' # Couleur de fond pour les champs invalides

class ScraperView:
    """
    Gère l'affichage de l'interface utilisateur Tkinter.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Import de références vinyles")

        self.rows = [] # Stocke les Entry widgets pour chaque ligne de produit
        self.controller = None # Le contrôleur sera défini plus tard

        

    def set_controller(self, controller):
        """Définit le contrôleur pour que la vue puisse lui notifier les événements."""
        self.controller = controller

    def _create_widgets(self):
        """Crée tous les widgets de l'interface utilisateur."""
        # Cadre pour le champ Fournisseur
        frame_fourn = tk.Frame(self.root, padx=10, pady=5)
        frame_fourn.pack(fill='x')
        tk.Label(frame_fourn, text="Fournisseur :").grid(row=0, column=0)
        self.entry_fournisseur = tk.Entry(frame_fourn, width=30)
        self.entry_fournisseur.grid(row=0, column=1, padx=5)
        self.entry_fournisseur.default_bg = self.entry_fournisseur.cget('bg') # Sauvegarde la couleur de fond par défaut
        self.entry_fournisseur.bind("<KeyRelease>", lambda e: self.controller.validate_all_inputs())

        # Cadre pour le nombre de produits à traiter
        frame_haut = tk.Frame(self.root, padx=10, pady=5)
        frame_haut.pack(fill='x')
        tk.Label(frame_haut, text="Nombre de produits à traiter :").grid(row=0, column=0)
        self.entry_nombre = tk.Entry(frame_haut, width=5)
        self.entry_nombre.grid(row=0, column=1, padx=5)
        self.btn_generer = tk.Button(frame_haut, text="Générer", command=self.controller.generate_lines_command)
        self.btn_generer.grid(row=0, column=2)

        # Cadre pour les lignes de produits (défilable si nécessaire)
        self.frame_lignes = tk.Frame(self.root, padx=10, pady=10)
        self.frame_lignes.pack(fill='both', expand=True)

        # Bouton Lancer
        frame_bas = tk.Frame(self.root, pady=10)
        frame_bas.pack()
        self.btn_import = tk.Button(frame_bas, text="Lancer", state='disabled', command=self.controller.launch_script_command)
        self.btn_import.pack()

        # Initialisation de l'état des validations
        self.controller.validate_all_inputs()

    def get_num_products(self):
        """Retourne le nombre de produits à générer depuis l'entrée utilisateur."""
        try:
            nb = int(self.entry_nombre.get())
            if nb < 1 or nb > N_MAX:
                raise ValueError
            return nb
        except ValueError:
            self.show_error("Erreur", f"Entrez un entier entre 1 et {N_MAX}.")
            return None

    def get_supplier(self):
        """Retourne le nom du fournisseur."""
        return self.entry_fournisseur.get().strip()

    def get_references_data(self):
        """
        Récupère les données (référence, prix, quantité, poids) de toutes les lignes.
        Retourne une liste de dictionnaires.
        """
        data = []
        for row_entries in self.rows:
            ref = row_entries[0].get().strip()
            prix_str = row_entries[1].get().strip()
            qte_str = row_entries[2].get().strip()
            poids_str = row_entries[3].get().strip()

            # Convertit les valeurs numériques, gère les erreurs de conversion
            try:
                prix = float(prix_str)
            except ValueError:
                prix = None
            try:
                quantite = int(qte_str)
            except ValueError:
                quantite = None
            try:
                poids = float(poids_str)
            except ValueError:
                poids = None

            data.append({
                'référence': ref,
                'prix': prix,
                'quantité': quantite,
                'poids': poids
            })
        return data

    def clear_product_rows(self):
        """Supprime toutes les lignes de produits existantes de l'interface."""
        for widget in self.frame_lignes.winfo_children():
            widget.destroy()
        self.rows.clear()

    def add_product_headers(self):
        """Ajoute les en-têtes de colonne pour les produits."""
        headers = ["Référence", "Prix", "Quantité", "Poids"]
        for j, h in enumerate(headers):
            lbl = tk.Label(self.frame_lignes, text=h, font=('Arial', 10, 'bold'))
            lbl.grid(row=0, column=j, padx=5, pady=2)

    def add_product_row(self, row_index):
        """Ajoute une nouvelle ligne d'entrée pour un produit."""
        row_entries = []
        for j in range(4):
            ent = tk.Entry(self.frame_lignes, width=15)
            ent.grid(row=row_index, column=j, padx=5, pady=2)
            ent.default_bg = ent.cget('bg')
            ent.bind("<KeyRelease>", lambda e: self.controller.validate_all_inputs())
            row_entries.append(ent)
        self.rows.append(row_entries)

    def highlight_entry(self, entry_widget, is_valid):
        """Met en surbrillance ou réinitialise la couleur d'un champ d'entrée."""
        if not is_valid:
            entry_widget.configure(bg=HIGHLIGHT_BG)
        else:
            entry_widget.configure(bg=entry_widget.default_bg)

    def set_launch_button_state(self, state):
        """Active ou désactive le bouton 'Lancer'."""
        self.btn_import.config(state=state)

    def show_message(self, title, message):
        """Affiche une boîte de message d'information."""
        messagebox.showinfo(title, message)

    def show_error(self, title, message):
        """Affiche une boîte de message d'erreur."""
        messagebox.showerror(title, message)

    def show_warning(self, title, message):
        """Affiche une boîte de message d'avertissement."""
        messagebox.showwarning(title, message)

    def get_all_entry_widgets(self):
        """Retourne tous les widgets Entry de la grille de produits."""
        all_entries = []
        for row_entries in self.rows:
            all_entries.extend(row_entries)
        return all_entries

    def get_supplier_entry(self):
        """Retourne le widget Entry du fournisseur."""
        return self.entry_fournisseur


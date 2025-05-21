import tkinter as tk
from tkinter import messagebox

N_MAX = 50  # Ajustez selon vos besoins
HIGHLIGHT_BG = '#ffcdd2'

def generer_lignes():
    # Lecture et validation du nombre de lignes à générer
    try:
        nb = int(entry_nombre.get())
        if nb < 1 or nb > N_MAX:
            raise ValueError
    except ValueError:
        messagebox.showerror("Erreur", f"Entrez un entier entre 1 et {N_MAX}.")
        return

    # Nettoyage de l'ancienne grille
    for widget in frame_lignes.winfo_children():
        widget.destroy()
    rows.clear()

    # Création de l'en-tête
    headers = ["Référence", "Prix", "Quantité", "Poids"]
    for j, h in enumerate(headers):
        lbl = tk.Label(frame_lignes, text=h, font=('Arial', 10, 'bold'))
        lbl.grid(row=0, column=j, padx=5, pady=2)

    # Création des lignes d'entrée
    for i in range(1, nb + 1):
        row_entries = []
        for j in range(4):
            ent = tk.Entry(frame_lignes, width=15)
            ent.grid(row=i, column=j, padx=5, pady=2)
            ent.default_bg = ent.cget('bg')
            ent.bind("<KeyRelease>", lambda e: validate_all())
            row_entries.append(ent)
        rows.append(row_entries)

    validate_all()  # Met à jour l’état du bouton et surbrillance

def validate_all():
    """Valide le fournisseur et toutes les lignes, et active/désactive 'Lancer'."""
    # Validation du champ Fournisseur
    supp = entry_fournisseur.get().strip()
    valid_supp = bool(supp) and len(supp) <= 100
    if not valid_supp:
        entry_fournisseur.configure(bg=HIGHLIGHT_BG)
    else:
        entry_fournisseur.configure(bg=entry_fournisseur.default_bg)

    # Validation des lignes
    all_valid = valid_supp
    for row in rows:
        # Récupération des valeurs
        ref, prix_str, qte_str, poids_str = [ent.get().strip() for ent in row]

        valid_ref = bool(ref and ref.isalnum())
        try:
            float(prix_str)
            valid_prix = True
        except ValueError:
            valid_prix = False
        valid_qte = qte_str.isdigit() and bool(qte_str)
        try:
            float(poids_str)
            valid_poids = True
        except ValueError:
            valid_poids = False

        # Surbrillance seulement si non vide et invalide
        for ent, valid in zip(row, [valid_ref, valid_prix, valid_qte, valid_poids]):
            if ent.get().strip() and not valid:
                ent.configure(bg=HIGHLIGHT_BG)
            else:
                ent.configure(bg=ent.default_bg)

        if not (valid_ref and valid_prix and valid_qte and valid_poids):
            all_valid = False

    # Activation / désactivation du bouton "Lancer"
    btn_import.config(state=('normal' if all_valid and rows else 'disabled'))

def lancer_script():
    """Prépare et lance le script d'import (stub)."""
    fournisseur = entry_fournisseur.get().strip()
    data = []
    for row in rows:
        data.append({
            'fournisseur': fournisseur,
            'référence': row[0].get().strip(),
            'prix': float(row[1].get().strip()),
            'quantité': int(row[2].get().strip()),
            'poids': float(row[3].get().strip())
        })
    print("Données prêtes à l'import :", data)
    messagebox.showinfo("Import", "Les données sont prêtes à être importées.")

# --- Construction de l'interface ---

root = tk.Tk()
root.title("Import de références vinyles")

# Fournisseur en haut
frame_fourn = tk.Frame(root, padx=10, pady=5)
frame_fourn.pack(fill='x')
tk.Label(frame_fourn, text="Fournisseur :").grid(row=0, column=0)
entry_fournisseur = tk.Entry(frame_fourn, width=30)
entry_fournisseur.grid(row=0, column=1, padx=5)
entry_fournisseur.default_bg = entry_fournisseur.cget('bg')
entry_fournisseur.bind("<KeyRelease>", lambda e: validate_all())

# Nombre de produits
frame_haut = tk.Frame(root, padx=10, pady=5)
frame_haut.pack(fill='x')
tk.Label(frame_haut, text="Nombre de produits à traiter :").grid(row=0, column=0)
entry_nombre = tk.Entry(frame_haut, width=5)
entry_nombre.grid(row=0, column=1, padx=5)
tk.Button(frame_haut, text="Générer", command=generer_lignes).grid(row=0, column=2)

# Zone des lignes
frame_lignes = tk.Frame(root, padx=10, pady=10)
frame_lignes.pack(fill='both', expand=True)
rows = []

# Bouton Lancer
frame_bas = tk.Frame(root, pady=10)
frame_bas.pack()
btn_import = tk.Button(frame_bas, text="Lancer", state='disabled', command=lancer_script)
btn_import.pack()

# Initialisation de l’état
validate_all()

root.mainloop()

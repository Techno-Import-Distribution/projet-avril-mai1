import tkinter as tk
from tkinter import messagebox

N_MAX = 50  # à ajuster si nécessaire

def generer_lignes():
    try:
        nb = int(entry_nombre.get())
        if nb < 1 or nb > N_MAX:
            raise ValueError
    except ValueError:
        messagebox.showerror("Erreur", f"Veuillez entrer un entier entre 1 et {N_MAX}.")
        return

    for widget in frame_lignes.winfo_children():
        widget.destroy()  # Nettoie les anciennes lignes

    for i in range(nb):
        ligne = tk.Entry(frame_lignes)
        ligne.grid(row=i, column=0, pady=2)

# Fenêtre principale
root = tk.Tk()
root.title("Choix du nombre de produits")

# Barre de saisie + bouton
frame_haut = tk.Frame(root, padx=10, pady=10)
frame_haut.pack()

label = tk.Label(frame_haut, text="Nombre de produits à traiter :")
label.grid(row=0, column=0)

entry_nombre = tk.Entry(frame_haut, width=5)
entry_nombre.grid(row=0, column=1, padx=5)

bouton = tk.Button(frame_haut, text="Lancer", command=generer_lignes)
bouton.grid(row=0, column=2)

# Zone d'affichage des lignes
frame_lignes = tk.Frame(root, padx=10, pady=10)
frame_lignes.pack()

root.mainloop()

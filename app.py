import tkinter as tk
from Controller.controller import ScraperController

def main():
    """
    Fonction principale pour lancer l'application Tkinter.
    """
    root = tk.Tk() # Crée la fenêtre principale Tkinter
    app = ScraperController(root) # Instancie le contrôleur, qui initialise la vue et le modèle
    root.mainloop() # Lance la boucle d'événements Tkinter

if __name__ == "__main__":
    main() # Exécute la fonction main si le script est lancé directement

# controleur/controller.py

_collected_data = None

def lancer_script(fournisseur, rows):
    """
    Stocke toutes les données entrées dans l'UI pour le modèle.
    Args:
        fournisseur (str): nom du fournisseur
        rows (list of list of tk.Entry): les lignes de saisie de l'UI
    Returns:
        list of dict: les enregistrements collectés
    """
    global _collected_data
    data = []
    for row in rows:
        data.append({
            'fournisseur': fournisseur,
            'référence': row[0].get().strip(),
            'prix':    float(row[1].get().strip()),
            'quantité': int(row[2].get().strip()),
            'poids':   float(row[3].get().strip())
        })
    _collected_data = data
    return data

def get_collected_data():
    """Renvoie les données stockées par le dernier appel à lancer_script."""
    return _collected_data

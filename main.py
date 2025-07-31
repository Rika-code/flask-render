from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime, timedelta, time

app = Flask(__name__)
CORS(app)

entrepots = {}
historique_depots = []
VENTES_FILE = "ventes.json"

# -------------------------- Base Employé (SQLite) ------------------------ #
DB_PATH = "employes.db"

def get_employes_actifs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT nom, prenom, grade FROM employes WHERE statut = 'actif'")
    results = cursor.fetchall()
    conn.close()
    return [{"nom": n, "prenom": p, "grade": g} for (n, p, g) in results]

@app.route("/api/employes", methods=["GET"])
def api_employes():
    return jsonify(get_employes_actifs())

# -------------------------- Gestion Ventes ------------------------ #
def charger_ventes():
    if not os.path.exists(VENTES_FILE):
        return [], datetime.now()
    with open(VENTES_FILE, "r") as f:
        contenu = json.load(f)
        return contenu.get("ventes", []), datetime.fromisoformat(contenu.get("derniere_reset"))

def sauvegarder_ventes(ventes, derniere_reset):
    with open(VENTES_FILE, "w") as f:
        json.dump({
            "ventes": ventes,
            "derniere_reset": derniere_reset.isoformat()
        }, f, indent=2)

def prochain_dimanche_23h():
    today = datetime.now()
    jours_jusqua_dimanche = (6 - today.weekday()) % 7
    prochain = today + timedelta(days=jours_jusqua_dimanche)
    return datetime.combine(prochain.date(), time(23, 0))

# Chargement initial des ventes
ventes, derniere_reset = charger_ventes()

@app.before_request
def verifier_reset_hebdo():
    global ventes, derniere_reset
    maintenant = datetime.now()
    prochain_reset = prochain_dimanche_23h()

    if derniere_reset < prochain_reset and maintenant >= prochain_reset:
        print("🧹 Réinitialisation automatique des quotas (dimanche 23h)")
        ventes = []
        derniere_reset = maintenant
        sauvegarder_ventes(ventes, derniere_reset)

# -------------------------- Webhooks ------------------------ #
@app.route("/webhook", methods=["POST"])
def recevoir_donnee():
    data = request.json
    joueur = data.get("joueur")
    entrepot = data.get("entrepot")
    item = data.get("item")
    quantite = data.get("quantite")
    action = data.get("action")

    if not all([joueur, entrepot, item, quantite, action]):
        return jsonify({"erreur": "donnée manquante"}), 400

    if entrepot not in entrepots:
        entrepots[entrepot] = {}

    current_qte = entrepots[entrepot].get(item, 0)

    if action == "déposé":
        entrepots[entrepot][item] = current_qte + quantite
        if item.lower() in ["tomate", "emmental"]:
            historique_depots.append({
                "joueur": joueur,
                "item": item.lower(),
                "quantite": quantite
            })
    elif action == "retiré":
        entrepots[entrepot][item] = max(0, current_qte - quantite)
    else:
        return jsonify({"erreur": "action invalide"}), 400

    print(f"📦 {joueur} a {action} {quantite}x {item} dans l'entrepôt #{entrepot}")
    return jsonify({"message": "reçu"}), 200

@app.route("/webhook/ventes", methods=["POST"])
def recevoir_vente():
    data = request.json
    vendeur = data.get("vendeur")
    item = data.get("item")
    quantite = data.get("quantite")

    if not all([vendeur, item, quantite]):
        return jsonify({"erreur": "vente incomplète"}), 400

    ventes.append({
        "vendeur": vendeur,
        "item": item,
        "quantite": quantite
    })

    sauvegarder_ventes(ventes, derniere_reset)  # Sauvegarde à chaque ajout

    print(f"📄 Vente enregistrée : {vendeur} a vendu {quantite}x {item}")
    return jsonify({"message": "vente reçue"}), 200

# -------------------------- API Public ------------------------ #
@app.route("/api/ventes", methods=["GET"])
def get_ventes():
    return jsonify(ventes)

@app.route("/api/coffres", methods=["GET"])
def get_entrepots():
    return jsonify(entrepots)

@app.route("/api/depots", methods=["GET"])
def get_depots():
    return jsonify(historique_depots)

@app.route("/")
def home():
    return "Hello Railway!"

# -------------------------- Lancement ------------------------ #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway fournit le port
    app.run(host="0.0.0.0", port=port)

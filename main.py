from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime, timedelta, time

app = Flask(__name__)
CORS(app)

# -------------------------- CONFIG -------------------------- #
DB_PATH = "employes.db"
VENTES_FILE = "ventes.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "reset06")

# -------------------------- STOCKAGE ------------------------ #
coffres = {}   # { "Distilling Co.": { "Sac De Céréales": 48 } }
ventes = []
derniere_reset = datetime.now()

# -------------------------- VENTES -------------------------- #
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

ventes, derniere_reset = charger_ventes()

@app.route("/api/ventes/save", methods=["POST"])
def force_save_ventes():
    sauvegarder_ventes(ventes, derniere_reset)
    return jsonify({"message": "ventes sauvegardées"}), 200


# ---------------------- DB EMPLOYÉS ------------------------- #
def get_employes_actifs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nom, prenom, grade FROM employes WHERE statut = 'actif'"
    )
    results = cursor.fetchall()
    conn.close()
    return [{"nom": n, "prenom": p, "grade": g} for (n, p, g) in results]

# -------------------------- API ------------------------------ #
@app.route("/api/coffres/<path:entrepot>/<path:produit>", methods=["DELETE", "OPTIONS"])
def delete_coffre_produit(entrepot, produit):
    # Préflight CORS
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response, 200

    # Suppression réelle
    if entrepot in coffres and produit in coffres[entrepot]:
        del coffres[entrepot][produit]

        if not coffres[entrepot]:
            del coffres[entrepot]

        print(f"🗑️ Produit supprimé : [{entrepot}] {produit}")
        return jsonify({"message": "Produit supprimé"}), 200

    return jsonify({"error": "Produit non trouvé"}), 404

@app.route("/api/employes", methods=["GET"])
def api_employes():
    return jsonify(get_employes_actifs())

@app.route("/api/ventes", methods=["GET"])
def api_ventes():
    return jsonify(ventes)

@app.route("/api/coffres", methods=["GET"])
def api_coffres():
    return jsonify(coffres)

@app.route("/api/ventes/reset", methods=["POST"])
def reset_ventes():
    data = request.json
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"erreur": "Mot de passe incorrect"}), 403

    global ventes, derniere_reset
    ventes = []
    derniere_reset = datetime.now()
    sauvegarder_ventes(ventes, derniere_reset)

    return jsonify({"message": "ventes réinitialisées"}), 200

# ------------------------ WEBHOOK COFFRE -------------------- #
@app.route("/webhook", methods=["POST"])
def recevoir_coffre():
    data = request.json or {}

    joueur = data.get("joueur", "inconnu")
    job = data.get("job", "global")
    item = data.get("item_label")
    quantite = data.get("quantite")
    action = data.get("action")

    # champs réellement indispensables
    if not all([item, quantite, action]):
        print("❌ Données manquantes :", data)
        return jsonify({"erreur": "donnée manquante"}), 400

    quantite = int(quantite)

    if job not in coffres:
        coffres[job] = {}

    actuel = coffres[job].get(item, 0)

    if action == "dépot":
        coffres[job][item] = actuel + quantite
    elif action == "retrait":
        coffres[job][item] = max(0, actuel - quantite)
    else:
        return jsonify({"erreur": "action invalide"}), 400

    print(f"📦 [{job}] {joueur} a {action} {quantite}x {item}")
    return jsonify({"message": "coffre reçu"}), 200


# ------------------------ WEBHOOK VENTES -------------------- #
@app.route("/webhook/ventes", methods=["POST"])
def recevoir_vente():
    data = request.json

    ventes.append({
        "vendeur": data.get("vendeur"),
        "item": data.get("item_label"),
        "item_id": data.get("item_id"),
        "quantite": data.get("quantite"),
        "montant_total": data.get("montant_total"),
        "montant_societe": data.get("montant_societe"),
        "date": data.get("date")
    })

    sauvegarder_ventes(ventes, derniere_reset)

    print(
        f"{data.get('vendeur')} → "
        f"{data.get('quantite')}x {data.get('item_label')}"
    )

    return jsonify({"message": "vente reçue"}), 200

# -------------------------- HOME ----------------------------- #
@app.route("/")
def home():
    return "Hello Railway!"

# ------------------------ LANCEMENT -------------------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

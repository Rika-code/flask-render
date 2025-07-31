import discord
import aiohttp
import re

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

WEBHOOK_URL = "http://127.0.0.1:5000/webhook"

ENTREPOTS_AUTORISES = [
    "garage", "boîte-de-nuit", "echelle", "limonade-1", "limonade-2", "limonade-3",
    "pneu-1", "pneu-2", "wey", "video-games", "goyave", "kebab"
]

@client.event
async def on_ready():
    print(f'✅ Connecté en tant que {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user or not message.embeds:
        return

    channel_name = message.channel.name.lower()
    if not channel_name.startswith("logs-"):
        return

    # 🔁 Gestion des entrepôts
    if channel_name.replace("logs-", "") in ENTREPOTS_AUTORISES:
        entrepot = channel_name.replace("logs-", "")
        print(f"📦 Message reçu pour l'entrepôt '{entrepot}'")

        for embed in message.embeds:
            texte = embed.description
            if not texte:
                continue

            print(f"🧩 Texte à parser : {texte}")

            pattern1 = r"\*\*(.+?)\*\* a (déposé|retiré) (\d+)x (.+)"
            pattern2 = r"(.+?) a (déposé|retiré) (\d+)x (.+)"

            match = re.match(pattern1, texte) or re.match(pattern2, texte)
            if not match:
                print("❌ Aucun pattern reconnu")
                continue

            joueur, action, quantite, item = match.groups()
            data = {
                "joueur": joueur.strip(" *"),
                "entrepot": entrepot,
                "item": item.strip(),
                "quantite": int(quantite),
                "action": action
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, json=data) as resp:
                    print(f"✅ Envoyé à Flask: {data}, status: {resp.status}")

    # 💰 Gestion des ventes
    elif channel_name == "logs-vente":
        print("🧾 Message reçu dans le salon de vente.")

        for embed in message.embeds:
            texte = embed.description
            if not texte:
                continue

            print(f"🧾 Texte de vente : {texte}")

            vente_pattern = r"Vente de (\d+)x (.+?) pour \d+\$ par (.+?)\."
            match = re.match(vente_pattern, texte)

            if not match:
                print("❌ Pattern de vente non reconnu.")
                continue

            quantite, item, vendeur = match.groups()
            vente_data = {
                "vendeur": vendeur.strip(),
                "quantite": int(quantite),
                "item": item.strip()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{WEBHOOK_URL}/ventes", json=vente_data) as resp:
                    print(f"✅ Vente envoyée à Flask: {vente_data}, status: {resp.status}")

                

client.run('MTM5MjgwNDE2OTM3MDQzOTc1Mg.GdhD8U.GGyWwYiOhIYSH5IrEQOq9QXNAUtGMhdSgnoNF0')

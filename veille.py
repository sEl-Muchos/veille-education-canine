import os
import feedparser
from google import genai

FEEDS = [
    "https://www.centrale-canine.fr/rss.xml",
    "https://www.veterinaire.fr/rss.xml",
]

articles = []

for url in FEEDS:
    try:
        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", "")
            })

    except Exception as e:
        print(f"Erreur avec {url}: {e}")

if not articles:
    print("Aucun article récupéré.")
    with open("digest.md", "w", encoding="utf-8") as f:
        f.write("# Veille éducation canine\n\nAucun nouvel article récupéré.")
    raise SystemExit(0)

texte = "\n\n".join(
    f"TITRE : {a['title']}\n"
    f"CONTENU : {a['summary']}\n"
    f"LIEN : {a['link']}"
    for a in articles
)

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

prompt = f"""
Tu es un expert professionnel de l'éducation canine.

Analyse les articles ci-dessous.

Conserve uniquement les informations réellement utiles à un éducateur canin professionnel.

Catégories :
- Éducation canine
- Comportement
- Science
- Santé
- Réglementation
- Actualité canine
- Métier et formation

Pour chaque article retenu, indique :

TITRE :
SOURCE :
CATÉGORIE :
RÉSUMÉ :
POURQUOI C'EST UTILE :
LIEN ORIGINAL :

Ne fabrique aucune information.
Ne crée aucun lien.
Utilise uniquement les informations fournies.

ARTICLES :
{texte}
"""

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt
)

with open("digest.md", "w", encoding="utf-8") as f:
    f.write("# 🐕 Veille éducation canine\n\n")
    f.write(response.text)

print("Veille terminée.")

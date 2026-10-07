import os
import feedparser
from google import genai

FEEDS = [
    "https://www.centrale-canine.fr/rss.xml",
    "https://www.veterinaire.fr/rss.xml",
]

articles = []

for url in FEEDS:
    feed = feedparser.parse(url)
    for entry in feed.entries[:10]:
        articles.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "link": entry.get("link", ""),
        })

texte = "\n\n".join(
    f"TITRE: {a['title']}\nRESUME: {a['summary']}\nLIEN: {a['link']}"
    for a in articles
)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = f"""
Tu es un expert professionnel de l'éducation canine.

Analyse les articles ci-dessous.

Garde uniquement ceux qui présentent un intérêt réel pour :
- éducation canine
- comportement du chien
- méthodes d'apprentissage
- bien-être et santé du chien
- recherche scientifique
- réglementation
- actualité professionnelle canine

Pour chaque article retenu :
1. donne le titre
2. indique la catégorie
3. fais un résumé de 3 à 5 phrases
4. explique en une phrase pourquoi c'est utile à un éducateur canin
5. conserve le lien original

Ne fabrique aucune information.

ARTICLES :
{texte}
"""

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt
)

with open("digest.md", "w", encoding="utf-8") as f:
    f.write("# Veille éducation canine\n\n")
    f.write(response.text)

print(response.text)

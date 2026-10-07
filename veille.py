import os
import re
import html
import feedparser
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from google import genai


# ============================================================
# CONFIGURATION
# ============================================================

# Sites importants à surveiller via Google News RSS.
# Cela permet de surveiller aussi des sites qui n'ont pas
# de flux RSS public facilement exploitable.

GOOGLE_NEWS_SOURCES = [
    ("MFEC", "site:mfec.fr chien"),
    ("Vox Animae", "site:vox-animae.com chien"),
    ("Centrale Canine", "site:centrale-canine.fr chien"),
    ("Ordre des vétérinaires", "site:veterinaire.fr chien"),
    ("Ministère de l'Agriculture", "site:agriculture.gouv.fr chien"),
    ("ANSES", "site:anses.fr chien animal"),
    ("Légifrance", "site:legifrance.gouv.fr chien animal"),
    ("Service-Public", "site:service-public.fr chien animal"),
]

# Recherches scientifiques PubMed.
PUBMED_SEARCHES = [
    "dog behavior",
    "canine behavior",
    "dog training",
    "canine training",
    "dog welfare",
    "canine welfare",
    "dog aggression",
    "dog anxiety",
    "dog fear",
    "dog cognition",
    "dog human interaction",
    "dog enrichment",
]

# Mots-clés permettant d'éliminer une partie du bruit.
KEYWORDS = [
    "chien",
    "canin",
    "canine",
    "dog",
    "comportement",
    "behavior",
    "behaviour",
    "éducation",
    "education",
    "training",
    "dressage",
    "agression",
    "aggressive",
    "anxiété",
    "anxiety",
    "peur",
    "fear",
    "stress",
    "bien-être",
    "welfare",
    "socialisation",
    "socialization",
    "cognition",
    "apprentissage",
    "learning",
    "renforcement",
    "reinforcement",
    "réactivité",
    "reactivity",
    "vétérinaire",
    "veterinary",
    "santé",
    "health",
    "réglementation",
    "regulation",
    "formation",
]

# Nombre maximum d'articles envoyés à Gemini.
MAX_ARTICLES_FOR_AI = 40

# On regarde les nouveautés des 72 dernières heures.
# Cela évite de perdre un article si GitHub a un problème
# pendant une journée.
MAX_AGE_HOURS = 72


# ============================================================
# OUTILS
# ============================================================

def clean_text(text):
    """Nettoie le HTML et les espaces inutiles."""
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_relevant(title, summary):
    """Filtre grossièrement les articles avant Gemini."""
    text = f"{title} {summary}".lower()

    return any(keyword.lower() in text for keyword in KEYWORDS)


def parse_date(entry):
    """Retourne une date UTC si disponible."""
    try:
        if entry.get("published_parsed"):
            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            )

        if entry.get("updated_parsed"):
            return datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            )
    except Exception:
        pass

    return datetime.now(timezone.utc)


def add_article(articles, title, summary, link, source, published=None):
    """Ajoute un article en évitant les doublons."""
    title = clean_text(title)
    summary = clean_text(summary)
    link = link.strip() if link else ""

    if not title or not link:
        return

    if not is_relevant(title, summary):
        return

    now = datetime.now(timezone.utc)

    if published is None:
        published = now

    # Évite les articles trop anciens.
    if now - published > timedelta(hours=MAX_AGE_HOURS):
        return

    # Déduplication par URL et titre.
    normalized_title = title.lower()

    for article in articles:
        if article["link"] == link:
            return

        if article["title"].lower() == normalized_title:
            return

    articles.append({
        "title": title,
        "summary": summary[:3000],
        "link": link,
        "source": source,
        "published": published,
    })


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def collect_google_news(articles):
    print("Recherche des actualités web...")

    for source_name, query in GOOGLE_NEWS_SOURCES:

        try:
            rss_url = (
                "https://news.google.com/rss/search?"
                f"q={quote(query)}"
                "&hl=fr"
                "&gl=FR"
                "&ceid=FR:fr"
            )

            feed = feedparser.parse(rss_url)

            print(
                f"  {source_name}: "
                f"{len(feed.entries)} résultats trouvés"
            )

            for entry in feed.entries[:15]:

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                published = parse_date(entry)

                add_article(
                    articles,
                    title,
                    summary,
                    link,
                    source_name,
                    published
                )

        except Exception as e:
            print(
                f"  Erreur {source_name}: {e}"
            )


# ============================================================
# PUBMED
# ============================================================

def collect_pubmed(articles):
    print("Recherche scientifique PubMed...")

    for search in PUBMED_SEARCHES:

        try:
            rss_url = (
                "https://pubmed.ncbi.nlm.nih.gov/"
                "?term="
                + quote(search)
                + "&format=rss"
            )

            feed = feedparser.parse(rss_url)

            print(
                f"  PubMed [{search}]: "
                f"{len(feed.entries)} résultats"
            )

            for entry in feed.entries[:8]:

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                published = parse_date(entry)

                add_article(
                    articles,
                    title,
                    summary,
                    link,
                    "PubMed",
                    published
                )

        except Exception as e:
            print(
                f"  Erreur PubMed [{search}]: {e}"
            )


# ============================================================
# GEMINI
# ============================================================

def analyze_with_gemini(articles):

    if not articles:
        return (
            "# 🐕 Veille éducation canine\n\n"
            "Aucune nouvelle information pertinente "
            "n'a été détectée."
        )

    # Tri par date décroissante.
    articles.sort(
        key=lambda x: x["published"],
        reverse=True
    )

    articles = articles[:MAX_ARTICLES_FOR_AI]

    texte = "\n\n".join(
        f"""
ARTICLE {i}

SOURCE :
{article['source']}

TITRE :
{article['title']}

DATE :
{article['published'].strftime('%Y-%m-%d')}

RÉSUMÉ / EXTRAIT :
{article['summary']}

LIEN :
{article['link']}
"""
        for i, article in enumerate(articles, 1)
    )

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"]
    )

    prompt = f"""
Tu es un expert professionnel de l'éducation canine,
du comportement animal et de la veille scientifique.

Tu analyses une sélection d'articles récents.

OBJECTIF :
Créer une veille réellement utile à un éducateur canin
professionnel.

IMPORTANT :
- Ne fabrique aucune information.
- Ne fabrique aucun lien.
- Utilise uniquement les informations présentes dans les articles.
- Conserve les liens originaux.
- Élimine les doublons.
- Élimine les articles manifestement sans intérêt professionnel.
- Ne transforme pas une opinion en fait scientifique.
- Signale clairement lorsqu'un article présente une étude
  scientifique.
- Privilégie les informations nouvelles, solides et
  directement applicables.

CATÉGORIES :

🐕 ÉDUCATION CANINE
🧠 COMPORTEMENT
🔬 SCIENCE
🩺 SANTÉ
⚖️ RÉGLEMENTATION
🇫🇷 ACTUALITÉ CANINE
💼 MÉTIER & FORMATION

POUR CHAQUE ARTICLE RETENU :

### TITRE

**Source :**
Nom de la source

**Catégorie :**
Une des catégories ci-dessus

**Résumé :**
3 à 6 phrases maximum.

**Pourquoi c'est utile pour un éducateur canin :**
1 à 3 phrases concrètes.

**Niveau de confiance :**
- Élevé : source institutionnelle ou étude scientifique
- Moyen : source professionnelle reconnue
- À vérifier : source moins solide

**Lien original :**
Lien fourni dans les données.

Ne crée surtout pas de lien.

Ne garde que les informations réellement utiles.

Commence directement par :

# 🐕 Veille éducation canine

Puis organise les résultats par ordre d'intérêt professionnel.

ARTICLES À ANALYSER :

{texte}
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        print(
            f"Erreur Gemini : {e}"
        )

        # Même si Gemini tombe en panne,
        # on conserve les articles récupérés.
        result = [
            "# 🐕 Veille éducation canine",
            "",
            "⚠️ Analyse Gemini indisponible.",
            "",
            "## Articles détectés",
            ""
        ]

        for article in articles:
            result.append(
                f"### {article['title']}"
            )
            result.append(
                f"**Source :** {article['source']}"
            )
            result.append(
                f"**Lien :** {article['link']}"
            )
            result.append("")

        return "\n".join(result)


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    print("=" * 60)
    print("🐕 VEILLE AUTOMATIQUE ÉDUCATION CANINE")
    print("=" * 60)

    articles = []

    collect_google_news(articles)
    collect_pubmed(articles)

    print()
    print(
        f"Articles pertinents détectés : "
        f"{len(articles)}"
    )

    digest = analyze_with_gemini(articles)

    with open(
        "digest.md",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(digest)

    print()
    print("✅ digest.md mis à jour.")
    print("✅ Veille terminée.")


if __name__ == "__main__":
    main()

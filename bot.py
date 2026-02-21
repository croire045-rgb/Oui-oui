#!/usr/bin/env python3
"""
🤖 Bot Telegram - Actualités automatiques
Version GitHub Actions : s'exécute une fois puis s'arrête
Le scheduling est géré par GitHub Actions (cron toutes les heures)
"""

import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
import feedparser
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import asyncio

# ══════════════════════════════════════════════════════════
#  CONFIGURATION (via variables d'environnement GitHub Secrets)
# ══════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL_ID     = os.environ.get("CHANNEL_ID", "@news045_au")
NEWSAPI_KEY    = os.environ.get("NEWSAPI_KEY", "")
GNEWS_KEY      = os.environ.get("GNEWS_KEY", "")
PEXELS_KEY     = os.environ.get("PEXELS_KEY", "")

POSTED_FILE = "posted_articles.json"

# ══════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  GESTION DES ARTICLES DÉJÀ POSTÉS
# ══════════════════════════════════════════════════════════
def load_posted() -> set:
    if Path(POSTED_FILE).exists():
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted: set):
    data = list(posted)[-500:]
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ══════════════════════════════════════════════════════════
#  SOURCE 1 : NEWSAPI.ORG
# ══════════════════════════════════════════════════════════
def fetch_newsapi() -> list:
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"apiKey": NEWSAPI_KEY, "language": "fr", "pageSize": 15},
            timeout=10
        )
        data = r.json()
        if data.get("status") != "ok":
            return []
        articles = []
        for a in data.get("articles", []):
            if a.get("title") and a.get("url") and "[Removed]" not in a.get("title", ""):
                articles.append({
                    "title":       a["title"].strip(),
                    "description": a.get("description") or "",
                    "url":         a["url"],
                    "image":       a.get("urlToImage"),
                    "source":      a.get("source", {}).get("name", "Actualités")
                })
        log.info(f"NewsAPI ✅ {len(articles)} articles")
        return articles
    except Exception as e:
        log.error(f"NewsAPI ❌ {e}")
        return []

# ══════════════════════════════════════════════════════════
#  SOURCE 2 : GNEWS.IO
# ══════════════════════════════════════════════════════════
def fetch_gnews() -> list:
    try:
        r = requests.get(
            "https://gnews.io/api/v4/top-headlines",
            params={"token": GNEWS_KEY, "lang": "fr", "country": "fr", "max": 15},
            timeout=10
        )
        data = r.json()
        articles = []
        for a in data.get("articles", []):
            if a.get("title") and a.get("url"):
                articles.append({
                    "title":       a["title"].strip(),
                    "description": a.get("description") or "",
                    "url":         a["url"],
                    "image":       a.get("image"),
                    "source":      a.get("source", {}).get("name", "Actualités")
                })
        log.info(f"GNews ✅ {len(articles)} articles")
        return articles
    except Exception as e:
        log.error(f"GNews ❌ {e}")
        return []

# ══════════════════════════════════════════════════════════
#  SOURCE 3 : RSS FEEDS
# ══════════════════════════════════════════════════════════
RSS_FEEDS = [
    # 🌍 Actualités générales
    ("Le Monde",          "https://www.lemonde.fr/rss/une.xml"),
    ("Le Figaro",         "https://www.lefigaro.fr/rss/figaro_actualites.xml"),
    ("France Info",       "https://www.francetvinfo.fr/titres.rss"),
    ("RFI",               "https://www.rfi.fr/fr/rss"),
    ("20 Minutes",        "https://www.20minutes.fr/feeds/rss/une"),
    # 💰 Économie & Finance
    ("Les Échos",         "https://www.lesechos.fr/rss/rss_une.xml"),
    ("BFM Business",      "https://www.bfmtv.com/rss/economie/"),
    ("Le Monde Économie", "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Capital",           "https://www.capital.fr/feed"),
    ("Boursorama",        "https://www.boursorama.com/rss/actualites/"),
]

def fetch_rss() -> list:
    articles = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                image = None
                if hasattr(entry, "media_content") and entry.media_content:
                    image = entry.media_content[0].get("url")
                elif hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                    image = entry.media_thumbnail[0].get("url")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    enc = entry.enclosures[0]
                    if enc.get("type", "").startswith("image"):
                        image = enc.get("url")
                title = entry.get("title", "").strip()
                desc  = re.sub(r'<[^>]+>', '', entry.get("summary", "")).strip()
                link  = entry.get("link", "")
                if title and link:
                    articles.append({
                        "title": title, "description": desc,
                        "url": link, "image": image, "source": source
                    })
        except Exception as e:
            log.error(f"RSS {source} ❌ {e}")
    log.info(f"RSS ✅ {len(articles)} articles")
    return articles

# ══════════════════════════════════════════════════════════
#  IMAGE DE SECOURS VIA PEXELS
# ══════════════════════════════════════════════════════════
def get_pexels_image(query: str) -> Optional[str]:
    try:
        mots = re.sub(r'[^a-zA-ZÀ-ÿ\s]', ' ', query).split()[:3]
        q = " ".join(mots) or "actualités monde"
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": q, "per_page": 8, "orientation": "landscape"},
            timeout=10
        )
        photos = r.json().get("photos", [])
        if photos:
            return random.choice(photos)["src"]["large"]
    except Exception as e:
        log.error(f"Pexels ❌ {e}")
    return None

def is_valid_image_url(url: str) -> bool:
    if not url:
        return False
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        return r.status_code == 200 and "image" in ct
    except Exception:
        return False

# ══════════════════════════════════════════════════════════
#  FORMATAGE DU MESSAGE
# ══════════════════════════════════════════════════════════
def format_message(article: dict) -> str:
    title  = article["title"]
    desc   = re.sub(r'<[^>]+>', '', article.get("description", "")).strip()
    url    = article["url"]
    source = article.get("source", "")
    now    = datetime.now().strftime("%d/%m/%Y • %Hh%M")
    if len(desc) > 350:
        desc = desc[:347].rsplit(" ", 1)[0] + "..."
    msg = f"📰 <b>{title}</b>\n\n"
    if desc:
        msg += f"{desc}\n\n"
    msg += f"🔗 <a href='{url}'>Lire l'article complet</a>\n\n"
    msg += f"📡 <i>{source} • {now}</i>\n\n"
    msg += f"➖➖➖➖➖➖➖➖➖➖\n"
    msg += f"👉 <i>Tu aimes ces infos ? Abonne-toi à @news045_au et partage à tes amis !</i> 🙏"
    return msg

# ══════════════════════════════════════════════════════════
#  FONCTION PRINCIPALE
# ══════════════════════════════════════════════════════════
async def main():
    log.info("🤖 Bot démarré - GitHub Actions")

    # Récupère les articles
    articles = fetch_newsapi()
    if len(articles) < 3:
        articles += fetch_gnews()
    if len(articles) < 3:
        articles += fetch_rss()
    random.shuffle(articles)

    if not articles:
        log.error("❌ Aucun article trouvé !")
        return

    # Évite les doublons
    posted  = load_posted()
    article = None
    for a in articles:
        if a["url"] not in posted:
            article = a
            break

    if not article:
        log.info("🔄 Reset du cache des articles")
        posted.clear()
        article = articles[0]

    log.info(f"📄 Article : {article['title'][:60]}...")

    # Image
    image_url = article.get("image")
    if image_url and not is_valid_image_url(image_url):
        image_url = None
    if not image_url:
        image_url = get_pexels_image(article["title"])

    message = format_message(article)
    bot = Bot(token=TELEGRAM_TOKEN)

    try:
        if image_url:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=message,
                parse_mode=ParseMode.HTML
            )
            log.info("✅ Article posté avec image !")
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            log.info("✅ Article posté (sans image) !")

        posted.add(article["url"])
        save_posted(posted)

    except TelegramError as e:
        log.error(f"Telegram ❌ {e}")
        if image_url:
            try:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                posted.add(article["url"])
                save_posted(posted)
                log.info("✅ Posté sans image (fallback OK)")
            except TelegramError as e2:
                log.error(f"Erreur fatale ❌ {e2}")

if __name__ == "__main__":
    asyncio.run(main())

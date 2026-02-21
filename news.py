#!/usr/bin/env python3
"""
🤖 Bot Telegram - Actualités automatiques toutes les heures
Canal : @news045_au
"""

import asyncio
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ══════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════
TELEGRAM_TOKEN = "7859076867:AAFYncHzIyWQy4e33sdOBWqNT99o1y071Dk"
CHANNEL_ID     = "@news045_au"
NEWSAPI_KEY    = "53eceee868644534be1e9a9e4c603c93"
GNEWS_KEY      = "b3e2694bfdd266d8bf88002d5f139316"
PEXELS_KEY     = "XUxuIECreEKPoSl8oE6YiyEilIjPSqo1pc3u39FeVbzpHLEMSfDkZ46B"

POSTED_FILE    = "posted_articles.json"
INTERVAL_HOURS = 1  # Modifier ici pour changer la fréquence

# ══════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  GESTION DES ARTICLES DÉJÀ POSTÉS (évite les doublons)
# ══════════════════════════════════════════════════════════
def load_posted() -> set:
    if Path(POSTED_FILE).exists():
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted: set):
    data = list(posted)[-500:]  # Garde seulement les 500 derniers
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ══════════════════════════════════════════════════════════
#  SOURCE 1 : NEWSAPI.ORG
# ══════════════════════════════════════════════════════════
def fetch_newsapi() -> list:
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={
                "apiKey": NEWSAPI_KEY,
                "language": "fr",
                "pageSize": 15
            },
            timeout=10
        )
        data = r.json()
        if data.get("status") != "ok":
            log.warning(f"NewsAPI status: {data.get('status')} | {data.get('message')}")
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
            params={
                "token":    GNEWS_KEY,
                "lang":     "fr",
                "country":  "fr",
                "max":      15
            },
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
#  SOURCE 3 : RSS FEEDS (fallback, sans clé API)
# ══════════════════════════════════════════════════════════
RSS_FEEDS = [
    ("Le Monde",     "https://www.lemonde.fr/rss/une.xml"),
    ("Le Figaro",    "https://www.lefigaro.fr/rss/figaro_actualites.xml"),
    ("France Info",  "https://www.francetvinfo.fr/titres.rss"),
    ("RFI",          "https://www.rfi.fr/fr/rss"),
    ("20 Minutes",   "https://www.20minutes.fr/feeds/rss/une"),
]

def fetch_rss() -> list:
    articles = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                image = None
                # Cherche l'image dans différents champs RSS
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
                        "title":       title,
                        "description": desc,
                        "url":         link,
                        "image":       image,
                        "source":      source
                    })
        except Exception as e:
            log.error(f"RSS {source} ❌ {e}")

    log.info(f"RSS ✅ {len(articles)} articles")
    return articles

# ══════════════════════════════════════════════════════════
#  RÉCUPÉRATION GLOBALE (avec fallbacks)
# ══════════════════════════════════════════════════════════
def get_articles() -> list:
    articles = fetch_newsapi()
    if len(articles) < 3:
        articles += fetch_gnews()
    if len(articles) < 3:
        articles += fetch_rss()
    # Shuffle pour varier les sources
    random.shuffle(articles)
    return articles

# ══════════════════════════════════════════════════════════
#  IMAGE DE SECOURS VIA PEXELS
# ══════════════════════════════════════════════════════════
def get_pexels_image(query: str) -> Optional[str]:
    try:
        # Extrait les 3 premiers mots utiles du titre
        mots = re.sub(r'[^a-zA-ZÀ-ÿ\s]', ' ', query).split()[:3]
        q = " ".join(mots)
        if not q.strip():
            q = "actualités monde"

        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": q, "per_page": 8, "orientation": "landscape"},
            timeout=10
        )
        photos = r.json().get("photos", [])
        if photos:
            photo = random.choice(photos)
            return photo["src"]["large"]
    except Exception as e:
        log.error(f"Pexels ❌ {e}")
    return None

# ══════════════════════════════════════════════════════════
#  VÉRIFICATION QUE L'URL IMAGE EST VALIDE
# ══════════════════════════════════════════════════════════
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
#  FORMATAGE DU MESSAGE TELEGRAM
# ══════════════════════════════════════════════════════════
def format_message(article: dict) -> str:
    title  = article["title"]
    desc   = re.sub(r'<[^>]+>', '', article.get("description", "")).strip()
    url    = article["url"]
    source = article.get("source", "")
    now    = datetime.now().strftime("%d/%m/%Y • %Hh%M")

    # Tronque la description si trop longue
    if len(desc) > 350:
        desc = desc[:347].rsplit(" ", 1)[0] + "..."

    msg = f"📰 <b>{title}</b>\n\n"
    if desc:
        msg += f"{desc}\n\n"
    msg += f"🔗 <a href='{url}'>Lire l'article complet</a>\n\n"
    msg += f"📡 <i>{source} • {now}</i>"
    return msg

# ══════════════════════════════════════════════════════════
#  ENVOI DANS LE CANAL
# ══════════════════════════════════════════════════════════
async def post_news():
    log.info("═" * 50)
    log.info("⏰ Récupération des actualités en cours...")

    bot     = Bot(token=TELEGRAM_TOKEN)
    posted  = load_posted()
    articles = get_articles()

    if not articles:
        log.warning("⚠️ Aucun article récupéré depuis toutes les sources !")
        return

    # Sélectionne le premier article non encore posté
    article = None
    for a in articles:
        if a["url"] not in posted:
            article = a
            break

    # Si tous déjà postés → on reset le cache
    if not article:
        log.info("🔄 Tous les articles ont déjà été postés → reset du cache")
        posted.clear()
        article = articles[0]

    log.info(f"📄 Article sélectionné : {article['title'][:60]}...")

    # Récupère l'image
    image_url = article.get("image")
    if image_url and not is_valid_image_url(image_url):
        log.info("⚠️ Image de l'article invalide → recherche Pexels")
        image_url = None

    if not image_url:
        log.info("🖼️ Recherche image Pexels...")
        image_url = get_pexels_image(article["title"])

    message = format_message(article)

    # Envoi
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
        err = str(e).lower()
        log.error(f"Telegram ❌ {e}")

        # Si l'image plante → réessaie sans image
        if image_url and ("wrong type" in err or "failed to get" in err or "url" in err):
            log.info("🔁 Tentative sans image...")
            try:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                posted.add(article["url"])
                save_posted(posted)
                log.info("✅ Article posté sans image (fallback OK)")
            except TelegramError as e2:
                log.error(f"Erreur fatale Telegram ❌ {e2}")

# ══════════════════════════════════════════════════════════
#  POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════
async def main():
    log.info("🤖 Bot Actualités démarré !")
    log.info(f"📢 Canal : {CHANNEL_ID}")
    log.info(f"⏱️  Fréquence : toutes les {INTERVAL_HOURS}h")

    # Premier post immédiat au démarrage
    await post_news()

    # Scheduler toutes les heures
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")
    scheduler.add_job(post_news, "interval", hours=INTERVAL_HOURS, id="news_job")
    scheduler.start()

    log.info(f"✅ Scheduler actif → prochain post dans {INTERVAL_HOURS}h")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("🛑 Bot arrêté proprement.")

if __name__ == "__main__":
    asyncio.run(main())
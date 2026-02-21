# 🤖 Bot Actualités Telegram — @news045_au

Bot qui poste automatiquement les actualités toutes les heures dans ton canal Telegram, avec une photo.

---

## 📦 Installation

### 1. Avoir Python 3.10+ installé
```bash
python --version
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancer le bot
```bash
python bot.py
```

C'est tout ! Le bot :
- Poste un article immédiatement au démarrage
- Poste ensuite toutes les heures automatiquement

---

## 🔧 Personnalisation

Dans `bot.py`, tu peux changer :

```python
INTERVAL_HOURS = 1   # Change la fréquence (ex: 2 pour toutes les 2h)
```

Et dans `RSS_FEEDS` pour ajouter d'autres sources d'actualités.

---

## 🖥️ Hébergement en continu (recommandé)

### Option A — Railway.app (gratuit)
1. Crée un compte sur railway.app
2. "New Project" → "Deploy from GitHub"
3. Upload tes fichiers
4. Le bot tourne 24h/24 gratuitement

### Option B — VPS (DigitalOcean, Hetzner...)
```bash
# Lancer en arrière-plan avec nohup
nohup python bot.py &

# Ou avec screen
screen -S bot
python bot.py
# CTRL+A puis D pour détacher
```

### Option C — Systemd (Linux serveur)
```bash
# Crée le fichier /etc/systemd/system/newsbot.service
[Unit]
Description=News Telegram Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /chemin/vers/bot.py
WorkingDirectory=/chemin/vers/dossier/
Restart=always

[Install]
WantedBy=multi-user.target

# Puis :
sudo systemctl enable newsbot
sudo systemctl start newsbot
```

---

## 📋 Sources d'actualités

Le bot utilise dans cet ordre (avec fallback automatique) :
1. **NewsAPI.org** — Actualités françaises
2. **GNews.io** — Backup si NewsAPI tombe
3. **RSS Feeds** — Le Monde, Le Figaro, France Info, RFI, 20 Minutes (sans clé API)

## 🖼️ Images

1. Image incluse dans l'article (priorité)
2. Image Pexels générée selon le sujet de l'article (fallback)
3. Texte seul si aucune image disponible (fallback final)

---

## 📁 Fichiers

| Fichier | Rôle |
|---|---|
| `bot.py` | Code principal du bot |
| `requirements.txt` | Dépendances Python |
| `posted_articles.json` | Cache des articles déjà postés (créé auto) |
| `bot.log` | Logs du bot (créé auto) |

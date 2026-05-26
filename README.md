# 🎵 statimusic

Transforme ton historique d'écoute Deezer en dashboard musical personnel.

> **Accès au site** → [statimusic.fr](https://statimusic.fr)

---

## C'est quoi ?

Tu as déjà téléchargé tes données personnelles Deezer ? statimusic les transforme en statistiques visuelles : combien d'heures tu as écouté, quels sont tes artistes préférés, comment tes goûts ont évolué dans le temps.

**Ce que tu pourras voir :**
- Tes indicateurs clés : heures totales, nombre d'écoutes, artistes découverts
- Ton top artistes, titres et albums avec leurs photos (podium 2-1-3)
- Des pages détaillées par artiste, album et titre avec graphiques
- Une barre de recherche avec suggestions en temps réel
- Une landing page publique pour présenter le projet

---

## Stack technique

- **Backend** : Flask (Python)
- **Base de données** : Supabase (PostgreSQL + Storage)
- **Hébergement** : Render (plan gratuit)
- **API** : Spotify (photos artistes et covers)
- **Design** : CSS custom, Inter font, dark mode (#191919 / #F2CC0D)
- **Domaine** : statimusic.fr (OVHcloud)
- **Format données** : Parquet (pyarrow + brotli) pour optimiser la RAM

---

## Architecture

```
statimusic/
├── app.py                          # Point d'entrée Flask
├── config.py                       # Variables d'environnement
├── db.py                           # Clients Supabase (public + admin)
├── models.py                       # Classe User (Flask-Login)
├── auth/
│   └── routes.py                   # /login, /register, /logout, /landing
├── dashboard/
│   ├── routes.py                   # /home, /upload, /track, /album, /artist, /api/search
│   ├── processor.py                # Traitement Excel, Storage, index recherche
│   └── analytics/
│       ├── loaders.py              # Lecture Excel Deezer
│       ├── spotify.py              # Appels API Spotify
│       ├── home.py                 # KPIs et top home
│       ├── artist.py               # KPIs page artiste
│       ├── album.py                # KPIs page album
│       └── track.py                # KPIs page titre
├── templates/
│   ├── base.html                   # Navbar + footer (pages connectées)
│   ├── landing.html                # Page d'accueil publique
│   └── dashboard/ + auth/          # Templates des pages
└── static/
    ├── styles.css                  # Design system complet
    └── logo_blanc.png
```

---

## Installation en local

**Prérequis** : Python 3.10+, Git

```bash
git clone https://github.com/TORiiiii05/statimusic.git
cd statimusic
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

Crée un fichier `.env` à la racine :

```
SECRET_KEY=ta_clé_secrète
SUPABASE_URL=ton_url_supabase
SUPABASE_KEY=ta_clé_supabase
SUPABASE_SECRET_KEY=ta_secret_key_supabase
SPOTIFY_CLIENT_ID=ton_client_id
SPOTIFY_CLIENT_SECRET=ton_client_secret
SPOTIFY_MARKET=FR
```

Lance le serveur :

```bash
python app.py
# Ouvre http://localhost:5000
```

---

## Développement

Pour tester avec un jeu de données réduit (10k écoutes les plus récentes) :

```bash
python make_dev_excel.py
```

Puis uploade `deezer_data_10k.xlsx` depuis la page `/upload`.

**Note :** Les pages détaillées (artiste, album, titre) peuvent être lentes sur Render plan gratuit (0.1 CPU). En local elles sont fluides.

---

## Roadmap

- [x] Session 0 — Mini projet de référence (musicstats)
- [x] Session 1 — Authentification + Base de données
- [x] Session 2 — Upload Excel + Dashboard
- [x] Session 3 — Pages détaillées artiste / album / titre
- [x] Session 4 — Recherche + Design
- [x] Session 5 — Production (Supabase Storage, Parquet, domaine statimusic.fr)
- [x] Session 6 — Landing page + Navigation
- [ ] Session 7 — Visualisations + Cache artiste + Page Mon compte

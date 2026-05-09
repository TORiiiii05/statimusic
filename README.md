# 🎵 statimusic

Transforme ton historique d'écoute Deezer en dashboard musical personnel.

> **Accès au site** → [statimusic.onrender.com](https://statimusic.onrender.com)

---

## C'est quoi ?

Tu as déjà téléchargé tes données personnelles Deezer ? statimusic les transforme en statistiques visuelles : combien d'heures tu as écouté, quels sont tes artistes préférés, comment tes goûts ont évolué dans le temps.

**Ce que tu pourras voir :**
- Tes indicateurs clés : heures totales, nombre d'écoutes, artistes découverts
- Ton top artistes avec leurs photos
- Ton top titres et albums
- L'évolution de ton écoute mois par mois et année par année
- Des pages détaillées par artiste, album et titre

---

## Stack technique

- **Backend** : Flask (Python)
- **Base de données** : Supabase (PostgreSQL)
- **Hébergement** : Render
- **API** : Spotify (photos artistes et covers)

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
SPOTIFY_CLIENT_ID=ton_client_id
SPOTIFY_CLIENT_SECRET=ton_client_secret
SPOTIFY_MARKET=FR
```

Lance le serveur :

```bash
python app.py
# Ouvre http://localhost:5000/register
```

---

## Roadmap

- [x] Session 0 — Mini projet de référence (musicstats)
- [x] Session 1 — Authentification + Base de données
- [ ] Session 2 — Upload Excel + Dashboard
- [ ] Session 3 — Pages détaillées artiste / album / titre
- [ ] Session 4 — Recherche + Design
- [ ] Session 5 — Production
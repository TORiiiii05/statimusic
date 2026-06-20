# statimusic — contexte pour Claude

## Projet
Application web Flask d'analyse d'historique d'écoute Deezer (et bientôt Spotify/Apple Music).
Déployée sur Render (free plan) à **statimusic.fr**. Repo GitHub : `TORiiiii05/statimusic`.

Développée par Jules Del Frate (Monstre), étudiant en 3ème année BUT Science des Données parcours EAMS.
Le projet a été construit de A à Z avec Claude (Anthropic) comme assistant de développement principal —
pas pour générer du code à l'aveugle, mais pour apprendre, déboguer et prendre des décisions d'architecture.

---

## Stack

| Couche | Technologie |
|---|---|
| Backend | Flask, Flask-Login, Flask-Bcrypt, gunicorn |
| Données | pandas, PyArrow/Parquet, openpyxl |
| Base de données | Supabase (PostgreSQL) |
| Stockage fichiers | Supabase Storage (bucket `user-data`) |
| API externe | Spotify (client credentials flow) |
| Visualisations | Plotly (graphiques mensuels), Chart.js |
| Frontend | Jinja2, HTML, CSS vanilla, JavaScript |
| Design | Figma (maquettes), Inter font, dark mode |
| Déploiement | Render (free plan), OVHcloud (domaine) |

---

## Architecture

```
statimusic/
├── app.py                          # Point d'entrée Flask, blueprints, route /
├── config.py                       # Variables d'environnement centralisées
├── db.py                           # Clients Supabase : supabase (publishable) + supabase_admin (secret)
├── models.py                       # Classe User (Flask-Login, UserMixin)
├── gunicorn.conf.py                # timeout=300, workers=1
├── make_dev_excel.py               # Script génération Excel dev 10k lignes
├── auth/
│   ├── __init__.py
│   └── routes.py                   # /login, /register, /logout, /landing
├── dashboard/
│   ├── __init__.py
│   ├── routes.py                   # /home, /upload, /track/<isrc>, /album/<id>, /artist/<id>
│   │                               # /api/search, /search/resolve/artist, /search/resolve/album
│   ├── processor.py                # Traitement Excel, upload/download Parquet, index recherche
│   └── analytics/
│       ├── loaders.py              # Lecture Excel Deezer → DataFrame (6 colonnes utiles)
│       ├── home.py                 # KPIs et tops page Home (top 10 artistes, top 3 tracks/albums)
│       ├── artist.py               # KPIs page Artiste (rank, listen time, top titres, top albums)
│       ├── album.py                # KPIs page Album (rank, top titres, graphique mensuel)
│       ├── track.py                # KPIs page Titre (rank, graphique mensuel, meta Spotify)
│       └── spotify.py              # Helpers API Spotify (search, covers, get_by_id, token)
├── templates/
│   ├── base.html                   # Navbar (logo, search, Se déconnecter) + footer
│   ├── landing.html                # Page d'accueil publique (hero animé, features, about)
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── dashboard/
│       ├── home.html               # Podium 2-1-3 artistes/tracks/albums + KPIs
│       ├── upload.html             # Instructions 3 étapes + drag & drop
│       ├── artist.html             # Header cover + rank + pills + KPIs 2x2 + table + top albums
│       ├── album.html              # Header cover + rank + pills + KPIs 2x2 + table + graphique
│       └── track.html              # Header cover + rank + pills + KPIs 2x2 + graphique
└── static/
    ├── styles.css                  # Design system complet
    └── logo_blanc.png
```

---

## Supabase

**Projet ID** : `rszmydghmulmxgjbnjoi`

**Table `users`** :
| Colonne | Type | Usage |
|---|---|---|
| `id` | uuid | Clé primaire |
| `email` | text | Email utilisateur |
| `password_hash` | text | Mot de passe hashé (bcrypt) |
| `created_at` | timestamptz | Date création |
| `stats_json` | text | JSON stats home (KPIs + top artistes/tracks/albums avec covers b64) |
| `df_path` | text | Chemin fichier Parquet dans Storage (`{user_id}/df_tracks.parquet`) |

**Bucket `user-data`** :
- `{user_id}/df_tracks.parquet` — historique complet (6 colonnes, compression brotli)
- `{user_id}/search_index.json` — index de recherche pré-calculé

**Clients** :
- `supabase` — clé publishable, pour les opérations sur la table `users`
- `supabase_admin` — clé secret, pour toutes les opérations Storage

---

## Données

**Source** : fichier Excel exporté depuis Deezer (feuille `10_listeningHistory`)

**Colonnes lues** (après `usecols`) :
| Colonne Excel | Colonne DataFrame | Type |
|---|---|---|
| Song Title | titre | str |
| Artist | artiste | str (peut contenir "Vald, Alkpote") |
| Album Title | album | str |
| ISRC | ISRC | str (identifiant universel) |
| Listening Time | temps_écoute | float (secondes) |
| Date | date_écoute | datetime |

**Règles données** :
- `temps_écoute` est **toujours en secondes** dans le DataFrame
- **ISRC** est l'identifiant universel des titres — ne jamais utiliser les noms pour réconcilier Deezer↔Spotify
- `artiste` peut contenir plusieurs artistes séparés par virgules → **toujours splitter avant de filtrer ou compter**

---

## Flows principaux

**Upload** :
1. Excel uploadé → `load_listening_history` (pandas, usecols) → df_tracks
2. `process_excel_and_build_stats` → KPIs + top artistes/tracks/albums + covers Spotify → `stats_json`
3. `upload_df_to_storage` → Parquet brotli → Storage `{user_id}/df_tracks.parquet`
4. `build_search_index` + `upload_search_index_to_storage` → Storage `{user_id}/search_index.json`
5. Tout stocké en Supabase / Storage, Excel supprimé immédiatement

**Page détaillée** :
1. `_load_df_from_supabase` → download Parquet depuis Storage → DataFrame (~40 Mo RAM)
2. Calcul KPIs depuis le DataFrame
3. Appels Spotify pour covers/métadonnées
4. Rendu Jinja2

**Recherche** :
1. `download_search_index_from_storage` → JSON depuis Storage
2. Filtrage en mémoire sur `search_key` (lowercase)
3. Résolution artiste/album via `search_artist` / `search_album` Spotify → redirect vers page

---

## Déploiement

| Élément | Valeur |
|---|---|
| Hébergeur | Render (free plan) |
| RAM | 512 Mo |
| CPU | 0.1 |
| URL Render | statimusic.onrender.com |
| Domaine | statimusic.fr (OVHcloud) |
| DNS A | @ → 216.24.57.1 |
| DNS CNAME | www → statimusic.onrender.com |
| Start command | `gunicorn app:app --config gunicorn.conf.py` |
| Timeout | 300s |

**Variables d'environnement Render** :
`SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SECRET_KEY`,
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_MARKET`

---

## Règles impératives

- **Ne jamais** lire, afficher ni modifier le fichier `.env`
- **Ne jamais** committer `.env`, `*.xlsx`, `data.json`, `venv/`
- **Toujours** mettre à jour `CHANGELOG.md` **AVANT** de committer
- **Commits seulement** après validation explicite de Jules
- Environnement : **Windows PowerShell, VS Code**

---

## Roadmap — sessions de développement

Le projet suit un plan structuré en sessions. Chaque session a un périmètre défini.
**Session en cours : Session 8.**

| Session | Contenu | Durée estimée | Statut |
|---------|---------|---------------|--------|
| 1–6 | Auth, upload, stats, design, optimisations prod, landing | — | ✅ Terminées |
| **7** | Correction des indicateurs faux/suspects (`home.py`, `artist.py`) | ~8h | ✅ Terminée |
| 8 | Mot de passe oublié (Brevo + tokens Supabase) | ~3h | ⏳ |
| 9 | Fichier démo Deezer simulé + intégration page upload | ~3h | ⏳ |
| 10 | Import historique Spotify (loader JSON, upload, indicateurs) | ~8h | ⏳ |
| 11 | Cache visualisations + port horloge d'écoute + répartition mensuelle home | ~5h | ⏳ |
| 12 | Port frises chronologiques + recommandations artiste/titre/album | ~5h | ⏳ |
| 13 | Polish UX : mobile, skeletons, design cards KPI + tests de non-régression (assertions sur les KPIs) | ~3h | ⏳ |
| 14 | Roue aléatoire (top 1000, filtres, liens Deezer/Spotify/YouTube) | ~8h | ⏳ |
| 15 | Poster typographique (génération Pillow, paiement Lemon Squeezy) | ~12h | ⏳ |

**Détail session 7 — corrections indicateurs :**

Indicateurs ❌ FAUX à corriger :
- `total_hours` (`home.py`) : exclure les lignes où `temps_écoute <= 0` avant de sommer
- `nb_artists` (`home.py`) : splitter les champs multi-artistes par virgule avant `nunique()`
- `coverage_pill` + `nb_sons_pill` (`artist.py`) : refonte par ISRC (dénominateur = `album+single` uniquement, déduplication par ISRC ; numérateur = intersection ISRCs écoutés)

Indicateurs ⚠️ SUSPECTS à corriger :
- `get_artist_rank` (`artist.py`) : remplacer le filtre exact par regex word-boundary pour capter les feats
- `get_total_listen_minutes` (`artist.py`) : même correctif regex

Indicateurs ✅ CORRECTS — ne pas toucher :
Tous les KPIs album et track, `nb_tracks` home, `avg_minutes_per_day`, `get_first_listen_date`, `get_most_listened_month`.

**Contexte session 10 — import Spotify :**

Format export Spotify : ZIP contenant des fichiers JSON. Structure d'une ligne :
```json
{
  "ts": "2023-06-07T10:03:56Z",
  "ms_played": 32880,
  "master_metadata_track_name": "Draps en sang",
  "master_metadata_album_artist_name": "Alkpote",
  "master_metadata_album_album_name": "LSDC",
  "spotify_track_uri": "spotify:track:6dyR9ETg04bjKQb6XRKDJE",
  "episode_name": null,
  "skipped": true
}
```
Pas d'ISRC dans l'export Spotify — identifiant interne = `spotify_track_uri`. Filtrer podcasts (`episode_name != null`) et audiobooks (`audiobook_title != null`). Convertir `ms_played` en secondes.

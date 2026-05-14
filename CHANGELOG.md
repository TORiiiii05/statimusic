# Changelog

Toutes les évolutions du projet statimusic, session par session.

Format : `✅ Fait` · `🚧 En cours` · `⏳ À faire`

---

## Session 4 — Recherche + Design ✅
*Mai 2026*

**Réalisé :**
- `templates/base.html` : navbar complète avec logo PNG, barre de recherche toujours visible, liens "Mettre à jour" et "Mon compte", footer
- `templates/dashboard/home.html` : podium 2-1-3 avec tailles différentes (#1 = 250px, #2/#3 = 200px), covers cliquables
- `templates/dashboard/artist.html` : layout header cover + rank + pills + KPIs 2x2, table titres cliquable, top albums
- `templates/dashboard/album.html` : même layout, table titres cliquable, graphique mensuel
- `templates/dashboard/track.html` : même layout, liens artiste et album cliquables
- `templates/auth/login.html` + `register.html` : design dark card avec logo
- `templates/dashboard/upload.html` : design minimaliste dark card
- `static/styles.css` : design system complet (palette #191919/#333/#F0F0F0/#F2CC0D, Inter, composants navbar/podium/table/cards/charts)
- Recherche : `/api/search` avec index en Supabase (`search_index_json`), suggestions temps réel, Enter pour valider, dropdown groupé par type
- `dashboard/analytics/home.py` : `img_size=400` pour artistes, tracks et albums
- `dashboard/analytics/track.py` : `fig.update_layout` fond transparent + couleur jaune + police Inter
- `dashboard/analytics/album.py` : même uniformisation des graphiques
- `dashboard/analytics/artist.py` : filtre artiste exact (regex word-boundary) pour éviter les faux positifs (jul → julien doré)
- `dashboard/analytics/spotify.py` : `search_album` avec scoring nom pour éviter les mauvaises covers
- `dashboard/analytics/artist.py` : colonne `album` ajoutée dans `get_top_10_titles_by_listen_time`
- `make_dev_excel.py` : script de génération d'un Excel de dev 10k lignes
- Colonne `search_index_json` (text, nullable) ajoutée à la table `users` dans Supabase

**Connu / à faire plus tard :**
- Sons publiés / discographie affichent `—` à la première visite (calcul async Spotify)
- Pages détaillées crashent sur Render plan gratuit (502) → à migrer vers Supabase Storage en Session 5
- Landing page non encore implémentée

**Appris :**
- Index de recherche en Supabase plutôt qu'en session Flask (limite 4Ko cookie)
- `pd.read_json` sur Windows interprète les longues strings comme des chemins → `StringIO`
- Regex word-boundary pour filtrer les artistes exacts dans un champ multi-artistes séparé par virgules
- Spotify trie les images par taille décroissante → `images[0]` = la plus grande (640x640)
- `img_size` dans `covers_getter` contrôle la résolution stockée en base64

---

## Session 3 — Pages détaillées ✅
*Mai 2026*

**Réalisé :**
- `templates/dashboard/track.html` : page titre avec cover, KPIs, graphique mensuel Plotly
- `templates/dashboard/album.html` : page album avec cover, KPIs, top titres, graphique mensuel
- `templates/dashboard/artist.html` : page artiste avec photo, KPIs, top titres, top albums
- `dashboard/routes.py` : routes `/track/<isrc>`, `/album/<album_id>`, `/artist/<artist_id>`
- `dashboard/processor.py` : ajout `serialize_df_tracks` + `load_df_from_supabase`
- Colonne `df_json` (text, nullable) ajoutée à la table `users` dans Supabase
- Compression gzip + base64 du df_tracks pour passer le timeout Supabase
- Fix `pd.read_json` sur Windows : passage par `StringIO`
- Fix `_ensure_month_start` : suppression du `raise ValueError` sur dates NaN → `dropna`

**Appris :**
- `pd.read_json` interprète les longues strings comme des chemins fichier → toujours passer par `StringIO`
- Compression gzip réduit un JSON de 10x → résout les timeouts Supabase sur plan gratuit
- Indexation track par ISRC (universel) plutôt que Spotify ID (instable)
- `get_artist_kpis_by_id` prend `df_tracks` ET `df_artists` en arguments séparés

---

## Session 2 — Upload + Dashboard ✅
*Mai 2026*

**Réalisé :**
- `dashboard/analytics/` : copie et adaptation des modules depuis mon_site_musical
- Correction des imports (`from analytics.` → `from dashboard.analytics.`)
- `dashboard/processor.py` : traitement de l'Excel, conversion PIL → base64, assemblage JSON
- `dashboard/routes.py` : route `/upload` (GET/POST) + route `/home` avec lecture Supabase
- `templates/dashboard/upload.html` : formulaire d'upload
- `templates/dashboard/home.html` : affichage KPIs + top artistes + top titres + top albums
- Colonne `stats_json` (text, nullable) ajoutée à la table `users` dans Supabase
- Fix Windows : `tmp.close()` avant `f.save()` pour éviter le PermissionError

**Appris :**
- Les objets PIL ne sont pas JSON-sérialisables → conversion en base64 avant stockage
- `tempfile.NamedTemporaryFile` sur Windows garde un handle ouvert → fermer avant d'écrire
- Affichage d'images base64 en HTML : `src="data:image/png;base64,{{ cover }}"`

---

## Session 1 — Authentification + Base de données ✅
*Mai 2026*

**Réalisé :**
- Création du repo `statimusic` sur GitHub
- Structure de dossiers : auth/, dashboard/, templates/, static/
- Création du projet Supabase — table `users` (id, email, password_hash, created_at)
- `db.py` : connexion Supabase centralisée
- `config.py` : variables d'environnement centralisées
- `models.py` : classe User compatible Flask-Login
- `auth/routes.py` : /register, /login, /logout avec Flask-Bcrypt
- Templates : base.html, login.html, register.html, dashboard/home.html
- Déploiement sur Render avec gunicorn

**Appris :**
- Import circulaire Python et comment l'éviter (fichier db.py dédié)
- Blueprint Flask : séparer auth et dashboard
- Flask-Login : UserMixin, login_user, logout_user, login_required, user_loader
- Flask-Bcrypt : hash et vérification de mot de passe
- Supabase : création projet, récupération clés API, Table Editor
- Windows PowerShell : echo. pour créer des fichiers

---

## Session 5 — Production ⏳
*À venir*

- [ ] Migrer df_json vers Supabase Storage (fichier .json.gz) → résoudre crash RAM sur Render (502)
- [ ] Nom de domaine statimusic.fr
- [ ] Optimisations performances
- [ ] Landing page

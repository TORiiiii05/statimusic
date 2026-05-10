# Changelog

Toutes les évolutions du projet statimusic, session par session.

Format : `✅ Fait` · `🚧 En cours` · `⏳ À faire`

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
- Fix `pd.read_json` sur Windows : passage par `StringIO` pour éviter l'interprétation comme chemin de fichier
- Fix `_ensure_month_start` : suppression du `raise ValueError` sur dates NaN → `dropna` à la place

**Connu / à faire plus tard :**
- `df_artists` non stocké → rank artiste toujours `#None`
- Sons publiés / discographie affichent `—` à la première visite (calcul async Spotify)
- Liens depuis la home vers les pages détaillées pas encore en place

**Appris :**
- `pd.read_json` interprète les longues strings comme des chemins fichier → toujours passer par `StringIO`
- Compression gzip réduit un JSON de 10x → résout les timeouts Supabase sur plan gratuit
- Indexation track par ISRC (universel, dans l'Excel) plutôt que Spotify ID (propre à Spotify, instable)
- `get_artist_kpis_by_id` prend `df_tracks` ET `df_artists` en arguments séparés

---

## Session 2 — Upload + Dashboard ✅
*Mai 2026*

**Réalisé :**
- `dashboard/analytics/` : copie et adaptation des modules depuis mon_site_musical (loaders, spotify, home, artist, album, track)
- Correction des imports (`from analytics.` → `from dashboard.analytics.`)
- `dashboard/processor.py` : traitement de l'Excel, conversion PIL → base64, assemblage JSON
- `dashboard/routes.py` : route `/upload` (GET/POST) + route `/home` avec lecture Supabase
- `templates/dashboard/upload.html` : formulaire d'upload
- `templates/dashboard/home.html` : affichage KPIs + top artistes + top titres + top albums
- Colonne `stats_json` (text, nullable) ajoutée à la table `users` dans Supabase
- Fix Windows : `tmp.close()` avant `f.save()` pour éviter le PermissionError sur fichier temporaire

**Appris :**
- Les objets PIL ne sont pas JSON-sérialisables → conversion en base64 avant stockage
- `tempfile.NamedTemporaryFile` sur Windows garde un handle ouvert → il faut fermer avant d'écrire dessus
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

## Session 4 — Recherche + Design ⏳
*À venir*

- [ ] Liens depuis la home vers les pages détaillées (artiste, album, track)
- [ ] Stocker df_artists en Supabase → débloquer rank artiste
- [ ] Barre de recherche avec suggestions
- [ ] Polish visuel complet

---

## Session 5 — Production ⏳
*À venir*

- [ ] Nom de domaine statimusic.fr
- [ ] Optimisations performances
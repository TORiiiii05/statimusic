# Changelog

Toutes les évolutions du projet statimusic, session par session.

Format : `✅ Fait` · `🚧 En cours` · `⏳ À faire`

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

## Session 3 — Pages détaillées ⏳
*À venir*

- [ ] Page artiste /artist/<artist_id>
- [ ] Page album /album/<album_id>
- [ ] Page titre /track/<isrc>

---

## Session 4 — Recherche + Design ⏳
*À venir*

- [ ] Barre de recherche avec suggestions
- [ ] Polish visuel complet

---

## Session 5 — Production ⏳
*À venir*

- [ ] Nom de domaine statimusic.fr
- [ ] Optimisations performances

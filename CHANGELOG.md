# Changelog

Toutes les évolutions du projet statimusic, session par session.

Format : `✅ Fait` · `🚧 En cours` · `⏳ À faire`

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
- Windows PowerShell : New-Item, echo. pour créer des fichiers

---

## Session 2 — Upload + Dashboard ⏳
*À venir*

- [ ] Page d'upload de l'Excel
- [ ] Flask reçoit le fichier → calcule les stats → appelle Spotify → stocke JSON en Supabase → supprime l'Excel
- [ ] Dashboard : 6 KPIs, top artistes avec photos, bar chart années

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
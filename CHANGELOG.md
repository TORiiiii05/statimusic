# Changelog

Toutes les évolutions du projet statimusic, session par session.

Format : `✅ Fait` · `🚧 En cours` · `⏳ À faire`

---

## Session 7 — Audit & correction des indicateurs ✅
*Juin 2026*

- `home.py` : exclure les `temps_écoute <= 0` du calcul de `total_hours`
- `home.py` : `nb_artists` corrigé — split par virgule avant `nunique()` (multi-artistes)
- `artist.py` : `get_artist_rank` corrigé — split + explode sur tous les artistes avant classement
- `artist.py` : `get_total_listen_minutes` corrigé — regex word-boundary pour capter les feats
- `artist.py` : `get_discography_coverage_by_id` corrigé — numérateur par ISRC, dénominateur album+single uniquement (sans appears_on), déduplication par ISRC
- `artist.py` : `get_total_tracks_by_artist_id` corrigé — déduplication par ISRC (fallback nom normalisé)
- Tests de non-régression déplacés en session 13

---

## Session 8 — Mot de passe oublié ✅
*Juin 2026*

- `config.py` : ajout `BREVO_API_KEY` et `CONTACT_EMAIL`
- `auth/email.py` : helper `send_reset_email` via API HTTP Brevo (POST `/v3/smtp/email`)
- `auth/routes.py` : route `/forgot-password` — génère token UUID4, insère dans `password_reset_tokens` (TTL 1h), envoie email ; message générique anti-énumération
- `auth/routes.py` : route `/reset-password/<token>` — vérifie token non expiré et non utilisé, hash bcrypt, update `users.password_hash`, marque token `used = TRUE`
- `templates/auth/forgot_password.html` + `reset_password.html` : nouveaux templates dark mode
- `templates/auth/login.html` : ajout lien "Mot de passe oublié ?"

---

## Session 9 — Historique simulé ✅
*Juin 2026*

- Script `generate_demo_data.py` créé à la racine — génère 10 444 lignes avec 51 artistes internationaux et 264 titres uniques
- Fichier `static/demo/historique_exemple.xlsx` généré et disponible en téléchargement
- Bouton "Télécharger un historique exemple" ajouté sur `upload.html` et `landing.html`
- `static/demo/*.xlsx` ajouté au `.gitignore`

---

## Session 10 — Import Spotify + refonte page upload ✅
*Juin 2026*

- Nouveau `dashboard/analytics/loaders_spotify.py` — lecture JSON Spotify, filtrage podcasts/audiobooks, conversion ms→secondes
- Schéma interne commun : colonnes `source` ("deezer"/"spotify") et `spotify_uri` ajoutées au DataFrame
- `resolve_spotify_isrcs()` dans `spotify.py` — résolution ISRC batch par 50 via API Spotify
- Route `/upload` refaite : accepte plusieurs fichiers simultanément (.xlsx, .json, .zip), fusion des DataFrames Deezer+Spotify
- Refonte complète `templates/dashboard/upload.html` : design option D, bandeau démo enrichi, section aide en bas
- Logos Deezer (blanc) et Spotify intégrés dans les cartes d'aide
- `static/deezer-logo-white.svg` généré (texte blanc, wave violet)
- Tutoriels mis à jour : vrais noms des boutons, délais corrects (Deezer ~7j, Spotify 2-3 semaines), liens directs corrects
- Captures d'écran annotées intégrées (Deezer sous étape 2, Spotify sous étape 3)
- Barre de recherche masquée sur les pages sans données (upload, login, register, landing, forgot/reset password)
- Correction lien Deezer : `https://www.deezer.com` (évite l'encodage %2F)

---

## Session 11 — Cache visualisations + nouvelles visus Home (à venir)

- Nouveau `dashboard/analytics/charts_builder.py` — génération visus à l'upload
- Stockage PNG/JSON Plotly dans Supabase Storage sous `{user_prefix}/charts/`
- Port horloge d'écoute (`plot_listening_clock`) depuis `test_complet.py`
- Port répartition mensuelle interactive (`plot_listening_time_by_month_interactive`)

---

## Session 12 — Nouvelles visus Artiste / Titre / Album (à venir)

- Port timeline sorties d'albums
- Port recommandations artistes/titres/albums similaires par co-écoute

---

## Session 13 — Polish UX + tests de non-régression (à venir)

- Amélioration rendu mobile des graphiques Plotly
- États de chargement skeleton sur les visus
- Refonte cards KPI (typographie, espacements)
- Tests de non-régression : assertions sur les KPIs principaux

---

## Session 14 — Roue aléatoire (à venir)

- Route `/wheel` + template dédié
- Endpoint `/api/wheel-tracks` — top 1000 filtrable (genre, période, artiste)
- Roue animée Canvas/SVG
- Carte résultat avec liens Deezer / Spotify / YouTube

---

## Session 15 — Poster typographique (à venir)

- Script `poster_generator.py` — génération PNG haute résolution avec Pillow
- Design typographique + palette couleurs extraite des pochettes (sans reproduction des images)
- Route `/poster` — preview watermarquée + bouton achat
- Intégration paiement Lemon Squeezy (configuré mais désactivé jusqu'à la session 16)
- Route `/poster/download/<order_id>` — vérification paiement, téléchargement HD

---

## Session 16 — Tests E2E + audit + go live (à venir)

- Suite de tests Playwright couvrant tous les parcours utilisateur
- Tests de charge Locust (simulation utilisateurs simultanés sur Render)
- Audit sécurité OWASP ZAP
- Corrections des bugs détectés
- Activation du paiement Lemon Squeezy après validation complète
- Tests de non-régression KPIs (assertions sur le DataFrame)

---

## Session 6 — Landing page + Navigation ✅
*Mai 2026*

**Réalisé :**
- `templates/landing.html` : page d'accueil publique complète avec navbar, hero animé, features, section "La volonté du site", footer
- Animation canvas hero : formes géométriques jaunes flottantes en CSS/JS vanilla
- `app.py` : route `/` — redirige vers landing si non connecté, vers `/home` si connecté
- `auth/routes.py` : route `/landing` publique avec redirection si déjà connecté
- `static/styles.css` : CSS landing (navbar fixe avec blur, hero plein écran, features grid, about, footer)
- `base.html` : bouton "Mon compte" remplacé par "Se déconnecter" → `url_for('auth.logout')`
- `templates/auth/register.html` + `login.html` : correction classe `auth-container` → `auth-page` + `auth-card`

**Texte landing :**
- Titre : "Votre écoute musicale en chiffres"
- Sous-titre : questions percutantes ciblant l'audience rap/musique
- Description : accent sur gratuité et confidentialité des données
- CTA : "Commencer maintenant" + "Importer mon historique"

**Appris :**
- Canvas HTML5 pour animations légères sans librairie externe
- `backdrop-filter: blur()` pour navbar transparente pro
- `clamp()` CSS pour typographie responsive sans media queries

---

## Session 5 — Production ✅
*Mai 2026*

**Réalisé :**
- Migration `df_json` (colonne Supabase) → Supabase Storage (fichier `.parquet`)
- Format Parquet (brotli) : JSON.gz 150 Mo RAM → Parquet ~40 Mo RAM (~75% de réduction)
- `dashboard/processor.py` : `upload_df_to_storage` et `download_df_from_storage` avec pyarrow
- `dashboard/analytics/loaders.py` : `usecols` pour ne lire que 6 colonnes depuis l'Excel, suppression `df_artists`
- `dashboard/analytics/artist.py` : nettoyage 1137 → 280 lignes, suppression fonctions name-based, `.loc[mask, cols]` sans `.copy()`
- `dashboard/analytics/album.py` : nettoyage 700 → 210 lignes, suppression recommandations et visualisations inutilisées
- `dashboard/analytics/track.py` : nettoyage 676 → 220 lignes, suppression `get_track_artists_spotify`, `get_track_artists`
- `db.py` : ajout `supabase_admin` avec secret key pour les opérations Storage
- `gunicorn.conf.py` : timeout 300s pour l'upload de gros fichiers Excel
- Bucket `user-data` créé dans Supabase Storage avec policies SQL
- Colonne `df_path` (text, nullable) ajoutée à la table `users`
- Nom de domaine `statimusic.fr` acheté sur OVHcloud (4,99€/an)
- DNS configurés : enregistrement A `@` → `216.24.57.1` + CNAME `www` → `statimusic.onrender.com`
- Domaine vérifié et SSL actif sur Render

**Appris :**
- Parquet (pyarrow) vs JSON.gz : même taille disque, 4x moins de RAM à la lecture
- `usecols` dans `pd.read_excel` évite de charger les colonnes inutiles dès la lecture
- `.loc[mask, cols]` sans `.copy()` réduit les pics mémoire lors des filtres pandas
- Supabase Storage RLS : les policies doivent être créées via SQL Editor avec `bucket_id = 'user-data'`
- DNS : enregistrement A pour le domaine racine, CNAME pour www
- Gunicorn timeout par défaut 30s → insuffisant pour un upload + calcul Spotify → 300s
- RAM ≠ vitesse : RAM = espace de travail, vitesse = CPU + algorithme

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
- `templates/dashboard/upload.html` : page pleine avec instructions 3 étapes + drag & drop
- `static/styles.css` : design system complet (palette #191919/#333/#F0F0F0/#F2CC0D, Inter, composants navbar/podium/table/cards/charts)
- Recherche : `/api/search` avec index en Supabase (`search_index_json`), suggestions temps réel, Enter pour valider, dropdown groupé par type
- `dashboard/analytics/home.py` : `img_size=400` pour artistes, tracks et albums
- `dashboard/analytics/track.py` : graphiques fond transparent + couleur jaune + police Inter
- `dashboard/analytics/album.py` : même uniformisation des graphiques
- `dashboard/analytics/artist.py` : filtre artiste exact (regex) pour éviter les faux positifs
- `dashboard/analytics/spotify.py` : `search_album` avec scoring nom
- `make_dev_excel.py` : script de génération d'un Excel de dev 10k lignes
- Colonne `search_index_json` (text, nullable) ajoutée à la table `users` dans Supabase

**Appris :**
- Index de recherche en Supabase plutôt qu'en session Flask (limite 4Ko cookie)
- Regex word-boundary pour filtrer les artistes exacts dans un champ multi-artistes
- Spotify trie les images par taille décroissante → `images[0]` = la plus grande (640x640)

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
- Fix `_ensure_month_start` : suppression du `raise ValueError` sur dates NaN → `dropna`

**Appris :**
- `pd.read_json` interprète les longues strings comme des chemins fichier → toujours passer par `StringIO`
- Compression gzip réduit un JSON de 10x → résout les timeouts Supabase sur plan gratuit
- Indexation track par ISRC (universel) plutôt que Spotify ID (instable)

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

## À venir — Améliorations futures

- [ ] `artist_cache` table Supabase → pages détaillées instantanées
- [ ] Visualisations supplémentaires (frises chronologiques, répartition horaire)
- [ ] Multi-utilisateurs → plan Render Standard ($25/mois) si nécessaire
- [ ] Page "Mon compte" : changement de mot de passe, suppression du compte

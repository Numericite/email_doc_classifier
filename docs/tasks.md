# Tâches — V1

Découpage du projet V1 en tâches indépendantes, dans un ordre logique, à partir de
[`product.md`](./product.md) et [`architecture.md`](./architecture.md).

Chaque tâche vise **un objectif clair** et doit pouvoir être **développée et testée
indépendamment**. Le périmètre est strictement celui de la V1 (voir la section
« Hors périmètre » de `product.md`).

**État d'avancement actuel** : le socle est en place de bout en bout — configuration,
messagerie, extraction (Docling), projets Notion, analyse **Anthropic**, orchestration
(`pipeline.py`), persistance **PostgreSQL** et interface (**PySide6**). Il reste
principalement : le **dépôt Nextcloud** (module vide), l'**enrichissement des champs
analysés** (résumé, contact, référence, date), la fiabilisation et les tests.

Légende : `- [x]` fait · `- [~]` fait partiellement / à compléter · `- [ ]` à faire.

---

## 1. Configuration (`config/`) — ✅ fait

- [x] Mettre en place le chargement des variables d'environnement (fichier `.env`).
- [x] Centraliser les identifiants et secrets (Exchange, Notion, Nextcloud, Anthropic,
      base de données).
- [x] Définir les chemins de travail (dossier temporaire des pièces jointes, journaux).
- [x] Définir les paramètres et seuils de traitement.
- [ ] Vérifier au démarrage que la configuration requise est présente et valide.

## 2. Messagerie (`emails/`) — ✅ fait

- [x] Établir la connexion à la boîte mail Exchange.
- [x] Filtrer les nouveaux e-mails porteurs de pièces jointes.
- [x] Récupérer les métadonnées d'un e-mail (expéditeur, sujet, date, corps).
- [x] Extraire et sauvegarder les pièces jointes dans le dossier temporaire.
- [x] Restituer, par e-mail, ses métadonnées et la liste des fichiers sauvegardés.

## 3. Extraction (`extraction/`, `vision/`) — ✅ fait

> **Décision** : unifier l'extraction autour de **Docling** (PDF texte + scanné, image,
> DOCX, tableaux), avec **RapidOCR** comme moteur OCR interne. L'interface de sortie ne
> change pas : un document en entrée, un **texte unique** en sortie.

- [x] Intégrer **Docling** comme moteur d'extraction unique dans `extraction/`.
- [x] Configurer **RapidOCR** comme backend OCR de Docling (pas de Tesseract/PaddleOCR).
- [x] Activer la reconstruction des **tableaux** + OCR pleine page pour les scans.
- [x] Conserver l'interface `prepare(document) -> texte` (sortie Markdown / texte unique).
- [x] Garantir qu'aucun document brut n'est transmis au LLM (texte extrait uniquement).
- [x] Couvrir les formats de la V1 : PDF texte ✓, PDF scanné ✓, DOCX ✓ — validés sur
      documents réels (image supportée par Docling, non testée faute d'échantillon).
- [x] Plafonner les documents longs : `MAX_PAGES=5` et `MAX_CHARS=20000`, sans tronquer
      les documents courts.
- [x] Retirer l'ancien pipeline redondant ; mettre `vision/` en attente.
- [ ] Fiabiliser l'extraction sur les cas dégradés (qualité OCR, tableaux complexes).

## 4. Projets Notion (`notion/`) — ✅ fait

- [x] Connecter l'application à l'API Notion (token + `database_id` via `settings`).
- [x] Récupérer uniquement les projets actifs (filtre `Status = "In Progress"`).
- [x] Formater chaque projet pour le LLM : nom, description, client, contact,
      **lien Nextcloud** (`get_projets_actifs()`), avec gestion d'erreur API.
- [ ] (Étape Nextcloud) convertir le lien Nextcloud (URL interface `?dir=...`) en chemin
      WebDAV pour le dépôt.

## 5. Analyse LLM (`classification/`) — ✅ fait (Anthropic), à compléter

> Un **seul appel Anthropic** par document (`claude-haiku-4-5`), sur le **texte extrait**
> + la liste des projets. Sortie **structurée** (json_schema) : le LLM renvoie l'**index**
> du projet, réutilisé pour retrouver le dossier Nextcloud.

- [x] Construire l'entrée de l'analyse à partir du **texte extrait** (`preparation_prompt`).
- [x] Ajouter la liste des projets actifs Notion à l'entrée de l'analyse.
- [x] Réaliser **un seul appel** à l'**API Anthropic** par document.
- [x] Récupérer une sortie **structurée en JSON** garantie (json_schema).
- [x] Maîtriser le coût : modèle économique (Haiku) + texte extrait plafonné.
- [~] Champs de sortie : type de document ✓, projet ✓, score ✓, dossier Nextcloud ✓
      (via le projet) — **manquants** : résumé, contact, référence, date, informations
      extraites du document.
- [ ] Tester l'appel réel : valider `output_config`/`json_schema` et l'ID de modèle
      (`claude-haiku-4-5`) sur de vrais documents.

## 6. Orchestration (`orchestration/`) — ✅ fait

- [x] Enchaîner les étapes dans le bon ordre (mail → Notion → extraction → analyse →
      enregistrement) dans `pipeline.py`.
- [x] Transmettre les données entre les modules (fichiers, texte, projets, proposition).
- [x] Gérer les erreurs et décider de poursuivre / ignorer un document.
- [x] Ne conserver aucune logique métier (délégation pure aux modules).
- [x] Anti-doublon : un mail déjà en base n'est pas ré-analysé (économie de tokens).

## Persistance (`databases/`) — ✅ fait

- [x] Schéma PostgreSQL (`mails`, `documents`) créé de façon idempotente (`init_db`).
- [x] Couche d'accès (repository) : enregistrement mail + documents, anti-doublon,
      listing, changement de statut. Source de vérité de l'application.

## 7. Interface (`ui/`) — ✅ fait

- [x] Afficher la liste des mails / documents reçus (PySide6).
- [x] Aperçu du document (ouverture avec l'application système).
- [x] Afficher les informations : type, projet proposé, score de confiance.
- [x] Afficher / modifier l'état de validation (statut) du document.
- [x] Actions : Aperçu, Télécharger, changement de statut, « Classé ».
- [ ] Afficher explicitement le **dossier Nextcloud proposé** (aujourd'hui seul le projet
      est montré).

## 8. Validation (flux de décision) — ~ partiel

- [x] Enregistrer la décision de l'utilisateur (statut : en attente / à signer /
      à renvoyer / classé).
- [x] Gérer le refus / renvoi : téléchargement du document par l'utilisateur.
- [x] Ré-analyse d'un document renvoyé : un nouveau mail = nouveau `message_id` = analysé.
- [ ] Déclencher le **dépôt Nextcloud** au moment de la validation (aujourd'hui « Classé »
      ne fait que changer le statut, sans dépôt).

## 9. Nextcloud (`nextcloud/`) — à faire

> Le module `nextcloud/imports_liste_project.py` est **vide** : rien n'est implémenté.

- [ ] Connecter l'application à l'API Nextcloud (WebDAV, `settings.nextcloud_url`).
- [ ] Récupere la laiste des dossier d'un dossier specifie ( je le met dans le code) mais sauf les dossier qui ont une date inferieur a un an
- [ ] 
- [ ] Convertir le lien Notion (URL interface `?dir=...`) en chemin WebDAV.
- [ ] Déposer un document dans le dossier proposé (uniquement sur ordre de validation).
- [ ] Confirmer le résultat du dépôt (succès / échec) et le tracer en base
      (`chemin_nextcloud`, statut).
- [ ] Garantir qu'aucun dépôt n'a lieu sans validation humaine préalable.

## 10. Tests — ~ partiel

- [x] Scripts de test manuels existants : extraction, sauvegarde des pièces jointes,
      classifier, import Notion.
- [ ] Tester la connexion et le filtrage des e-mails de bout en bout.
- [ ] Tester l'analyse Anthropic (validité et structure du JSON de sortie).
- [ ] Tester le pipeline d'orchestration complet (mail → base).
- [ ] Tester le flux de validation / changement de statut via l'UI.
- [ ] Tester le dépôt Nextcloud (une fois implémenté), uniquement après validation.

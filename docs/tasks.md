# Tâches — V1

Découpage du projet V1 en tâches indépendantes, dans un ordre logique, à partir de
[`product.md`](./product.md) et [`architecture.md`](./architecture.md).

Chaque tâche vise **un objectif clair** et doit pouvoir être **développée et testée
indépendamment**. Le périmètre est strictement celui de la V1 (voir la section
« Hors périmètre » de `product.md`).

**État d'avancement actuel** : la configuration et la récupération des pièces jointes
sont **faites**. L'extraction et l'OCR sont **implémentés mais à fiabiliser**. Le projet
s'arrête aujourd'hui à l'analyse des documents ; la suite reste à faire.

Légende : `- [x]` fait · `- [~]` fait mais à fiabiliser · `- [ ]` à faire.

---

## 1. Configuration (`config/`) — ✅ fait

- [x] Mettre en place le chargement des variables d'environnement (fichier `.env`).
- [x] Centraliser les identifiants et secrets (Exchange, Notion, Nextcloud, Anthropic).
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
> DOCX, tableaux), avec **RapidOCR** comme moteur OCR interne. Docling remplace
> l'assemblage manuel actuel (détection de page + PyMuPDF + OCR séparé). L'interface de
> sortie ne change pas : un document en entrée, un **texte unique** en sortie, pour ne
> pas impacter `classification/`.

- [x] Sauvegarde du document reçu prête à être traitée (issu de `emails/`).
- [x] Intégrer **Docling** comme moteur d'extraction unique dans `extraction/`.
- [x] Configurer **RapidOCR** comme backend OCR de Docling (pas de Tesseract/PaddleOCR).
- [x] Activer la reconstruction des **tableaux** (`do_table_structure`).
- [x] Conserver l'interface `prepare(document) -> texte` (sortie Markdown / texte unique).
- [x] Garantir qu'aucun document brut n'est transmis au LLM (texte extrait uniquement).
- [x] Couvrir les formats de la V1 : PDF texte ✓, PDF scanné ✓ (OCR pleine page),
      DOCX ✓ — validés sur documents réels (image supportée par Docling, non testée
      faute d'échantillon).
- [x] Plafonner les documents longs : `MAX_PAGES=5` (borne l'extraction / la lenteur)
      et `MAX_CHARS=20000` (borne le coût LLM), sans tronquer les documents courts.
- [x] Retirer l'ancien pipeline devenu redondant
      (`analyse_document.py`, `ocr_extractor.py`, `image_extractor.py`).
- [x] Statuer sur `vision/` → **mis en attente** : l'OCR est couvert par Docling +
      RapidOCR, et la détection logo / signature n'est pas nécessaire en V1
      (LLM Vision hors périmètre).
- [ ] Fiabiliser l'extraction sur les différents types de documents (qualité, tableaux,
      documents dégradés).

## 4. Projets Notion (`notion/`) — à faire

- [ ] Connecter l'application à l'API Notion.
- [ ] Récupérer la liste des projets actifs.
- [ ] Formater les projets pour servir de référentiel au LLM.

## 5. Analyse LLM (`classification/`) — API Anthropic

> **Prérequis coût** : l'appel Anthropic ne doit recevoir que le **texte extrait**,
> jamais les documents bruts. C'est pourquoi l'analyse dépend d'une **extraction
> solide** (voir §3) : sans elle, il faudrait envoyer les documents entiers à Anthropic,
> ce qui coûterait beaucoup trop cher. On finalise donc l'extraction et la couverture
> des différents types de documents **avant** de brancher réellement Anthropic.

- [ ] Construire l'entrée de l'analyse à partir du **texte extrait** (jamais le doc brut).
- [ ] Ajouter la liste des projets actifs Notion à l'entrée de l'analyse.
- [ ] Réaliser **un seul appel** à l'**API Anthropic** par document.
- [ ] Récupérer et valider la sortie **structurée en JSON**.
- [ ] Extraire les champs attendus par la V1 : type de document, informations (client,
      contact, référence, date), résumé, projet proposé, score de confiance, dossier
      Nextcloud proposé.
- [ ] Gérer les réponses invalides ou incomplètes (garde-fous métier).
- [ ] Maîtriser le coût : limiter la taille du texte envoyé et le nombre d'appels.

## 6. Orchestration (`email_doc_classifier/`) — à faire

- [ ] Enchaîner les étapes du pipeline dans le bon ordre (mail → extraction → projets →
      analyse → proposition).
- [ ] Transmettre les données entre les modules (fichiers, texte, projets, proposition).
- [ ] Gérer les erreurs et décider de poursuivre ou d'interrompre le traitement d'un
      document.
- [ ] Ne conserver aucune logique métier dans ce module (délégation uniquement).

## 7. Interface (`ui`) — à faire

- [ ] Afficher la liste des nouveaux documents reçus.
- [ ] Afficher un aperçu du document.
- [ ] Afficher les informations extraites, le projet proposé, le score de confiance et
      le dossier proposé.
- [ ] Afficher l'état de validation du document.
- [ ] Proposer les actions : Valider, Refuser, Télécharger le document.

## 8. Validation (flux de décision) — à faire

- [ ] Enregistrer la décision de l'utilisateur (validation ou refus).
- [ ] Déclencher le dépôt Nextcloud uniquement après validation.
- [ ] Gérer le refus : permettre le téléchargement du document par l'utilisateur.
- [ ] Prendre en charge la ré-analyse d'un document renvoyé par e-mail après correction.

## 9. Nextcloud (`nextcloud/`) — à faire

- [ ] Connecter l'application à l'API Nextcloud.
- [ ] Déposer un document dans le dossier proposé (uniquement sur ordre de validation).
- [ ] Confirmer le résultat du dépôt (succès / échec).
- [ ] Garantir qu'aucun dépôt n'a lieu sans validation humaine préalable.

## 10. Tests — à faire

- [ ] Tester la configuration et le chargement des variables d'environnement.
- [ ] Tester la connexion et le filtrage des e-mails (`emails/`).
- [ ] Tester l'extraction pour chaque format (PDF texte, PDF scanné, image, DOCX).
- [ ] Tester la récupération des projets actifs (`notion/`).
- [ ] Tester l'analyse LLM sur la validité et la structure du JSON de sortie.
- [ ] Tester le pipeline d'orchestration de bout en bout.
- [ ] Tester le flux de validation / refus.
- [ ] Tester le dépôt Nextcloud (uniquement après validation).

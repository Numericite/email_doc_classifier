# Assistant intelligent de gestion documentaire

## Présentation

Application locale destinée au pôle administratif afin d'assister le traitement et le classement des documents.

L'application ne classe jamais automatiquement les documents. Chaque proposition doit être validée par un utilisateur avant toute sauvegarde dans Nextcloud.

L'objectif est d'automatiser les tâches répétitives tout en conservant un contrôle humain sur chaque décision.

---

# Objectifs

- Surveiller une boîte mail Exchange.
- Détecter les nouveaux e-mails contenant des pièces jointes.
- Identifier le type de document reçu.
- Extraire le contenu du document selon son format.
- Récupérer les projets actifs depuis Notion.
- Analyser le document à l'aide d'un LLM.
- Proposer le projet et le dossier Nextcloud les plus pertinents.
- Permettre à un utilisateur de valider ou de refuser la proposition.
- Classer le document dans Nextcloud après validation.

---

# Flux de traitement

1. Surveillance de la boîte mail Exchange.
2. Détection d'un nouvel e-mail avec pièce jointe.
3. Détection du type de fichier.
4. Routage vers le pipeline d'extraction adapté.
5. Extraction locale du texte.
6. Récupération des projets actifs depuis Notion.
7. Analyse du document par le LLM.
8. Affichage de l'analyse dans l'interface.
9. Validation ou refus par l'utilisateur.
10. Si validation :
   - Envoi du document vers Nextcloud via l'API.
11. Si refus :
   - L'utilisateur télécharge le document.
   - Il le modifie (signature, correction, etc.).
   - Il le renvoie par e-mail.
   - Une nouvelle analyse est effectuée.

---

# Formats de documents pris en charge

- PDF texte
- PDF scanné
- Images
- DOCX
- Autres formats pris en charge

---

# Traitement des documents

### PDF texte

- Extraction locale du texte
- PyMuPDF ou pdfplumber

### PDF scanné

- OCR local
- Tesseract ou PaddleOCR

### Images

- OCR local
- Tesseract ou PaddleOCR

### DOCX

- Extraction du texte et des tableaux
- python-docx

Aucun document brut n'est envoyé directement au LLM.

---

# Analyse par le LLM

Un seul appel est effectué.

### Entrée

- Texte extrait du document
- Liste des projets actifs provenant de Notion

### Sortie (JSON)

- Type de document
- Informations extraites
- Client
- Contact
- Référence
- Date
- Résumé
- Projet proposé
- Score de confiance
- Dossier Nextcloud proposé

---

# Interface utilisateur

L'application affiche :

- Les nouveaux documents reçus
- Un aperçu du document
- Les informations extraites
- Le projet proposé
- Le score de confiance
- Le dossier proposé
- L'état de validation

Actions disponibles :

- Valider
- Refuser
- Télécharger le document

---

# Hors périmètre (V1)

- Classement automatique sans validation
- Envoi automatique dans Nextcloud
- Base vectorielle (RAG)
- Base de données vectorielle
- LLM Vision
- Multi-utilisateur
- Déploiement Cloud

---

# Technologies

## Backend

- Python

## Services externes

- Exchange
- API Notion
- API Nextcloud

## Extraction de documents

- PyMuPDF
- pdfplumber
- python-docx

## OCR

- Tesseract
- PaddleOCR

## LLM

- Modèle API anthropic


---

# Principe fondamental

L'application est un **assistant de gestion documentaire**.

Elle analyse les documents, propose un classement et fournit les informations utiles, mais **la décision finale appartient toujours à l'utilisateur**.
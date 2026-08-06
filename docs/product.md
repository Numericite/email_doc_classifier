# Assistant intelligent de gestion documentaire

## Présentation

Application locale destinée au pôle administratif pour **assister** le traitement et le
classement des documents reçus par e-mail.

L'application ne classe **jamais** automatiquement. Chaque proposition est validée par un
utilisateur avant tout dépôt dans Nextcloud. L'objectif : automatiser le travail répétitif
tout en gardant un contrôle humain sur chaque décision.

---

## Ce que fait l'application

- Surveille une boîte mail **Exchange** et détecte les e-mails avec pièce jointe.
- Extrait le texte de chaque document (PDF, DOCX).
- Analyse le document avec un **LLM** et propose :
  - le **type** de document ;
  - le **dossier Nextcloud** le plus pertinent (parmi les dossiers existants) ;
  - un **score de confiance**.
- Cas particulier — **bon de commande** : propose aussi la **mission Ricobot** correspondante
  et pré-remplit les champs du bon de commande.
- Présente chaque proposition dans une interface où l'utilisateur **valide, corrige ou refuse**.
- Après validation : dépose le document dans Nextcloud (et/ou crée le bon de commande dans
  Ricobot).

---

## Flux de traitement

1. Réception d'un e-mail Exchange avec pièce jointe.
2. Sauvegarde locale de la pièce jointe.
3. Extraction du texte du document.
4. Récupération des dossiers Nextcloud existants.
5. Analyse par le LLM → type, dossier proposé, score (+ mission Ricobot pour un bon de commande).
6. Affichage de la proposition dans l'interface.
7. Décision de l'utilisateur :
   - **Classer** → dépôt dans le dossier Nextcloud choisi (créé à la volée si besoin).
   - **Remplir BDC** (bon de commande) → création dans Ricobot + lien vers le bon de commande.
   - **À signer / À renvoyer** → le document reste en attente d'une action.

---

## Formats pris en charge

| Format | Traitement |
|---|---|
| PDF texte | Extraction du texte |
| PDF scanné | OCR |
| Images | OCR |
| DOCX | Extraction du texte et des tableaux |

L'extraction est locale. **Aucun document brut n'est envoyé au LLM** : seul le texte extrait
l'est (confidentialité et coût). Le texte est plafonné (5 pages, 20 000 caractères).

---

## Analyse par le LLM

Un seul appel par document (deux pour un bon de commande). La réponse est un **JSON garanti
valide** (le type est toujours dans la liste autorisée).

**Entrée** : objet de l'e-mail + texte extrait + liste des dossiers Nextcloud (ou des missions
Ricobot pour un bon de commande).

**Sortie** :
- Type de document : `facture`, `devis`, `contrat`, `avenant`, `bon_de_commande`,
  `document_administratif`, `autre`.
- Dossier Nextcloud proposé (choisi *dans la liste* ; « aucun » si rien ne correspond).
- Score de confiance (0 à 1).
- Pour un bon de commande : mission Ricobot + champs (titre, référence, dates).

---

## Interface

Application de bureau, organisée **par e-mail reçu**. Pour chaque e-mail : expéditeur, objet,
date, et la liste de ses documents.

Pour chaque document :
- nom du fichier et **type** ;
- **dossier proposé** (champ recherchable parmi tous les dossiers Nextcloud, ou saisie d'un
  nouveau nom → créé au dépôt) ;
- **score de confiance** ;
- **statut** modifiable.

**Statuts** : En attente · À signer · À renvoyer · Classé.

**Actions** : Aperçu · Télécharger · Classer (dépôt Nextcloud) · Remplir BDC (Ricobot) ·
recherche · filtre par statut · suppression d'un mail.

---

## Hors périmètre

- Classement automatique sans validation.
- Base vectorielle / RAG.
- LLM Vision.
- Multi-utilisateur.
- Déploiement cloud.

---

## Technologies

- **Python** (backend).
- **Exchange** (mail), **Nextcloud** (dépôt), **Ricobot** (bons de commande).
- **Docling** + **RapidOCR** (extraction et OCR).
- **API Anthropic (Claude)** — sortie JSON garantie.
- **PostgreSQL** (données de l'application), accès en SQL direct via **psycopg**.
- **PySide6** (interface de bureau).

---

## Principe fondamental

L'application est un **assistant**. Elle analyse, propose un classement et fournit les
informations utiles, mais **la décision finale appartient toujours à l'utilisateur**.

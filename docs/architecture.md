# Architecture technique — V1

## Objet du document

Ce document décrit l'architecture technique de la **V1** de l'assistant intelligent
de gestion documentaire défini dans [`product.md`](./product.md).

Il ne contient aucun code. Il décrit :

- le rôle de chaque dossier ;
- le flux complet de traitement d'un document ;
- les interactions entre les modules ;
- les technologies utilisées ;
- les principes d'architecture.

L'architecture s'appuie sur la **structure de dossiers actuelle** du projet, sans en
modifier l'organisation.

```
src/
├── classification/
├── config/
├── ui/
├── databases/
├── emails/
├── extraction/
├── notion/
├── nextcloud/
├── utils/
└── vision/
```

---

## 1. Vue d'ensemble

L'application est un **assistant local** de gestion documentaire. Elle surveille une
boîte mail, extrait et analyse les documents reçus, puis **propose** un classement dans
Nextcloud.

Principe fondateur (voir `product.md`) : **aucun classement automatique**. Chaque
proposition est présentée à un utilisateur, qui **valide** ou **refuse** avant toute
écriture dans Nextcloud. La décision finale appartient toujours à l'utilisateur.

L'application est découpée en **modules à responsabilité unique**, chacun logé dans son
propre dossier et communiquant par des données simples (chemins de fichiers, texte
extrait, dictionnaires d'informations).

---

## 2. Rôle de chaque dossier

### `config/`
Configuration centralisée de l'application.
- Charge les variables d'environnement (identifiants Exchange, clés d'API Notion,
  Nextcloud, Anthropic).
- Définit les chemins de travail (dossier temporaire des pièces jointes, journaux).
- Regroupe les paramètres et les seuils de traitement.

Tous les autres modules lisent leurs paramètres ici ; aucune valeur sensible n'est
codée en dur ailleurs.

### `emails/`
Connexion à la messagerie **Exchange** et point d'entrée du flux.
- Se connecte à la boîte mail et filtre les nouveaux e-mails porteurs de pièces jointes.
- Extrait les pièces jointes et les sauvegarde dans le dossier temporaire.
- Restitue les métadonnées de chaque e-mail (expéditeur, sujet, date, corps) et la liste
  des fichiers sauvegardés.

C'est la **source** des documents à traiter.

### `extraction/`
Cœur de l'**extraction de contenu** local, unifié autour de **Docling**. Convertit un
fichier (PDF texte, PDF scanné, image, DOCX) en texte structuré exploitable :
- détecte automatiquement, page par page, le texte natif et les pages scannées ;
- déclenche l'**OCR** en interne pour les pages scannées et les images
  (moteur **RapidOCR**) ;
- reconstruit la **structure du document** (titres, ordre de lecture, **tableaux**) ;
- produit une sortie **structurée** (Markdown / texte) prête pour l'analyse.

Docling constitue un **point d'entrée unique** pour tous les formats de la V1 et remplace
l'assemblage manuel « détection de page + extraction native + OCR ». L'interface exposée
au reste de l'application reste stable : un document en entrée, un **texte unique** en
sortie.

Conformément au produit : **aucun document brut n'est envoyé au LLM**, seul le texte
extrait localement l'est. Cette extraction propre et compacte réduit aussi le volume
transmis au LLM, donc son **coût**.

### `vision/`
Traitement optionnel des **images** par modèle de vision, réservé aux cas que l'OCR ne
couvre pas (ex. *décrire* un logo ou une signature plutôt que retranscrire du texte).
L'OCR courant des pages scannées et des images est assuré par Docling dans
`extraction/` ; `vision/` n'intervient qu'en complément ciblé.

### `notion/`
Intégration de l'**API Notion**. Récupère la liste des **projets actifs**, qui sert de
référentiel au LLM pour proposer le projet le plus pertinent.

### `classification/`
Orchestration de l'**analyse par le LLM**.
- Envoie au LLM le **texte extrait** et la **liste des projets actifs** issue de Notion.
- Réalise **un seul appel** LLM par document.
- Récupère une sortie **structurée en JSON** : type de document, informations extraites
  (client, contact, référence, date), résumé, projet proposé, score de confiance et
  dossier Nextcloud proposé.

C'est le module qui transforme un texte brut en **proposition de classement**.

### `nextcloud/`
Intégration de l'**API Nextcloud**. Dépose le document dans le dossier proposé,
**uniquement après validation humaine**. Ce module n'écrit jamais de manière autonome.

### `email_doc_classifier/`
Module **uniquement orchestrateur** du flux. Il assemble le pipeline de bout en bout et
coordonne les autres modules, **sans contenir aucune logique métier** : il ne réalise
lui-même ni extraction, ni OCR, ni classification, ni appel à Notion, ni dépôt
Nextcloud. Toute cette logique reste dans les modules dédiés (`extraction/`, `vision/`,
`classification/`, `notion/`, `nextcloud/`) ; ce module ne fait que les appeler.

Ses responsabilités se limitent à :
- **coordonner** les différents modules ;
- **exécuter les étapes du pipeline dans le bon ordre** (surveillance mail → extraction →
  récupération des projets → analyse → proposition → dépôt après validation) ;
- **transmettre les données** entre les modules (fichiers, texte extrait, projets actifs,
  proposition structurée) ;
- **gérer les erreurs** et **décider de poursuivre ou d'interrompre** le traitement d'un
  document.

C'est le **chef d'orchestre** du flux : il enchaîne les étapes et fait circuler les
données, mais délègue tout le travail métier aux modules spécialisés.

### `utils/`
Fonctions transverses partagées (sérialisation des dates et des objets, helpers). Sans
dépendance métier, réutilisables par tous les modules.

---

## 3. Flux complet de traitement d'un document

Orchestré par `email_doc_classifier/`, le flux reprend celui de `product.md` :

1. **Surveillance de la boîte mail** — `emails/` interroge Exchange.
2. **Détection d'un nouvel e-mail avec pièce jointe** — sauvegarde des pièces jointes
   dans le dossier temporaire défini par `config/`.
3. **Extraction du contenu** — `extraction/` passe le fichier (PDF texte, PDF scanné,
   image, DOCX) dans **Docling**, qui détecte automatiquement texte natif vs pages
   scannées, applique l'**OCR** (RapidOCR) quand nécessaire et reconstruit la structure,
   **tableaux compris**.
4. **Production d'un texte unique** — `extraction/` produit une sortie structurée
   (Markdown / texte) prête pour l'analyse. `vision/` n'intervient qu'en complément
   ciblé (ex. description d'un logo / d'une signature).
5. **Récupération des projets actifs** — `notion/` fournit la liste des projets en cours.
6. **Analyse par le LLM** — `classification/` envoie *texte extrait + projets actifs* et
   reçoit une réponse **JSON** (type, informations, client, contact, référence, date,
   résumé, projet proposé, score de confiance, dossier Nextcloud proposé).
7. **Affichage de l'analyse** — la proposition est présentée à l'utilisateur.
8. **Décision humaine** — l'utilisateur **valide** ou **refuse**.
9. **Si validation** — `nextcloud/` dépose le document dans le dossier proposé.
10. **Si refus** — l'utilisateur télécharge le document, le corrige (signature,
    correction…) et le renvoie par e-mail : un **nouveau cycle** démarre à l'étape 1.

Un seul appel LLM est effectué par document.

---

## 4. Interactions entre les modules

Les dépendances sont **orientées** (sens unique), ce qui limite le couplage :

```
config/  ← lu par tous les modules (paramètres, chemins, secrets)
utils/   ← utilitaires transverses, sans dépendance métier

                     ┌───────────────── email_doc_classifier/ (orchestration) ─────────────────┐
                     │                                                                          │
                     ▼                                                                          ▼
emails/  ──►  extraction/  ──►  classification/  ──►  (proposition)  ──►  (validation)  ──►  nextcloud/
                   │                  ▲
               vision/            notion/
```

Règles d'interaction :

- **`config/` et `utils/`** sont des dépendances de bas niveau : tous les modules
  peuvent les utiliser, eux ne dépendent de personne.
- **`email_doc_classifier/`** est le seul module qui connaît l'ensemble du flux ; il
  appelle les autres dans l'ordre et ne porte pas de logique métier propre.
- **`emails/`** ne connaît que la messagerie et le dossier temporaire ; il **produit**
  des fichiers et des métadonnées.
- **`extraction/`** ne connaît que les fichiers ; il **produit** du texte et peut
  s'appuyer sur `vision/` pour les images.
- **`notion/`** fournit un référentiel de projets, indépendamment du reste.
- **`classification/`** **consomme** le texte de `extraction/` et les projets de
  `notion/`, appelle le LLM et **produit** une proposition structurée.
- **`nextcloud/`** n'écrit **jamais** sans un ordre explicite issu de la validation.

Les échanges se font par **données simples** (chemins, texte, dictionnaires), ce qui
permet de tester et de remplacer chaque module indépendamment.

---

## 5. Technologies utilisées

### Langage & socle
- **Python** (backend).
- Configuration par variables d'environnement, chargées dans `config/`.

### Services externes
- **Exchange** — surveillance de la boîte mail.
- **API Notion** — récupération des projets actifs.
- **API Nextcloud** — dépôt des documents validés.

### Extraction de documents
- **Docling** — moteur d'extraction unifié pour PDF (texte et scanné), images et DOCX :
  analyse de mise en page, reconstruction des **tableaux** et sortie structurée
  (Markdown / texte).

### OCR
- **RapidOCR** — moteur d'OCR utilisé **par Docling** pour les pages scannées et les
  images (aucune installation de Tesseract / PaddleOCR requise).

### LLM
- **Modèle via l'API Anthropic (Claude)** — analyse structurée du document, sortie JSON.

---

## 6. Principes d'architecture

- **Modularité** — chaque étape du flux vit dans son propre dossier, avec une frontière
  claire.
- **Responsabilité unique** — un module fait une seule chose : `emails/` récupère,
  `extraction/` extrait, `classification/` analyse, `nextcloud/` dépose,
  `email_doc_classifier/` orchestre.
- **Validation humaine obligatoire** — le classement n'est jamais automatique ; le dépôt
  Nextcloud est conditionné à une action explicite de l'utilisateur.
- **Traitement local et confidentialité** — l'extraction et l'OCR sont réalisés en
  local ; **seul le texte extrait** est transmis au LLM, jamais le document brut.
- **Un seul appel LLM par document** — pour la simplicité, la maîtrise des coûts et la
  prévisibilité.
- **Configuration centralisée** — secrets et paramètres isolés dans `config/`.
- **Couplage faible / dépendances orientées** — les modules communiquent par données
  simples et suivent un sens unique (source → extraction → analyse → décision → dépôt),
  ce qui rend chaque brique testable et remplaçable.
- **Périmètre V1 maîtrisé** — hors périmètre : classement automatique, envoi automatique,
  base vectorielle / RAG, LLM Vision, multi-utilisateur, déploiement Cloud
  (voir `product.md`).

# PyDeployer — automatisation locale d’un pipeline CI/CD  
Université Paris-Saclay
Encadrant : Professeur Franck Pommereau

---

##Groupe
| Nom  | Prénom  | Numéro d'étudiant| Nom du groupe  |               Sujet traite                |
|------|---------|------------------|----------------|-------------------------------------------|
| Messadi | Mounir | 12345678 | Groupe 3 | PyDeployer : Automatisation d’un pipeline CI/CD local |

---

##Objectif
Développer un outil Python permettant d’automatiser localement les étapes d’un pipeline CI/CD comme jenkins :
**clonage**, **build**, **test**, **déploiement** et **rollback**, à partir d’un fichier de configuration `pipeline.yml`.
L’outil fonctionne entièrement en local et servira de base pour des extensions Cloud dans un rendu ultérieur ( le deuxieme rendu ).

---

## Noyau minimal

Le noyau minimal de **PyDeployer** comprend :

### #1 — Chargement de la configuration
Lecture du fichier `pipeline.yml` pour définir les paramètres du pipeline, le dépôt à cloner et les options d’exécution.
> Base de tout le système — toutes les autres fonctionnalités en dépendent.

### #2 — Journalisation
Création automatique du dossier `/logs` et enregistrement de chaque exécution dans un fichier daté.
> dépend de #1

### #3 — Clonage du dépôt Git
Clonage du dépôt GitHub défini dans la configuration. 
S’il existe déjà, PyDeployer effectue un `git pull`. 
> dépend de #1 et #2

### #4 — Étape Build
Ajout automatique des fichiers modifiés et création d’un commit local simulant la phase de build. 
> dépend de #3

### #5 — Étape Test
Exécution des tests unitaires avec `pytest -v` sur le dépôt cloné. 
> dépend de #3

### #6 — Étape Deploy
Push des commits locaux vers la branche distante (par défaut : `master`). 
> dépend de #3 et #4

### #7 — Étape Rollback
Retour à la version précédente via `git revert HEAD` pour annuler le dernier déploiement.
> dépend de #6

---

## Fonctionnalités supplémentaires

### #8 — Nettoyage des anciens logs
Suppression automatique des anciens fichiers de logs, ne conservant que les 20  plus récents. 
> modifie #2 pour ajouter la gestion du stockage.

### #9 — Exécution séquentielle complète
Commande `python3 pydeployer.py all` permettant d’exécuter toutes les étapes du pipeline d’un seul coup. 
> dépend de #3, #4, #5 et #6

### #10 — Archivage des déploiements
Sauvegarde des informations de déploiement dans `archive/deploy_history.json` pour garder l’historique local. 
> dépend de #6

### #11 — Mode Cloud (AWS)
Prévu pour le rendu suivant : sauvegarde des archives et logs sur AWS S3 et notifications SNS en cas d’échec. 
> dépend de #1 et #6

### #12 — Interface CLI interactive
Ajout d’un menu textuel permettant de choisir les étapes à exécuter depuis le terminal. 


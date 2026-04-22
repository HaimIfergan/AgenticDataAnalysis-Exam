# Analyse d'Architecture : POC Actuel vs Système de Production Cible

## Résumé Exécutif
Le Proof of Concept (POC) actuel démontre une capacité réelle à analyser des données via un agent intelligent. Cependant, l'architecture monolithique actuelle présente des limites critiques pour un déploiement à grande échelle. Pour passer en production, nous préconisons une transition vers une architecture distribuée basée sur **FastAPI**, une persistance robuste via **PostgreSQL** et une exécution asynchrone des tâches via **Celery**.

## Analyse des Problèmes Actuels

### Problème 1 : Amnésie au Redémarrage
- **Découverte** : Lors de nos tests (Tâche 1.1), chaque rafraîchissement ou redémarrage du serveur entraînait la perte de l'historique de chat et des variables d'état.
- **Cause Racine** : L'état est stocké dans la mémoire vive (`st.session_state`), qui est volatile.
- **Impact Métier** : Expérience utilisateur médiocre nécessitant de répéter les instructions, augmentant les coûts opérationnels et la consommation de tokens LLM.
- **Solution Proposée** : Utilisation d'un `Checkpointer` persistant avec **PostgreSQL** pour sauvegarder l'état des threads de l'agent.

### Problème 2 : Fuite de Données Multi-Utilisateurs
- **Découverte** : Les répertoires de stockage (`uploads/` et `pickle/`) sont partagés globalement par toutes les sessions.
- **Cause Racine** : Absence d'isolation des données et de système d'authentification des utilisateurs.
- **Impact Métier** : Risque critique de sécurité et de non-conformité RGPD. Un utilisateur pourrait accéder aux données sensibles d'un autre.
- **Solution Proposée** : Authentification **JWT** et isolation des répertoires de fichiers par identifiant utilisateur (ID).

### Problème 3 : Sécurité de l'Exécution de Code
- **Découverte** : L'agent exécute du code Python généré par l'IA via la commande `exec()` dans l'outil `python_repl`.
- **Cause Racine** : Le code est exécuté directement sur le serveur hôte sans aucune isolation (sandbox).
- **Impact Métier** : Risque d'injection de code malveillant capable d'effacer des données serveur ou de voler des secrets d'environnement.
- **Solution Proposée** : Exécution du code dans des conteneurs **Docker** éphémères et isolés.

### Problème 4 : Goulot d'Étranglement (Scalabilité)
- **Découverte** : L'interface utilisateur Streamlit se bloque complètement pendant que l'agent génère des analyses complexes.
- **Cause Racine** : Modèle d'exécution synchrone bloquant le thread principal du serveur web.
- **Impact Métier** : Incapacité à gérer une montée en charge (plus de 2-3 utilisateurs simultanés).
- **Solution Proposée** : Architecture de file d'attente asynchrone avec **Celery** et **Redis**.

### Problème 5 : Volatilité de l'Analyse
- **Découverte** : La perte ou la corruption de fichiers `.pickle` entraîne des erreurs fatales (`GraphRecursionError`).
- **Cause Racine** : Dépendance forte entre la logique de l'agent et le système de fichiers local non indexé.
- **Impact Métier** : Instabilité du service et perte de rapports stratégiques déjà facturés à l'utilisateur.
- **Solution Proposée** : Stockage d'objets (S3) et base de données pour indexer les actifs générés.

## Architecture Cible Proposée

### Diagramme de l'Architecture
```mermaid
graph TD
    U[Utilisateur] --> API[FastAPI Gateway]
    API --> Auth[JWT Auth]
    API --> DB[(PostgreSQL: Threads & Metadata)]
    API --> Queue[Redis Task Queue]
    Queue --> Worker[Celery Worker: Agent Logic]
    Worker --> Exec[Isolated Python Sandbox]
    Worker --> Store[(S3 Storage: Files & Pickles)]   

### Décisions Techniques Clés

| Composant | Choix Technique | Raison Principale |
| :--- | :--- | :--- |
| **Backend** | FastAPI | Haute performance, support natif de l'asynchrone et documentation OpenAPI. |
| **Persistance** | PostgreSQL | Robustesse pour la gestion des fils de discussion et compatibilité avec LangGraph. |
| **Async** | Celery / Redis | Gestion efficace des tâches longues sans bloquer l'expérience utilisateur. |
| **Authentification** | JWT | Standard sécurisé pour une architecture micro-services "stateless". |
| **Sécurité** | Sandbox Docker | Isolation totale des processus d'exécution de code Python. |    
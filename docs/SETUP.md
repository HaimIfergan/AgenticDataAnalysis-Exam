# 🛠️ Guide d'Installation et Configuration - DataStream AI
#Par : Haïm IFERGAN (Formation AI LIORA  2O26)

Ce document détaille les étapes nécessaires pour configurer, installer et lancer la plateforme DataStream AI dans un environnement de développement ou de production.

---

## 📋 Prérequis

Avant de commencer, assurez-vous que les outils suivants sont installés sur votre machine :

* **Docker** (v20.10+)
* **Docker Compose** (v2.0+)
* **Git**
* **Une clé API OpenAI** valide

---
## 0.⚙️ on récupére le projet initial
git clone https://github.com/DataScientest/AgenticDataAnalysis-Exam.git

## ⚙️ Configuration de l'Environnement

Le projet utilise des variables d'environnement pour gérer les secrets et les configurations de connexion.

1.  **Créer le fichier .env** à la racine du projet :
    ```bash
    cp .env.example .env
    ```

2.  **Éditer le fichier .env** avec vos paramètres :
    ```env
    # --- IA ---
    OPENAI_API_KEY=sk-your-openai-key-here

    # --- Base de Données ---
    POSTGRES_USER=user_admin
    POSTGRES_PASSWORD=password_secure
    POSTGRES_DB=datastream_ai
    DATABASE_URL=postgresql://user_admin:password_secure@db:5432/datastream_ai

    # --- Broker Redis & Celery ---
    REDIS_URL=redis://redis:6379/0
    ```

---

## 🚀 Lancement avec Docker (Recommandé)

L'architecture est composée de 6 services interdépendants. Docker Compose orchestre automatiquement le réseau et les volumes.

### 1. Construction et démarrage
Exécutez la commande suivante à la racine :
```bash
docker-compose up --build

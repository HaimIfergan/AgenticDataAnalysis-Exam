# 🚀 DataStream AI - Plateforme d'Analyse Agentique (SaaS)

**Auteur :** Haïm IFERGAN (Formation IA 2026 - Sprint 9 - Patterns Agentiques)
**Rôle :** Senior AI Engineer Exam

---

## 📌 Aperçu du Projet
DataStream AI est une solution d'analyse de données conversationnelle conçue pour passer d'un prototype à une infrastructure de production capable de servir 500+ clients. La plateforme permet aux utilisateurs de télécharger des datasets, de poser des questions en langage naturel et d'obtenir des visualisations dynamiques via un agent intelligent.

### 🏗️ Architecture du Système
L'architecture repose sur une séparation stricte des services (microservices) pour garantir l'isolation de l'exécution et la persistance des données conformément aux exigences de l'examen.

```mermaid
graph TD
    subgraph Client_Layer
        User((Utilisateur)) --> Streamlit[Frontend Streamlit :8501]
    end

    subgraph API_Layer
        Streamlit --> FastAPI[Backend FastAPI :8000]
        FastAPI --> JWT{Auth JWT}
    end

    subgraph Async_Execution
        FastAPI --> Redis{Redis Broker :6379}
        Redis --> Worker[Celery Worker]
        Worker --> Sandbox[Python Sandbox]
        Sandbox --> Agent[LangGraph Agent]
    end

    subgraph Persistence_Layer
        FastAPI --> Postgres[(PostgreSQL :5432)]
        Worker --> Postgres
        Agent --> Postgres
    end

    subgraph Monitoring
        Worker --> Flower[Flower :5555]
    end

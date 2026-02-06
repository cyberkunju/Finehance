# Finehance — Documentation Index

This directory contains all project documentation for the AI Finance Platform.

---

## User Documentation

- **[User Guide](USER_GUIDE.md)** — End-user walkthrough covering transactions, budgets, goals, AI features, reports, and import/export

## Developer Documentation

- **[API Documentation](API_DOCUMENTATION.md)** — REST API reference for all 10 route groups (auth, transactions, budgets, goals, predictions, advice, reports, import/export, ML, AI Brain)
- **[Code Documentation](CODE_DOCUMENTATION.md)** — Codebase architecture (project structure, core components, database layer, service layer, ML pipeline, testing conventions)
- **[Database Schema](DATABASE_SCHEMA.md)** — Table definitions (users, transactions, budgets, financial_goals, ml_models, connections), relationships, indexes, query patterns

## Operations Documentation

- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** — Production deployment (Docker, cloud providers, nginx, SSL, monitoring, backup, scaling)
- **[Docker Development Guide](DOCKER_DEVELOPMENT.md)** — Local development environment (7 Docker services, Make commands, GPU setup, monitoring stack)

## Project Documentation

- **[Release Notes](RELEASE_NOTES.md)** — Version 1.0.0 release information, known issues, roadmap status
- **[README](../README.md)** — Project overview, architecture, quick start, tech stack
- **[Roadmap](../roadmap/00_ROADMAP_OVERVIEW.md)** — Production perfection roadmap (P0–P5 phases)

## AI Brain Documentation

- **[AI Brain Production Roadmap](AI_BRAIN_PRODUCTION_ROADMAP.md)** — Production readiness phases (security, reliability, observability, quality — all complete; scalability — not started). Includes RAG strategy, merchant database design, and continuous improvement loop.
- **[AI/ML Integration Guide](AI_ML_INTEGRATION.md)** — Two-tier ML + LLM architecture (TF-IDF categorization, Qwen 2.5-3B inference, RAG pipeline, all API endpoints)

## AI Brain Technical Docs (in `ai_brain/docs/`)

- **[Model Architecture](../ai_brain/docs/01_MODEL_ARCHITECTURE.md)** — Qwen 2.5-3B, QLoRA methodology, hybrid "Tag & Sum" architecture
- **[Dataset & Training](../ai_brain/docs/02_DATASET_AND_TRAINING.md)** — Sujet-Finance-Instruct-177k, ChatML format, training hyperparameters
- **[Implementation Guide](../ai_brain/docs/03_IMPLEMENTATION_GUIDE.md)** — Prompt patterns, strict mode, JSON output, Python post-processing
- **[Performance Report](../ai_brain/docs/04_PERFORMANCE_REPORT.md)** — Raw vs fine-tuned comparison (70% → 95% accuracy)

---

## Quick Links

| Audience | Start Here |
|----------|-----------|
| **End users** | [User Guide](USER_GUIDE.md) |
| **Developers** | [Docker Development Guide](DOCKER_DEVELOPMENT.md) → [Code Documentation](CODE_DOCUMENTATION.md) → [API Documentation](API_DOCUMENTATION.md) |
| **DevOps** | [Deployment Guide](DEPLOYMENT_GUIDE.md) |
| **AI/ML engineers** | [AI/ML Integration Guide](AI_ML_INTEGRATION.md) → [ai_brain/ docs](../ai_brain/docs/) |

---

**Repository**: [github.com/cyberkunju/Finehance](https://github.com/cyberkunju/Finehance)  
**Last Updated**: February 2026

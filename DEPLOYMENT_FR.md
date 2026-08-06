# Déployer CasinoAI facilement

## Option 1 — Windows local

1. Installer Python 3.11 ou 3.12 depuis `python.org` et cocher **Add Python to PATH**.
2. Décompresser le projet.
3. Double-cliquer sur `run.bat`.
4. Attendre l'installation initiale des bibliothèques.
5. Ouvrir `http://localhost:8501`.

Le script accepte aussi le lanceur Windows `py -3` lorsque la commande `python` n'est pas disponible.

## Option 2 — macOS ou Linux

```bash
chmod +x run.sh
./run.sh
```

Puis ouvrir `http://localhost:8501`.

## Ouvrir sur un iPhone

L'ordinateur et l'iPhone doivent utiliser le même Wi-Fi.

1. Lancer CasinoAI sur l'ordinateur.
2. Trouver l'adresse IPv4 de l'ordinateur avec `ipconfig` sous Windows ou `ifconfig` sous macOS/Linux.
3. Dans Safari, ouvrir `http://ADRESSE_IP:8501`, par exemple `http://192.168.1.42:8501`.
4. Si nécessaire, autoriser Python dans le pare-feu pour les réseaux privés.

Le fichier `.streamlit/config.toml` écoute déjà sur `0.0.0.0`.

## Option 3 — Streamlit Community Cloud

1. Créer un dépôt GitHub.
2. Envoyer tous les fichiers du projet, y compris `data/gambit_iq.db`.
3. Ouvrir `https://share.streamlit.io`.
4. Sélectionner le dépôt, la branche et `app.py`.
5. Choisir Python 3.12 et lancer le déploiement.

Aucun secret n'est requis pour cette démonstration. La base incluse contient uniquement des données synthétiques. Les modèles Joblib déjà entraînés sont également inclus ; le premier démarrage peut les reconstruire si la base est absente ou incompatible.

## Contrôle après déploiement

- La page **Command Center** doit afficher quatre KPI et quatre graphiques.
- Le menu doit contenir neuf pages.
- Les filtres de dates et de pays doivent rafraîchir les résultats.
- Les tables `model_scores` et `model_metrics` doivent exister dans SQLite.
- La page **AI Copilot** doit accepter une question, trois paramètres de scénario et une approbation simulée.
- Le badge **All systems operational** doit rester visible dans la barre latérale.

## Passage en production

Ne pas utiliser cette version avec de vraies données joueurs. Avant une production réelle, ajouter : authentification, isolation multi-tenant, PostgreSQL, chiffrement, journal d'audit, gestion des secrets, sauvegardes, monitoring, tests de sécurité et validation juridique/réglementaire.

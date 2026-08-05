# GAMBIT IQ — Rapport QA

Date de validation : 5 août 2026

## Résultat

**Statut : PASS — MVP local prêt à être lancé et déployé avec des données synthétiques.**

## Tests réalisés

- Compilation de tous les modules Python.
- Installation depuis `requirements.txt` dans un environnement virtuel vierge.
- Vérification de l'intégrité SQLite avec `PRAGMA integrity_check`.
- Régénération complète de la base depuis zéro.
- Test automatisé des neuf routes avec Streamlit AppTest après la migration SQL.
- Test automatisé des neuf pages avec les filtres « All markets » et « Canada ».
- Vérification des requêtes SQL paramétrées par période et pays, y compris la période précédente de même durée.
- Vérification des états sans données et suppression des accès `.iloc` dangereux avant contrôle.
- Vérification des formats monétaires, pourcentages, dates et scores dans les tableaux principaux.
- Vérification de la cohérence couleur : vert = favorable, or = vigilance, rouge = risque.
- Vérification responsive : colonnes empilées et tableaux défilables sous 768 px.
- Remplacement des valeurs décoratives non justifiées par des données filtrées, des estimations explicitement nommées ou des explications.
- Validation de la gouvernance KPI version 1.1 : statuts Observed/Estimated/Predicted et infobulles complètes.
- Validation SQL des cohortes matures FTD Conversion D30 et Observed Retention D30.
- Réconciliation du signe RTP `Actual − Theoretical` entre les faits et le data mart.
- Validation de la navigation groupée Executive, Customers, Performance et Operations.
- Validation des neuf routes, des icônes, de l'état actif natif et de la persistance des filtres globaux.
- Validation du bouton natif de réduction de la barre latérale avec la navigation explicite Streamlit.
- Reconstruction idempotente des couches raw, staging, dimensions, facts, intermediate et marts.
- Réconciliation des volumes raw/facts, des clés étrangères et du GGR raw/fact/mart.
- Entraînement réel de cinq pipelines scikit-learn et persistance Joblib.
- Vérification des bornes `[0,1]` des probabilités et de la table `model_metrics`.
- Recherche d'exceptions, tracebacks et avertissements d'API dépréciées.
- Vérification de l'archive ZIP.

## Volumes validés

| Table | Lignes |
|---|---:|
| players | 8 000 |
| games | 6 |
| sessions | 72 000 |
| transactions | 31 000 |
| sports_bets | 48 000 |
| model_scores | 6 719 joueurs éligibles au cutoff |

## Architecture SQL validée

- `raw_*` : cinq tables sources avec identifiants uniques.
- `stg_*` : cinq vues standardisées sans agrégation.
- `dim_*` : joueur, jeu et calendrier.
- `fact_*` : 72 000 sessions, 31 000 transactions et 48 000 paris.
- `int_*` : FTD, première activité, activité quotidienne et revenu quotidien.
- `mart_*` : executive, jeux, acquisition, paiements et Player 360.
- Journal technique : `pipeline_runs`.

## Rendu vérifié structurellement

| Page | KPI | Graphiques | Tables/éléments interactifs |
|---|---:|---:|---:|
| Command Center | 4 | 4 | — |
| Player Intelligence | 10 | 3 | 2 tables + joueur |
| Casino Games | 5 | 3 | 1 table |
| Sportsbook & Trading | 5 | 3 | 1 table |
| Acquisition | 5 | 2 | 1 table |
| CRM Automation | 5 | 2 | 1 table + parcours |
| Revenue & Finance | 5 | 5 | 1 table |
| Risk & Compliance | 5 | 3 | 1 table |
| AI Copilot | 5 | 2 | table, question, 3 sliders, bouton |

## Métriques du run validé

| Modèle | Métrique principale |
|---|---:|
| Churn | ROC AUC 0,7361 |
| Fraud | ROC AUC 0,5926 |
| Responsible gaming | ROC AUC 0,8854 |
| LTV | MAE 219,44 · R² 0,0746 |
| Revenue forecast | MAE 5 578,75 · R² -1,3894 |

## Limite volontaire

Il s'agit d'un MVP de démonstration. Les modèles sont réellement entraînés, mais uniquement sur des données synthétiques : leurs métriques prouvent le fonctionnement technique, pas une performance commerciale en production. Les décisions commerciales et de protection doivent toujours être revues humainement.

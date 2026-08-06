from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.shared.config import RANDOM_STATE
from ml.shared.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def preprocessor() -> ColumnTransformer:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)])


def classifier() -> Pipeline:
    return Pipeline([("preprocess", preprocessor()), ("model", HistGradientBoostingClassifier(
        learning_rate=.085, max_iter=70, max_leaf_nodes=24, min_samples_leaf=30,
        l2_regularization=1.2, class_weight="balanced", random_state=RANDOM_STATE,
    ))])


def regressor() -> Pipeline:
    return Pipeline([("preprocess", preprocessor()), ("model", HistGradientBoostingRegressor(
        loss="absolute_error", learning_rate=.085, max_iter=70, max_leaf_nodes=24,
        min_samples_leaf=25, l2_regularization=1.0, random_state=RANDOM_STATE,
    ))])

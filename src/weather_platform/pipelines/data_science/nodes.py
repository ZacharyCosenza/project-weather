import pandas as pd
import numpy as np
import optuna
import shap
import matplotlib.pyplot as plt
from typing import Tuple, Dict, Any
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error


def prepare_model_data(
    primary_data: pd.DataFrame,
    params: Dict[str, Any]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_columns = params['feature_columns']
    target_column = params['target_column']

    X = primary_data[feature_columns]
    y = primary_data[target_column]

    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=params['test_size'],
        random_state=params['random_state']
    )

    val_size_adjusted = params['val_size'] / (1 - params['test_size'])
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_size_adjusted,
        random_state=params['random_state']
    )

    train_data = X_train.copy()
    train_data[target_column] = y_train

    val_data = X_val.copy()
    val_data[target_column] = y_val

    test_data = X_test.copy()
    test_data[target_column] = y_test

    return train_data, val_data, test_data


def train_model(
    train_data: pd.DataFrame,
    val_data: pd.DataFrame,
    params: Dict[str, Any]
) -> XGBRegressor:
    feature_columns = params['feature_columns']
    target_column = params['target_column']

    X_train = train_data[feature_columns]
    y_train = train_data[target_column]
    X_val = val_data[feature_columns]
    y_val = val_data[target_column]

    def objective(trial):
        search_space = params['optuna']['search_space']
        param = {
            'n_estimators': trial.suggest_int('n_estimators', search_space['n_estimators']['low'], search_space['n_estimators']['high']),
            'max_depth': trial.suggest_int('max_depth', search_space['max_depth']['low'], search_space['max_depth']['high']),
            'learning_rate': trial.suggest_float('learning_rate', search_space['learning_rate']['low'], search_space['learning_rate']['high'], log=True),
            'subsample': trial.suggest_float('subsample', search_space['subsample']['low'], search_space['subsample']['high']),
            'colsample_bytree': trial.suggest_float('colsample_bytree', search_space['colsample_bytree']['low'], search_space['colsample_bytree']['high']),
            'random_state': params['random_state'],
            'verbosity': 0
        }
        model = XGBRegressor(**param)
        model.fit(X_train, y_train)
        return mean_squared_error(y_val, model.predict(X_val))

    if params['optuna']['flag_use_optuna']:
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=params['optuna']['n_trials'], timeout=params['optuna']['timeout'], show_progress_bar=True)
        best_params = {**study.best_params, 'random_state': params['random_state'], 'verbosity': 0}
        model = XGBRegressor(**best_params)
    else:
        model = XGBRegressor()

    model.fit(X_train, y_train)
    return model


def evaluate_model(model: XGBRegressor, test_data: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, float]:
    feature_columns = params['feature_columns']
    target_column = params['target_column']

    X_test = test_data[feature_columns]
    y_test = test_data[target_column]
    y_pred = model.predict(X_test)

    mse = mean_squared_error(y_test, y_pred)
    return {
        "mse": float(mse),
        "rmse": float(np.sqrt(mse)),
        "mae": float(np.mean(np.abs(y_test - y_pred))),
    }


def generate_shap_plot(model: XGBRegressor, test_data: pd.DataFrame, params: Dict[str, Any]) -> plt.Figure:
    feature_columns = params['feature_columns']
    X_test = test_data[feature_columns]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X_test)

    fig, ax = plt.subplots(figsize=(12, 8))
    shap.plots.beeswarm(shap_values, show=False)
    plt.title("SHAP Feature Importance")
    plt.tight_layout()
    return fig

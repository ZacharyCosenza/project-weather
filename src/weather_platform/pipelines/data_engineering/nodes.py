import pandas as pd


def create_features(raw_data: pd.DataFrame, params: dict) -> pd.DataFrame:
    df = raw_data.copy()
    df['valid'] = pd.to_datetime(df['valid'], errors='coerce')
    df['tmpf'] = pd.to_numeric(df['tmpf'], errors='coerce')
    df = df.dropna(subset=['valid', 'tmpf']).sort_values('valid')

    reference_date = pd.Timestamp(params['reference_date'])
    num_lags = params['num_lags']

    df['ft_month'] = df['valid'].dt.month
    df['ft_day'] = df['valid'].dt.day
    df['ft_hour'] = df['valid'].dt.hour
    df['ft_days_since_2000'] = (df['valid'] - reference_date).dt.total_seconds() / (24 * 3600)
    df['ft_temp'] = df['tmpf']

    for i in range(1, num_lags + 1):
        df[f'ft_temp_lag_{i}h'] = df['tmpf'].shift(i)

    df['tgt_tmpf'] = df['tmpf'].shift(-1) # predict the next hour

    feature_cols = ['ft_month',  # normal features
                    'ft_day', 
                    'ft_hour', 
                    'ft_days_since_2000', 
                    'ft_temp']
    
    feature_cols_no_NAN = [f'ft_temp_lag_{i}h' for i in range(1, num_lags + 1)]
    feature_cols.append('tgt_tmpf')

    df = df[feature_cols + feature_cols_no_NAN]
    df = df.dropna(subset = feature_cols) # need to allow for NULL temps

    return df
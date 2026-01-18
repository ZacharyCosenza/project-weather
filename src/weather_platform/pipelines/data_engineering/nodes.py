import pandas as pd


def create_features(raw_data: pd.DataFrame) -> pd.DataFrame:
    df = raw_data.copy()
    df['valid'] = pd.to_datetime(df['valid'], errors='coerce')
    df['tmpf'] = pd.to_numeric(df['tmpf'], errors='coerce')
    df = df.dropna(subset=['valid', 'tmpf']).sort_values('valid')

    df['ft_month'] = df['valid'].dt.month
    df['ft_day'] = df['valid'].dt.day
    df['ft_hour'] = df['valid'].dt.hour
    df['ft_temp'] = df['tmpf']
    df['tgt_tmpf'] = df['tmpf'].shift(-1)

    return df[['ft_month', 'ft_day', 'ft_hour', 'ft_temp', 'tgt_tmpf']].dropna()

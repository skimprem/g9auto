import os
import pandas as pd

df_path = os.path.join(
    os.path.expanduser('~'),
    'gitrepo',
    'kazakhstan_gravity_reference_frame_article',
    'src',
    'absolute',
    'qazgrf24.csv'
)

df = pd.read_csv(df_path, sep=';')

print(df.columns)

print(
    df.loc[
        (df['method'] == 'absolute') & (df['order'] == 'first'),
        [
            'station',
            'point',
            'gravity_eff',
            'total_uncert',
        ]
    ].to_markdown(floatfmt='.1f', index=False)
)
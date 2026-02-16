import os
import json
import pandas as pd
import numpy as np
from logger import setup_logging
from utils import get_full_path, expand_dataframe_with_fg5_files, add_comments
from loader import read_project

# get config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# Setup logging from config
logging_config = config.get('logging', {})
setup_logging(
    log_dir=logging_config.get('log_dir', 'logs'),
    verbose=logging_config.get('verbose', True),
    log_to_file=logging_config.get('log_to_file', True)
)

# get paths
info_path = config['paths']['info_path']
data_path = config['paths']['data_path']

comments_file = os.path.join(info_path, config['paths']['comments_file'])
comments_text = open(comments_file, 'r', encoding='utf-8').read()

first_path = os.path.join(info_path, config['paths']['first_absolute_file'])
zero_path = os.path.join(info_path, config['paths']['zero_absolute_file'])

df_first = pd.read_csv(first_path, sep=';')
df_first['order'] = 'first'
df_zero = pd.read_csv(zero_path, sep=';')
df_zero['order'] = 'zero'

df = pd.concat([df_first, df_zero], ignore_index=True)

df['full_path'] = df.apply(lambda row: get_full_path(data_path, row['order'], row['station'], row['point']), axis=1)

# search *.fg5 and expand dataframe
df_ex = expand_dataframe_with_fg5_files(df, 'full_path')

# add comments
df_ex['comments'] = df_ex.apply(lambda row: add_comments(row, comments_text), axis=1)

output_file = os.path.join(config['paths']['output_dir'], 'expanded_data.json')
os.makedirs(config['paths']['output_dir'], exist_ok=True)
df_ex.to_json(output_file, orient='records')

# get specific station
df_ex = df_ex[df_ex['order'].isin(['zero'])]
df_ex = df_ex[df_ex['station'].isin(['talg'])]
# df_ex = df_ex[df_ex['station'].isin(['agad'])]
# df_ex = df_ex[~df_ex['station'].isin(
#     [
#         'agad',
#         'aksa',
#         'aksu',
#         'akto',
#         'arka',
#         'atba',
#         'ayag',
#         'baik',
#         'best',
#         'beyn',
#         'bola',
#         'brsh',
#         'chel',
#         'dlin',
#         'ekib',
#         'elta',
#         'emba',
#         'esil',
#         'evge',
#         'fshe',
#         'gany',
#         'inde',
#         'kara',
#         'kark',
#         'kaul',
#         'kazt',
#         'kege',
#     ])]

# run application
# run_app(df_ex, config)

df_ex.to_csv(os.path.join(config['paths']['output_dir'], 'expanded_data.csv'), index=False)

result = pd.read_csv(
    os.path.join(
        '..',
        'kazakhstan_gravity_reference_frame_article',
        'src',
        'absolute',
        'qazgrf24.csv',
    ),
    sep=';',
    encoding='utf-8'
)

result['station_point'] = result['station'] + '_' + result['point'].apply(str.strip).astype(str)

result.set_index('station_point', inplace=True)

for station_point_date, grouped in df_ex.groupby(['station', 'point', 'session_date']):

    station, point, date = station_point_date

    # print((row.fg5_file, row.station, row.point))

    ref_point = result.loc[station + '_' + str(point).strip()]

    gravities = []; errors = []

    for row in grouped.itertuples():
        try:
            project_file = os.path.splitext(row.fg5_file)[0] + '.project.txt'

            if os.path.isfile(project_file):

                values, names = read_project(project_file)

                gravities.append(values[
                        (
                            'Processing Results',
                            'Gravity',
                            'µGal'
                        )
                    ]
                )
                errors.append(values[
                        (
                            'Processing Results',
                            'Measurement Precision',
                            'µGal'
                        )
                    ]
                )

        except TypeError as e:
            print((station, point, row.fg5_file, e))
            pass
 
    try:
        if len(gravities) > 0:
            diff = np.average(gravities, weights=np.array(errors)**-2) - ref_point.gravity_eff
        else:
            diff = gravities[0] - ref_point.gravity_eff

        if abs(diff) > 1:
            print(station, point, date, diff)
    except Exception as e:
        # print(f"Error calculating difference for station {station}: {e}")
        pass
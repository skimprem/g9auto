import os
import json
import pandas as pd
from functions import get_full_path, expand_dataframe_with_fg5_files
from functions import add_comments, run_app

# get config
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

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
df_ex = df_ex[df_ex['order'].isin(['first'])]
df_ex = df_ex[df_ex['station'].isin(['agad'])]
# df_ex = df_ex[~df_ex['station'].isin(
#     [
#         'agad',
#         'aksa',
#         'aksu',
#         'akto'
#     ])]

# run application
run_app(df_ex, config)

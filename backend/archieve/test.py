import pandas as pd
import numpy as np

missing_values_to_replace = [
    '',        # 空字符串
    ' ',       # 单个空格 (可以多加几个，如 '  ')
    '  ',
    'nan',     # 字符串 'nan'
    'None',    # 字符串 'None'
    'NULL'     # 字符串 'NULL'
]

file_path = "../data_test/ref_BOM.xlsx"

df = pd.read_excel(file_path).replace(missing_values_to_replace, np.nan)

data_clean = df.dropna(subset=['物料编码', '物料名称', '产品配置'])

data = data_clean[['物料编码', '物料名称', '产品配置']].drop_duplicates()

record = data.to_markdown()

with open('../data_test/ref_BOM.md', 'w') as f:
    f.write(record)

print(record)
import json
import os

fp = r'c:\Users\Galang\Documents\Project App\GC Toxic Shield\assets\word_list.json'
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Add new words as requested
if 'anjing' not in data['toxic_words']:
    data['toxic_words']['anjing'] = ['anjeng', 'anjg', 'ajg', 'anj']
if 'bangsat' not in data['toxic_words']:
    data['toxic_words']['bangsat'] = ['bangsad', 'bngst', 'bgst']
if 'tolol' not in data['toxic_words']:
    data['toxic_words']['tolol'] = ['tll', 'tololll']
if 'babi' not in data['toxic_words']:
    data['toxic_words']['babi'] = ['bby', 'babik']
if 'goblok' not in data['toxic_words']:
    data['toxic_words']['goblok'] = ['gblk', 'goblog']

with open(fp, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
print("word_list.json updated!")

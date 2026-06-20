# -*- coding: utf-8 -*-
"""
Preload existing source files into TVproxy.
Run once to seed the database with channels.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import state, process_entries, save_state
from importer.txt_import import parse_txt
from channel_manager.matcher import get_merge_stats
from channel_manager.health import check_urls

BASE = r'C:\Users\yu\Desktop\github仓库\电视直播'

files = [
    os.path.join(BASE, '汇总all.txt'),
    os.path.join(BASE, '合成.txt'),
    os.path.join(BASE, 'tv.txt'),
]

total_entries = 0
for fp in files:
    if not os.path.exists(fp):
        print(f'[SKIP] Not found: {fp}')
        continue
    try:
        entries = parse_txt(fp)
        if entries:
            merged = process_entries(entries)
            stats = get_merge_stats(merged)
            total_entries += len(entries)
            fname = os.path.basename(fp)
            print(f'[OK] {fname}: {len(entries)} entries -> {stats["channels"]} channels')
            if fname not in state['source_files']:
                state['source_files'].append(fname)
        else:
            print(f'[EMPTY] {os.path.basename(fp)}: no valid entries')
    except Exception as e:
        print(f'[ERR] {os.path.basename(fp)}: {e}')

save_state()
print(f'\nPreload complete!')
print(f'  Channels: {len(state["channels"])}')
total_u = sum(len(u) for u in state['channels'].values())
print(f'  Total URLs: {total_u}')
print(f'\nRun "python app.py" to start the proxy server.')
print(f'TXT subscription: http://localhost:5000/api/export/txt')
print(f'M3U subscription: http://localhost:5000/api/export/m3u')

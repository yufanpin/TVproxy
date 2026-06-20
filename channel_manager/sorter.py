# -*- coding: utf-8 -*-
"""
Custom sorting for CCTV channels and others.
"""

import re
from .normalizer import CCTV_STANDARD, CCTV_PAID_STANDARD


# ── CCTV Number Order ──
CCTV_NUM_ORDER = {}
for i, num in enumerate(['1', '2', '3', '4', '5', '5+', '6', '7', '8', '9',
                          '10', '11', '12', '13', '14', '15', '16', '17']):
    CCTV_NUM_ORDER[num] = i + 1

# Paid channel order
PAID_ORDER_LIST = [
    'CCTV-第一剧场', 'CCTV-风云剧场', 'CCTV-怀旧剧场',
    'CCTV-世界地理', 'CCTV-兵器科技', 'CCTV-央视文化精品',
    'CCTV-央视台球', 'CCTV-电视指南', 'CCTV-女性时尚',
    'CCTV-风云音乐', 'CCTV-风云足球', 'CCTV-高尔夫网球',
]
PAID_ORDER = {name: i + 20 for i, name in enumerate(PAID_ORDER_LIST)}

# Category sort priority
CAT_PRIORITY = {
    '央视频道': 1,
    '卫视频道': 2,
    '少儿频道': 3,
    '影视频道': 4,
    '其他频道': 5,
}


def sort_key(name, category):
    """
    Generate sort key for a channel name within its category.
    """
    cat_pri = CAT_PRIORITY.get(category, 99)
    
    # CCTV numbered channels
    m = re.match(r'^CCTV-(\d[\d+]*)\b', name)
    if m:
        num = m.group(1)
        order = CCTV_NUM_ORDER.get(num, 50)
        return (cat_pri, 1, order, name)
    
    # CCTV paid channels
    for paid_name, order in PAID_ORDER.items():
        if name == paid_name:
            return (cat_pri, 2, order, name)
    
    # CETV
    m = re.match(r'^CETV-(\d+)', name)
    if m:
        return (cat_pri, 3, int(m.group(1)), name)
    
    # CNC
    if name.startswith('CNC'):
        order = 1 if '中文' in name else 2
        return (cat_pri, 4, order, name)
    
    # CGTN
    if name.startswith('CGTN'):
        return (cat_pri, 5, 0, name)
    
    # 卫视: sorted by pinyin or name
    if category == '卫视频道':
        return (cat_pri, 6, 0, name)
    
    # Default: alphabetical
    return (cat_pri, 7, 0, name)


def sort_channels(channels_by_cat):
    """
    Sort channels within each category.
    
    Args:
        channels_by_cat: OrderedDict {category: [(name, [urls]), ...]}
    
    Returns:
        OrderedDict with sorted entries
    """
    from collections import OrderedDict
    
    result = OrderedDict()
    for cat, entries in channels_by_cat.items():
        if not entries:
            continue
        sorted_entries = sorted(entries, key=lambda x: sort_key(x[0], cat))
        result[cat] = sorted_entries
    
    return result

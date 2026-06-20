# -*- coding: utf-8 -*-
"""
Channel categorization.
Groups channels into: 央视频道, 卫视频道, 少儿频道, 影视频道, 其他频道
"""

CATEGORY_ORDER = [
    '央视频道',
    '卫视频道',
    '少儿频道',
    '影视频道',
    '其他频道',
]


def categorize(name):
    """Determine which category a channel belongs to."""
    if name.startswith('CCTV-') or name.startswith('CCTV'):
        if name.startswith('CGTN'):
            return '其他频道'
        return '央视频道'
    if name.startswith('CETV-') or name.startswith('CETV'):
        return '央视频道'
    if name.startswith('CNC'):
        return '央视频道'
    if name.endswith('卫视') or '卫视' in name:
        return '卫视频道'
    if name in ['凤凰中文', '凤凰资讯', '凤凰香港']:
        return '卫视频道'
    # Kids channels
    kids_keywords = ['卡通', '动画', '宝贝', '少儿', '炫动']
    if any(k in name for k in kids_keywords):
        return '少儿频道'
    # Movie/Drama channels
    movie_keywords = ['CHC', '电影', '剧场', '影院', '大剧', '影视', '电视剧', '热剧']
    if any(k in name for k in movie_keywords):
        return '影视频道'
    # Variety/entertainment
    if any(k in name for k in ['综艺', '大片', '选播', '精选', '必看']):
        return '其他频道'
    if name.startswith('CGTN'):
        return '其他频道'
    return '其他频道'


def categorize_channels(channels_dict):
    """
    Group channels by category.
    
    Args:
        channels_dict: {standard_name: [urls]}
    
    Returns:
        OrderedDict: {category: [(name, [urls]), ...]}
    """
    from collections import OrderedDict
    
    groups = OrderedDict()
    for cat in CATEGORY_ORDER:
        groups[cat] = []
    
    # Sort channels within category by name
    sorted_names = sorted(channels_dict.keys())
    
    for name in sorted_names:
        cat = categorize(name)
        if cat not in groups:
            cat = '其他频道'
        groups[cat].append((name, channels_dict[name]))
    
    return groups

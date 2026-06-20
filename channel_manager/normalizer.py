# -*- coding: utf-8 -*-
"""
Channel name normalization.
Maps various naming conventions to a standard form.
"""

import re

# ── CCTV Numbered Channels ──
CCTV_STANDARD = {
    '1': 'CCTV-1 综合',
    '2': 'CCTV-2 财经',
    '3': 'CCTV-3 综艺',
    '4': 'CCTV-4 中文国际',
    '5': 'CCTV-5 体育',
    '5+': 'CCTV-5+ 体育赛事',
    '6': 'CCTV-6 电影',
    '7': 'CCTV-7 国防军事',
    '8': 'CCTV-8 电视剧',
    '9': 'CCTV-9 纪录',
    '10': 'CCTV-10 科教',
    '11': 'CCTV-11 戏曲',
    '12': 'CCTV-12 社会与法',
    '13': 'CCTV-13 新闻',
    '14': 'CCTV-14 少儿',
    '15': 'CCTV-15 音乐',
    '16': 'CCTV-16 奥林匹克',
    '17': 'CCTV-17 农业农村',
}

CCTV_PAID_STANDARD = {
    '第一剧场': 'CCTV-第一剧场',
    '风云剧场': 'CCTV-风云剧场',
    '怀旧剧场': 'CCTV-怀旧剧场',
    '世界地理': 'CCTV-世界地理',
    '兵器科技': 'CCTV-兵器科技',
    '央视文化精品': 'CCTV-央视文化精品',
    '央视台球': 'CCTV-央视台球',
    '电视指南': 'CCTV-电视指南',
    '女性时尚': 'CCTV-女性时尚',
    '风云音乐': 'CCTV-风云音乐',
    '风云足球': 'CCTV-风云足球',
    '高尔夫网球': 'CCTV-高尔夫网球',
}

CCTV_NUM_MAP = {v: k for k, v in CCTV_STANDARD.items()}

# ── CGTN ──
CGTN_STANDARD = {
    'CGTN': 'CGTN',
    'CGTN新闻': 'CGTN 新闻',
    'CGTN纪录': 'CGTN 纪录',
    'CGTN法语': 'CGTN 法语',
    'CGTN西语': 'CGTN 西语',
    'CGTN阿语': 'CGTN 阿语',
    'CGTN俄语': 'CGTN 俄语',
}

# ── CETV ──
CETV_STANDARD = {
    '1': 'CETV-1',
    '2': 'CETV-2',
    '3': 'CETV-3',
    '4': 'CETV-4',
}

# ── CNC ──
CNC_STANDARD = {
    'CNC中文': 'CNC 中文',
    'CNC英文': 'CNC 英文',
    'CNC英语': 'CNC 英文',
}

# ── Provincial satellite channels ──
WEISHI_MAP = {
    '北京': '北京卫视', '天津': '天津卫视', '河北': '河北卫视',
    '山西': '山西卫视', '内蒙古': '内蒙古卫视', '辽宁': '辽宁卫视',
    '吉林': '吉林卫视', '黑龙江': '黑龙江卫视', '上海': '东方卫视',
    '江苏': '江苏卫视', '浙江': '浙江卫视', '安徽': '安徽卫视',
    '福建': '东南卫视', '江西': '江西卫视', '山东': '山东卫视',
    '河南': '河南卫视', '湖北': '湖北卫视', '湖南': '湖南卫视',
    '广东': '广东卫视', '广西': '广西卫视', '海南': '海南卫视',
    '重庆': '重庆卫视', '四川': '四川卫视', '贵州': '贵州卫视',
    '云南': '云南卫视', '西藏': '西藏卫视', '陕西': '陕西卫视',
    '甘肃': '甘肃卫视', '青海': '青海卫视', '宁夏': '宁夏卫视',
    '新疆': '新疆卫视', '兵团': '兵团卫视', '康巴': '康巴卫视',
    '安多': '安多卫视', '延边': '延边卫视',
    # Aliases
    '东南': '东南卫视', '东方': '东方卫视', '三沙': '三沙卫视',
    '厦门': '厦门卫视', '深圳': '深圳卫视', '大湾区': '大湾区卫视',
    '南方': '大湾区卫视', '山东教育': '山东教育卫视',
    '农林': '农林卫视',
}

# ── Kids channels ──
KIDS_STANDARD = {
    '金鹰卡通': '金鹰卡通',
    '卡酷少儿': '卡酷少儿',
    '嘉佳卡通': '嘉佳卡通',
    '优漫卡通': '优漫卡通',
    '哈哈炫动': '哈哈炫动',
    '动画世界': '动画世界',
    '黑莓动画': '黑莓动画',
    '优优宝贝': '优优宝贝',
}

# ── Movie/Drama channels ──
MOVIE_STANDARD = {
    'CHC动作电影': 'CHC动作电影',
    'CHC家庭影院': 'CHC家庭影院',
    'CHC影迷电影': 'CHC影迷电影',
    '超级电影': '超级电影',
    '超级电视剧': '超级电视剧',
    '黑莓电影': '黑莓电影',
    '黑莓电视剧': '黑莓电视剧',
    '军旅剧场': '军旅剧场',
    '古装剧场': '古装剧场',
    '家庭剧场': '家庭剧场',
    '欢乐剧场': '欢乐剧场',
    '海外剧场': '海外剧场',
    '品质大剧': '品质大剧',
    '精品大剧': '精品大剧',
    '精品影视': '精品影视',
    '畅想影院': '畅想影院',
    '畅享影院': '畅享影院',
    '精品综艺': '精品综艺',
    '金牌综艺': '金牌综艺',
    '明星大片': '明星大片',
    '追番必看': '追番必看',
    '热播精选': '热播精选',
    '东北热剧': '东北热剧',
}

# ── Known exclude patterns ──
EXCLUDE_PATTERNS = [
    r'江西都市', r'南昌\d*', r'九江\d*', r'赣州\d*',
    r'景德镇', r'萍乡\d*', r'新余\d*', r'鹰潭\d*',
    r'宜春\d*', r'上饶\d*', r'吉安\d*', r'抚州\d*',
    r'咪咕', r'精品综合', r'精品体育', r'怡伴健康',
    r'哒啵', r'睛彩', r'4K超高清',
]


def strip_suffixes(name):
    """Remove common HD/source quality suffixes."""
    name = re.sub(r'[\s-]*(高清|标清|超清|HD|SD|FHD|UHD|4K|8K|HLS|TS)$', '', name, flags=re.I).strip()
    return name


def normalize(name):
    """
    Normalize a channel name to its standard form.
    Returns (normalized_name, is_excluded)
    """
    original = name
    name = name.strip()
    
    # Check exclusion patterns
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, name):
            return None, True
    
    # Strip quality suffixes
    name = strip_suffixes(name)
    
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    # ── CCTV numbered channels ──
    # Match patterns like: CCTV1, CCTV-1, CCTV-1综合, cctv1, CCTV 1 综合
    m = re.match(r'^[Cc][Cc][Tt][Vv][\s-]*(\d[\d+]*)\s*(.*)', name)
    if m:
        num = m.group(1).strip()
        suffix = m.group(2).strip()
        if num in CCTV_STANDARD:
            return CCTV_STANDARD[num], False
        if num == '5+' or num == '5加':
            return CCTV_STANDARD['5+'], False
        # If suffix matches a standard suffix
        if suffix:
            for std_suffix, std_name in CCTV_PAID_STANDARD.items():
                if std_suffix in suffix:
                    return std_name, False
        return None, False  # Unknown CCTV number
    
    # ── CCTV without number (paid channels) ──
    m = re.match(r'^[Cc][Cc][Tt][Vv][\s-]*(.+)', name)
    if m:
        rest = m.group(1).strip()
        for kw, std in CCTV_PAID_STANDARD.items():
            if kw in rest:
                return std, False
        return None, False
    
    # ── CGTN ──
    m = re.match(r'^[Cc][Gg][Tt][Nn]\s*(.*)', name)
    if m:
        suffix = m.group(1).strip()
        for key, std in CGTN_STANDARD.items():
            if suffix in key or key in name:
                return std, False
        return 'CGTN', False
    
    # ── CETV ──
    m = re.match(r'^[Cc][Ee][Tt][Vv][\s-]*(\d+)', name)
    if m:
        num = m.group(1)
        if num in CETV_STANDARD:
            return CETV_STANDARD[num], False
        return f'CETV-{num}', False
    
    # ── CNC ──
    m = re.match(r'^[Cc][Nn][Cc]\s*(.*)', name)
    if m:
        suffix = m.group(1).strip()
        for key, std in CNC_STANDARD.items():
            if suffix in key or key in name:
                return std, False
        return 'CNC 中文', False
    
    # ── Provincial satellite channels ──
    for province, std_name in WEISHI_MAP.items():
        if province in name:
            return std_name, False
    
    # ── Kids channels ──
    for key, std_name in KIDS_STANDARD.items():
        if key in name:
            return std_name, False
    
    # ── Movie/Drama channels ──
    for key, std_name in MOVIE_STANDARD.items():
        if key in name:
            return std_name, False
    
    # ── Phoenix TV ──
    if '凤凰中文' in name:
        return '凤凰中文', False
    if '凤凰资讯' in name:
        return '凤凰资讯', False
    if '凤凰香港' in name or '凤凰卫视' in name:
        return '凤凰香港', False
    
    # ── NewTV / other ──
    if '新动漫' in name:
        return '新动漫', False
    
    # ── If nothing matched, check if it's something we should exclude ──
    # Local channels (非卫视的地方台)
    if any(kw in name for kw in ['都市', '公共', '经济', '生活', '科教', '影视', '文体',
                                   '新闻', '综合', '教育', '少儿', '电影', '电视剧',
                                   '文旅', '国际', '移动', '导视']):
        # Only keep if it starts with CCTV or is a known sat
        if not any(p in name for p in ['北京', '上海', '广东', '深圳']):
            return None, True  # Likely a local sub-channel
    
    # If it contains provincial name but not 卫视, might be local
    provinces = ['北京', '天津', '上海', '重庆', '河北', '山西', '辽宁', '吉林',
                 '黑龙江', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
                 '湖北', '湖南', '广东', '海南', '四川', '贵州', '云南', '陕西',
                 '甘肃', '青海', '台湾', '广西', '内蒙古', '西藏', '宁夏', '新疆']
    for p in provinces:
        if p in name and '卫视' not in name:
            return None, True
    
    # Unknown but keep it (user might add custom mapping)
    return name, False

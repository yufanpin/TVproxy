# -*- coding: utf-8 -*-
"""
Fetch TV channel logos from vircloud/TVLogo GitHub repo.
Downloads all .png files into tvlogo/ folder.
"""
import json
import os
import sys
import urllib.request
import urllib.error

REPO_API = 'https://api.github.com/repos/vircloud/TVLogo/git/trees/main?recursive=1'
RAW_BASE = 'https://raw.githubusercontent.com/vircloud/TVLogo/main/'
TVLOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tvlogo')

# Our 104 channel names from channels.json (normalized)
CHANNELS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'channels.json')

# Mapping of virCloud filename patterns -> our channel names
# Built by analyzing the repo's naming conventions
FILENAME_MAP = {
    # CCTV main channels
    'CCTV1.png': 'CCTV-1 综合',
    'CCTV2.png': 'CCTV-2 财经',
    'CCTV3.png': 'CCTV-3 综艺',
    'CCTV4.png': 'CCTV-4 中文国际',
    'CCTV5.png': 'CCTV-5 体育',
    'CCTV5+.png': 'CCTV-5+ 体育赛事',
    'CCTV6.png': 'CCTV-6 电影',
    'CCTV7.png': 'CCTV-7 国防军事',
    'CCTV8.png': 'CCTV-8 电视剧',
    'CCTV9.png': 'CCTV-9 纪录',
    'CCTV10.png': 'CCTV-10 科教',
    'CCTV11.png': 'CCTV-11 戏曲',
    'CCTV12.png': 'CCTV-12 社会与法',
    'CCTV13.png': 'CCTV-13 新闻',
    'CCTV14.png': 'CCTV-14 少儿',
    'CCTV15.png': 'CCTV-15 音乐',
    'CCTV16.png': 'CCTV-16 奥林匹克',
    'CCTV17.png': 'CCTV-17 农业农村',
    'CCTV4K.png': 'CCTV-4K 超高清',
    'CCTV8K.png': 'CCTV-8K 超高清',
    
    # CCTV付费频道
    'CCTV第一剧场.png': 'CCTV-第一剧场',
    '风云剧场.png': 'CCTV-风云剧场',
    '怀旧剧场.png': 'CCTV-怀旧剧场',
    'CCTV世界地理.png': 'CCTV-世界地理',
    'CCTV兵器科技.png': 'CCTV-兵器科技',
    '央视文化精品.png': 'CCTV-央视文化精品',
    'CCTV台球.png': 'CCTV-央视台球',
    'CCTV电视指南.png': 'CCTV-电视指南',
    'CCTV女性时尚.png': 'CCTV-女性时尚',
    'CCTV风云音乐.png': 'CCTV-风云音乐',
    'CCTV风云足球.png': 'CCTV-风云足球',
    'CCTV高尔夫网球.png': 'CCTV-高尔夫网球',
    
    # CETV
    'CETV-1.png': 'CETV-1',
    'CETV-2.png': 'CETV-2',
    'CETV-4.png': 'CETV-4',
    
    # CNC
    'CNC中文.png': 'CNC 中文',
    'CNC英文.png': 'CNC 英文',
    
    # CHC
    'CHC动作电影.png': 'CHC动作电影',
    'CHC家庭影院.png': 'CHC家庭影院',
    'CHC高清电影.png': 'CHC高清电影',
    
    # 卫视 (use Chinese names as virCloud keeps them)
    '三沙卫视.png': '三沙卫视',
    '东南卫视.png': '东南卫视',
    '东方卫视.png': '东方卫视',
    '云南卫视.png': '云南卫视',
    '兵团卫视.png': '兵团卫视',
    '北京卫视.png': '北京卫视',
    '吉林卫视.png': '吉林卫视',
    '四川卫视.png': '四川卫视',
    '天津卫视.png': '天津卫视',
    '宁夏卫视.png': '宁夏卫视',
    '安徽卫视.png': '安徽卫视',
    '山东卫视.png': '山东卫视',
    '山东教育卫视.png': '山东教育卫视',
    '山西卫视.png': '山西卫视',
    '广东卫视.png': '广东卫视',
    '广西卫视.png': '广西卫视',
    '新疆卫视.png': '新疆卫视',
    '江苏卫视.png': '江苏卫视',
    '江西卫视.png': '江西卫视',
    '河北卫视.png': '河北卫视',
    '河南卫视.png': '河南卫视',
    '海南卫视.png': '海南卫视',
    '深圳卫视.png': '深圳卫视',
    '湖北卫视.png': '湖北卫视',
    '湖南卫视.png': '湖南卫视',
    '甘肃卫视.png': '甘肃卫视',
    '福建卫视.png': '福建卫视',
    '西藏卫视.png': '西藏卫视',
    '贵州卫视.png': '贵州卫视',
    '辽宁卫视.png': '辽宁卫视',
    '重庆卫视.png': '重庆卫视',
    '陕西卫视.png': '陕西卫视',
    '青海卫视.png': '青海卫视',
    '黑龙江卫视.png': '黑龙江卫视',
    '内蒙古卫视.png': '内蒙古卫视',
    '浙江卫视.png': '浙江卫视',
    
    # 少儿频道
    '金鹰卡通.png': '金鹰卡通',
    '卡酷少儿.png': '卡酷少儿',
    '嘉佳卡通.png': '嘉佳卡通',
    '优漫卡通.png': '优漫卡通',
    '哈哈炫动.png': '哈哈炫动',
    'CCTV少儿.png': 'CCTV-少儿',
    'CCTV少儿动画.png': 'CCTV-少儿动画',  # Might not exist in our channels
    
    # 影视频道
    'CHC影迷电影.png': 'CHC影迷电影',
    
    # 其他剧场类
    '家庭剧场.png': '家庭剧场',
    '都市剧场.png': 'CITY都市剧场',
}


def fetch_repo_tree():
    """Fetch the full recursive tree from vircloud/TVLogo repo."""
    print(f"Fetching repo tree from {REPO_API}...")
    req = urllib.request.Request(REPO_API, headers={'User-Agent': 'TVproxy'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"ERROR fetching repo tree: {e}")
        return None
    
    # Get all .png files (excluding default.png)
    png_files = []
    for item in data.get('tree', []):
        if item['path'].endswith('.png') and item['path'] != 'default.png':
            png_files.append(item['path'])
    
    print(f"Found {len(png_files)} PNG files in repo")
    return png_files


def load_channel_names():
    """Load our channel names from channels.json."""
    try:
        with open(CHANNELS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        names = list(data.get('channels', {}).keys())
        print(f"Loaded {len(names)} channels from channels.json")
        return names
    except Exception as e:
        print(f"ERROR loading channels.json: {e}")
        return []


def build_mapping_from_repo(png_files, channel_names):
    """
    Build a mapping from repo filenames to our channel names.
    Uses exact match, then substring match, then manual mapping fallback.
    """
    # Start with the explicit manual map
    mapping = {}
    for repo_name, ch_name in FILENAME_MAP.items():
        if repo_name in png_files:
            mapping[repo_name] = ch_name
    
    # Try to match remaining channels by filename similarity
    matched_channels = set(mapping.values())
    unmatched_channels = [c for c in channel_names if c not in matched_channels]
    
    # Build a reverse index: repo filename (without .png) -> repo filename
    repo_basenames = {}
    for f in png_files:
        base = f.replace('.png', '')
        repo_basenames[base] = f
    
    for ch in unmatched_channels:
        # Try direct match
        if ch in repo_basenames:
            mapping[repo_basenames[ch]] = ch
            continue
        
        # Try without spaces
        ch_nospace = ch.replace(' ', '')
        if ch_nospace in repo_basenames:
            mapping[repo_basenames[ch_nospace]] = ch
            continue
        
        # Try substring: does our channel name contain a keyword matching a repo file?
        # e.g. "CCTV-女性时尚" -> check if "女性时尚" is in some repo filename
        for base, fname in repo_basenames.items():
            if fname in mapping:
                continue
            # Check if any meaningful part of our channel name matches
            ch_parts = ch.replace('-', ' ').replace('  ', ' ').split(' ')
            for part in ch_parts:
                if len(part) >= 2 and part in base and part not in ('CCTV', 'CETV', 'CNC', 'CHC'):
                    mapping[fname] = ch
                    break
            if fname in mapping and mapping[fname] == ch:
                break
    
    return mapping, unmatched_channels


def download_logo(repo_filename, our_channel_name):
    """Download a single logo file from GitHub raw."""
    # URL-encode the repo filename to handle Chinese characters
    from urllib.parse import quote
    encoded_filename = quote(repo_filename, safe='')
    url = RAW_BASE + encoded_filename
    dest = os.path.join(TVLOGO_DIR, our_channel_name + '.png')
    
    # Skip if already exists
    if os.path.exists(dest):
        # Check if file is valid (non-zero size)
        if os.path.getsize(dest) > 100:
            return True, "already exists"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'TVproxy'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        
        if len(data) < 100:
            return False, f"too small ({len(data)} bytes)"
        
        with open(dest, 'wb') as f:
            f.write(data)
        return True, f"downloaded ({len(data)} bytes)"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def main():
    os.makedirs(TVLOGO_DIR, exist_ok=True)
    
    # Get data
    png_files = fetch_repo_tree()
    if not png_files:
        print("Failed to fetch repo tree, aborting.")
        return
    
    channel_names = load_channel_names()
    if not channel_names:
        print("No channels loaded, aborting.")
        return
    
    # Build mapping
    mapping, unmatched = build_mapping_from_repo(png_files, channel_names)
    
    print(f"\n=== Mapping Results ===")
    print(f"Mapped: {len(mapping)} logos")
    print(f"Unmatched channels ({len(unmatched)}):")
    for ch in unmatched:
        print(f"  - {ch}")
    
    # Show what maps to what
    print(f"\n=== Mapping Details ===")
    for repo_name, ch_name in sorted(mapping.items()):
        print(f"  {repo_name} -> {ch_name}")
    
    # Download
    print(f"\n=== Downloading Logos ===")
    success = 0
    failed = 0
    skipped = 0
    
    for repo_name, ch_name in sorted(mapping.items()):
        ok, msg = download_logo(repo_name, ch_name)
        if msg == "already exists":
            skipped += 1
        elif ok:
            success += 1
        else:
            failed += 1
            print(f"  FAILED: {repo_name} -> {ch_name}: {msg}")
    
    print(f"\n=== Summary ===")
    print(f"Downloaded: {success}")
    print(f"Skipped (exist): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total in tvlogo/: {len([f for f in os.listdir(TVLOGO_DIR) if f.endswith('.png')])}")


if __name__ == '__main__':
    main()

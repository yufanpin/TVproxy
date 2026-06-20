# -*- coding: utf-8 -*-
"""
TXT live source importer.
Parses txt format:  频道名,URL  with #genre# category headers.
"""

import os

def parse_txt(content_or_path):
    """
    Parse a txt live source file.
    
    Format:
        央视,#genre#
        CCTV-1 综合,http://...
        CCTV-2 财经,http://...
        
        卫视频道,#genre#
        北京卫视,http://...
    
    Args:
        content_or_path: file content string or file path
    
    Returns:
        list of (channel_name, url, source_label) tuples
    """
    if os.path.isfile(content_or_path):
        with open(content_or_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    else:
        content = content_or_path
    
    entries = []
    source_label = os.path.basename(content_or_path) if os.path.isfile(content_or_path) else 'txt_import'
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.endswith('#genre#'):
            continue
        if ',' in line:
            name, url = line.split(',', 1)
            name = name.strip()
            url = url.strip()
            if name and url.startswith('http'):
                entries.append((name, url, source_label))
    
    return entries


def parse_multiple_txt(file_paths):
    """Parse multiple txt files and merge entries."""
    all_entries = []
    for fp in file_paths:
        entries = parse_txt(fp)
        all_entries.extend(entries)
    return all_entries

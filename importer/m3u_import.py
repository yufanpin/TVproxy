# -*- coding: utf-8 -*-
"""
M3U live source importer.
Parses standard M3U8/M3U playlist format.
"""

import os
import re

def parse_m3u(content_or_path):
    """
    Parse an M3U playlist file.
    
    Format:
        #EXTM3U
        #EXTINF:-1 tvg-id="CCTV1" tvg-name="CCTV-1 综合",CCTV-1 综合
        http://...
        #EXTINF:-1,CCTV-2 财经
        http://...
    
    Args:
        content_or_path: file content string or file path
    
    Returns:
        list of (channel_name, url, source_label) tuples
    """
    if os.path.isfile(content_or_path):
        with open(content_or_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        source_label = os.path.basename(content_or_path)
    else:
        lines = content_or_path.splitlines()
        source_label = 'm3u_import'
    
    entries = []
    current_name = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('#EXTINF:'):
            # Extract channel name from EXTINF
            # Format: #EXTINF:-1 tvg-name="xxx",CHANNEL_NAME
            # or: #EXTINF:-1,CHANNEL_NAME
            
            # Try tvg-name="..." first
            m = re.search(r'tvg-name="([^"]+)"', line)
            if m:
                current_name = m.group(1).strip()
            else:
                # Fallback: extract after last comma
                parts = line.split(',')
                if len(parts) >= 2:
                    current_name = parts[-1].strip()
                else:
                    current_name = None
            
            # If still no name, try tvg-id
            if not current_name:
                m = re.search(r'tvg-id="([^"]+)"', line)
                if m:
                    current_name = m.group(1).strip()
        
        elif line.startswith('http://') or line.startswith('https://') or line.startswith('rtmp://'):
            if current_name:
                entries.append((current_name, line, source_label))
                current_name = None  # Reset after URL
            else:
                # No preceding EXTINF, try to use filename or path hint
                entries.append((current_name or f'ch_{len(entries)}', line, source_label))
        
        elif line and not line.startswith('#'):
            # Non-URL, non-comment line (some M3U variants)
            if current_name:
                entries.append((current_name, line, source_label))
                current_name = None
    
    return entries


def parse_multiple_m3u(file_paths):
    """Parse multiple m3u files and merge entries."""
    all_entries = []
    for fp in file_paths:
        entries = parse_m3u(fp)
        all_entries.extend(entries)
    return all_entries

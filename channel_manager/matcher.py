# -*- coding: utf-8 -*-
"""
Channel matching engine.
Merges entries from different sources that refer to the same channel.
"""

from .normalizer import normalize


def merge_entries(entries):
    """
    Merge channel entries from multiple sources.
    
    Args:
        entries: list of (original_name, url, source_name) tuples
    
    Returns:
        dict: {standard_name: [url1, url2, ...]}  (urls deduplicated)
    """
    channels = {}  # standard_name -> set of urls
    
    for orig_name, url, source in entries:
        std_name, excluded = normalize(orig_name)
        if excluded or std_name is None:
            continue
        if std_name not in channels:
            channels[std_name] = set()
        channels[std_name].add(url)
    
    return channels


def get_merge_stats(channels):
    """Get merge statistics."""
    total_urls = sum(len(urls) for urls in channels.values())
    return {
        'channels': len(channels),
        'total_urls': total_urls,
        'avg_per_channel': round(total_urls / max(len(channels), 1), 1),
    }

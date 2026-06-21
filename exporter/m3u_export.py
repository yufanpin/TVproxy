# -*- coding: utf-8 -*-
"""
M3U format exporter.
Outputs standard M3U playlist with proxy URLs.
Each channel appears only ONCE with a proxy URL.
"""

import os
from urllib.parse import quote

TVLOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tvlogo')


def _channel_logo(channel_name, proxy_base=''):
    """Generate a logo URL for a channel, pointing to local tvlogo/ serving."""
    logo_path = os.path.join(TVLOGO_DIR, f'{channel_name}.png')
    if os.path.exists(logo_path):
        # Serve via Flask /logo/ route
        safe = quote(channel_name, safe='')
        return f'{proxy_base}/logo/{safe}'
    # No local logo → empty string (player will hide logo or show nothing)
    return ''


def export_m3u(categorized_channels, proxy_base='http://localhost:5000', filepath=None):
    """
    Export channels to M3U format with proxy URLs.

    Each channel appears once:
        #EXTINF:-1 tvg-id="..." ...,CHANNEL_NAME
        http://localhost:5000/proxy/CHANNEL_NAME

    Args:
        categorized_channels: OrderedDict {category: [(name, [urls]), ...]}
        proxy_base: base URL of the proxy server
        filepath: optional output file path

    Returns:
        str: formatted M3U content
    """
    lines = ['#EXTM3U']
    path_prefix = '/proxy/'

    for cat, entries in categorized_channels.items():
        if not entries:
            continue

        # Category comment
        lines.append(f'# {cat}')

        for ch_name, _ in entries:
            logo = _channel_logo(ch_name, proxy_base=proxy_base)
            proxy_url = f'{proxy_base}{path_prefix}{quote(ch_name)}'
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch_name}" tvg-name="{ch_name}" '
                f'tvg-logo="{logo}",{ch_name}'
            )
            lines.append(proxy_url)

    content = '\n'.join(lines) + '\n'

    if filepath:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return content

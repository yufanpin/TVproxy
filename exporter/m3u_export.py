# -*- coding: utf-8 -*-
"""
M3U format exporter.
Outputs standard M3U playlist with proxy URLs.
Each channel appears only ONCE with a proxy URL.
"""

import os
from urllib.parse import quote


def _channel_logo(channel_name):
    """Generate a logo URL for a channel."""
    safe_name = channel_name.replace(' ', '%20').replace('&', '%26')
    return f'https://raw.githubusercontent.com/fanmingming/live/main/img/tv/{safe_name}.png'


def export_m3u(categorized_channels, proxy_base='http://localhost:5000', filepath=None, use_relay=False):
    """
    Export channels to M3U format with proxy URLs.

    Each channel appears once:
        #EXTINF:-1 tvg-id="..." ...,CHANNEL_NAME
        http://localhost:5000/proxy/CHANNEL_NAME

    Args:
        categorized_channels: OrderedDict {category: [(name, [urls]), ...]}
        proxy_base: base URL of the proxy server
        filepath: optional output file path
        use_relay: if True, use /relay/ instead of /proxy/

    Returns:
        str: formatted M3U content
    """
    lines = ['#EXTM3U']
    path_prefix = '/relay/' if use_relay else '/proxy/'

    for cat, entries in categorized_channels.items():
        if not entries:
            continue

        # Category comment
        lines.append(f'# {cat}')

        for ch_name, _ in entries:
            logo = _channel_logo(ch_name)
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

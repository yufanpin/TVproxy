# -*- coding: utf-8 -*-
"""
TXT format exporter.
Outputs: 频道名,http://proxy-url/channel  with #genre# category headers.
Each channel appears only ONCE with a proxy URL.
"""

import os
from urllib.parse import quote
from collections import OrderedDict


def export_txt(categorized_channels, proxy_base='http://localhost:5000', filepath=None):
    """
    Export channels to txt format with proxy URLs.

    Each channel appears once:  频道名,http://localhost:5000/proxy/频道名

    Args:
        categorized_channels: OrderedDict {category: [(name, [urls]), ...]}
        proxy_base: base URL of the proxy server
        filepath: optional output file path

    Returns:
        str: formatted txt content
    """
    lines = []
    first = True

    for cat, entries in categorized_channels.items():
        if not entries:
            continue

        if not first:
            lines.append('')
        first = False

        lines.append(f'{cat},#genre#')

        for name, _ in entries:
            # Proxy URL - one per channel
            proxy_url = f'{proxy_base}/proxy/{quote(name)}'
            lines.append(f'{name},{proxy_url}')

    content = '\n'.join(lines) + '\n'

    if filepath:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return content

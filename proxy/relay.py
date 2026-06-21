# -*- coding: utf-8 -*-
"""
Relay proxy - full traffic streaming proxy for IPTV.

Instead of 302 redirect (which exposes the original source URL to the player),
this module provides a full traffic relay: the server fetches the stream and
passes the bytes through to the client. The original source URL is never exposed.

Supports:
- Direct streams (HTTP FLV, TS, etc.) — pure byte relay
- HLS (.m3u8) — playlist rewriting + segment relay
"""

import re
import requests
from urllib.parse import urljoin, urlparse, quote
from flask import Response


# ── Headers to pass through (whitelist) ──
PASSTHROUGH_HEADERS = {
    'Content-Type',
    'Content-Length',
    'Cache-Control',
    'Expires',
    'Accept-Ranges',
}

# ── Default request headers for source fetches ──
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def relay_stream(source_url, timeout=30):
    """
    Generator that yields chunks from the source URL.

    Yields:
        bytes: chunks of stream data

    Raises:
        requests.RequestException on failure
    """
    with requests.get(source_url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        yield resp  # First yield gives the response object for header inspection
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                yield chunk


def build_relay_response(source_url, channel_name, request_host):
    """
    Build a Flask Response that relays content from source_url.

    For HLS playlists, rewrites segment URLs to go through our relay.
    For direct streams, pipes bytes through.

    Args:
        source_url: The original source URL to proxy
        channel_name: The channel name (for HLS URL rewriting)
        request_host: The request host URL (e.g. http://10.0.0.1:5000)

    Returns:
        Flask Response object
    """
    try:
        resp = requests.get(source_url, stream=True, timeout=30, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return _error_response('源连接超时', 504)
    except requests.exceptions.ConnectionError:
        return _error_response('源连接失败', 502)
    except requests.exceptions.RequestException as e:
        return _error_response(f'源请求错误: {str(e)[:100]}', 502)

    content_type = resp.headers.get('Content-Type', '').lower()
    filename = urlparse(source_url).path.lower()

    # ── Detect HLS (.m3u8) ──
    is_hls = ('mpegurl' in content_type or
              'm3u8' in filename or
              '.m3u8' in resp.url.lower())

    if is_hls:
        try:
            content = resp.content
            # Rewrite HLS playlist
            relay_base = f'{request_host.rstrip("/")}/relay/{quote(channel_name)}'
            new_content = rewrite_hls_playlist(content, relay_base)
            return Response(
                new_content,
                status=200,
                content_type='application/vnd.apple.mpegurl; charset=utf-8',
            )
        except Exception as e:
            return _error_response(f'HLS 重写失败: {str(e)[:100]}', 502)

    # ── Direct stream (FLV, TS, etc.) ──
    def generate():
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        except (ConnectionError, BrokenPipeError):
            pass

    # Pass through relevant headers
    headers = {}
    for h in PASSTHROUGH_HEADERS:
        val = resp.headers.get(h)
        if val:
            headers[h] = val

    # Remove Content-Encoding / Transfer-Encoding since we're re-streaming
    headers.pop('Content-Encoding', None)
    headers.pop('Transfer-Encoding', None)
    # Explicitly set chunked encoding
    headers.pop('Content-Length', None)

    return Response(
        generate(),
        status=resp.status_code,
        headers=headers,
    )


def rewrite_hls_playlist(content, relay_base):
    """
    Rewrite an HLS (.m3u8) playlist so segment URLs go through our relay.

    Handles:
    - Absolute URLs  → /relay/<channel>/<base64encoded>
    - Relative URLs  → /relay/<channel>/<path>
    - Variant playlists (multi-bitrate) → rewrite inner playlist URLs too

    Args:
        content: Raw bytes of the .m3u8 playlist
        relay_base: Base URL for relay (e.g. http://server/relay/CCTV-1)

    Returns:
        str: Rewritten playlist content
    """
    text = content.decode('utf-8', errors='replace')
    lines = text.split('\n')
    new_lines = []

    for line in lines:
        stripped = line.strip()

        # Comment / EXT tag (except EXTINF which precedes URL)
        if stripped.startswith('#') and not stripped.startswith('#EXTINF:'):
            new_lines.append(line)
            continue

        # Skip empty lines
        if not stripped:
            new_lines.append(line)
            continue

        # Strict EXTINF line — pass through unchanged
        if stripped.startswith('#EXTINF:'):
            new_lines.append(line)
            continue

        # ── This line is a URL (segment or sub-playlist) ──
        # Determine if absolute or relative
        if '://' in stripped:
            # Absolute URL — encode full URL as path-safe base64
            encoded = _encode_url_path(stripped)
            rewritten = f'{relay_base}/seg/{encoded}'
        else:
            # Relative URL — use as-is
            rewritten = f'{relay_base}/seg/{stripped}'

        # Preserve original whitespace if any
        new_lines.append(rewritten)

    return '\n'.join(new_lines) + '\n'


def _encode_url_path(url):
    """Encode a URL to a filesystem-safe string using hex encoding."""
    # Use URL-safe base-ish encoding: percent-encode then replace % with _
    encoded = quote(url, safe='')
    # Flask path converter handles / specially, so encode %
    return encoded.replace('%', '_')


def _decode_url_path(encoded):
    """Reverse of _encode_url_path."""
    return encoded.replace('_', '%')


def relay_segment(channel_name, segment_path, get_best_url_fn, request_host):
    """
    Relay a single HLS segment.

    Args:
        channel_name: The channel name
        segment_path: The segment path from the URL (may be encoded absolute URL or relative path)
        get_best_url_fn: Function to get the best source URL for a channel
        request_host: The request host URL

    Returns:
        Flask Response
    """
    best_url = get_best_url_fn(channel_name)
    if not best_url:
        return _error_response(f'频道 {channel_name} 无可用源', 404)

    # Derive base URL from best source
    base_url = best_url.rsplit('/', 1)[0] + '/'

    # Check if segment_path is an encoded absolute URL
    if segment_path.startswith('http_') or segment_path.startswith('https_'):
        try:
            seg_url = _decode_url_path(segment_path)
            # Validate it's a proper URL
            parsed = urlparse(seg_url)
            if not parsed.netloc:
                raise ValueError('Invalid URL')
        except Exception:
            seg_url = urljoin(base_url, segment_path)
    else:
        seg_url = urljoin(base_url, segment_path)

    try:
        resp = requests.get(seg_url, stream=True, timeout=30, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return _error_response('分片连接超时', 504)
    except requests.exceptions.RequestException as e:
        return _error_response(f'分片请求错误: {str(e)[:100]}', 502)

    # ── Check if response is an HLS playlist (needs recursive URL rewriting) ──
    content_type = resp.headers.get('Content-Type', '').lower()
    filename = urlparse(seg_url).path.lower()
    is_hls = ('mpegurl' in content_type or
              'm3u8' in filename or
              '.m3u8' in resp.url.lower())

    if is_hls:
        try:
            content = resp.content
            relay_base = f'{request_host.rstrip("/")}/relay/{quote(channel_name)}'
            new_content = rewrite_hls_playlist(content, relay_base)
            return Response(
                new_content,
                status=200,
                content_type='application/vnd.apple.mpegurl; charset=utf-8',
            )
        except Exception as e:
            return _error_response(f'HLS 重写失败: {str(e)[:100]}', 502)

    # ── Not HLS — stream raw bytes (TS, FLV, etc.) ──
    def generate():
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        except (ConnectionError, BrokenPipeError):
            pass

    headers = {}
    for h in PASSTHROUGH_HEADERS:
        val = resp.headers.get(h)
        if val and h != 'Content-Length':
            headers[h] = val

    return Response(
        generate(),
        status=resp.status_code,
        headers=headers,
    )


def _error_response(message, status_code):
    """Create a JSON error response."""
    from flask import jsonify
    return jsonify({'error': message}), status_code

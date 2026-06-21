# -*- coding: utf-8 -*-
"""
TVproxy - 电视直播源代理服务

核心功能：
1. 导入 TXT/M3U 源文件 → 自动匹配同一频道 → 归类排序
2. 全量活性检测 → 记录延迟
3. 请求频道时自动选择延迟最低的源 → 302 重定向 或 全流量代理（不暴露源 URL）
4. 输出统一订阅（TXT/M3U），每频道只一条代理 URL
5. 输出只包含：央视 + 卫视 + 少儿 + 影视
"""

import os
import json
import threading
import time
import re
from datetime import datetime
from collections import OrderedDict
from urllib.parse import unquote, quote

from flask import Flask, render_template, request, jsonify, send_file, redirect, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from channel_manager.matcher import merge_entries, get_merge_stats
from channel_manager.categorizer import categorize_channels, CATEGORY_ORDER, is_target_channel, KEEP_CATEGORIES
from channel_manager.sorter import sort_channels
from channel_manager.health import check_urls, pick_best_url
from channel_manager.normalizer import normalize
from importer.txt_import import parse_txt
from importer.m3u_import import parse_m3u
from exporter.txt_export import export_txt
from exporter.m3u_export import export_m3u

# ── App Setup ──
app = Flask(__name__)
app.secret_key = 'tvproxy-proxy-server-key'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SOURCES_DIR = os.path.join(DATA_DIR, 'sources')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
DB_FILE = os.path.join(DATA_DIR, 'db', 'channels.json')

os.makedirs(SOURCES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'db'), exist_ok=True)

# ── Export categories (only these 4) ──
EXPORT_CATEGORIES = ['央视频道', '卫视频道', '少儿频道', '影视频道']

# ── In-memory state ──
state = {
    'channels': {},           # {standard_name: [url1, url2, ...]}
    'source_files': [],       # list of imported file names
    'last_updated': None,
    'health': {
        'alive': set(),       # alive URLs
        'dead': set(),        # dead URLs
        'latencies': {},       # {url: latency_ms}
        'last_check': None,
    },
    'health_running': False,
    'best_cache': {},          # {channel_name: (best_url, cached_at)}
    'BEST_CACHE_TTL': 300,     # 5 min cache for best URL
    'logs': [],                # ring buffer for activity logs
    'MAX_LOGS': 500,
    'scheduler_enabled': False,
    'scheduler_hour': 6,
    'scheduler_minute': 0,
    'scheduler_job': None,     # APScheduler job reference
}


def add_log(typ, message, detail=''):
    """Add an entry to the in-memory ring-buffer log."""
    from datetime import datetime
    state['logs'].append({
        'time': datetime.now().astimezone().strftime('%m-%d %H:%M:%S'),
        'type': typ,
        'message': message,
        'detail': detail,
    })
    if len(state['logs']) > state['MAX_LOGS']:
        state['logs'] = state['logs'][-state['MAX_LOGS']:]


# ── Persistent storage ──

def save_state():
    """Save channel state to disk."""
    data = {
        'channels': {n: list(u) for n, u in state['channels'].items()},
        'source_files': state['source_files'],
        'last_updated': state['last_updated'],
        'health_alive': list(state['health']['alive']),
        'health_dead': list(state['health']['dead']),
        'health_latencies': state['health']['latencies'],
        'health_last_check': state['health']['last_check'],
        'scheduler_enabled': state['scheduler_enabled'],
        'scheduler_hour': state['scheduler_hour'],
        'scheduler_minute': state['scheduler_minute'],
    }
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state():
    """Load channel state from disk."""
    if not os.path.exists(DB_FILE):
        return
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        state['channels'] = {n: list(u) for n, u in data.get('channels', {}).items()}
        state['source_files'] = data.get('source_files', [])
        state['last_updated'] = data.get('last_updated')
        state['health']['alive'] = set(data.get('health_alive', []))
        state['health']['dead'] = set(data.get('health_dead', []))
        state['health']['latencies'] = data.get('health_latencies', {})
        state['health']['last_check'] = data.get('health_last_check')
        state['scheduler_enabled'] = data.get('scheduler_enabled', False)
        state['scheduler_hour'] = data.get('scheduler_hour', 6)
        state['scheduler_minute'] = data.get('scheduler_minute', 0)
    except Exception as e:
        print(f'Load state error: {e}')


# ── Core pipeline ──

def process_entries(entries):
    """Import pipeline: normalize → match → merge."""
    merged = merge_entries(entries)
    for name, urls in merged.items():
        if name not in state['channels']:
            state['channels'][name] = []
        for url in urls:
            if url not in state['channels'][name]:
                state['channels'][name].append(url)
    state['last_updated'] = datetime.now().astimezone().isoformat()
    save_state()
    return merged


def get_channels_for_export():
    """
    Get channels filtered to export categories (央视+卫视+少儿+影视),
    categorized and sorted. Excludes '其他频道'.
    """
    if not state['channels']:
        return OrderedDict()

    channels = state['channels']

    # Apply health filter if available
    if state['health']['alive']:
        filtered = {}
        for name, urls in channels.items():
            alive_urls = [u for u in urls if u in state['health']['alive']]
            if alive_urls:
                filtered[name] = alive_urls
        channels = filtered

    # Categorize
    cat = categorize_channels(channels)

    # Keep only export categories
    filtered_cat = OrderedDict()
    for export_cat in EXPORT_CATEGORIES:
        if export_cat in cat:
            filtered_cat[export_cat] = cat[export_cat]

    # Sort
    sorted_cat = sort_channels(filtered_cat)

    return sorted_cat


# ── Proxy: find best source for a channel ──

def get_best_url(channel_name):
    """
    Find the best (lowest latency) URL for a channel.
    Uses cache if available and fresh.
    """
    # Check cache
    cached = state['best_cache'].get(channel_name)
    if cached:
        cached_url, cached_at = cached
        if time.time() - cached_at < state['BEST_CACHE_TTL']:
            return cached_url

    # Get channel URLs
    urls = state['channels'].get(channel_name, [])
    if not urls:
        return None

    # If health data exists, pick best from alive set
    if state['health']['alive']:
        best_url, _ = pick_best_url(urls, state['health']['latencies'], state['health']['alive'])
        if best_url:
            state['best_cache'][channel_name] = (best_url, time.time())
            return best_url

    # Fallback: return first URL
    if urls:
        return urls[0]

    return None


# ── Routes: Web UI ──

@app.route('/')
def index():
    """Dashboard."""
    categorized = get_channels_for_export()
    total_export = sum(len(e) for e in categorized.values())

    stats = {
        'total_channels': len(state['channels']),
        'total_urls': sum(len(u) for u in state['channels'].values()),
        'alive_urls': len(state['health']['alive']),
        'dead_urls': len(state['health']['dead']),
        'export_channels': total_export,
        'last_updated': state['last_updated'] or '从未',
        'last_health_check': state['health']['last_check'] or '从未',
        'source_files': state['source_files'],
        'health_running': state['health_running'],
        'proxy_base': request.host_url.rstrip('/'),
        'scheduler_enabled': state['scheduler_enabled'],
        'scheduler_hour': state['scheduler_hour'],
        'scheduler_minute': state['scheduler_minute'],
    }
    job = state.get('scheduler_job')
    stats['scheduler_next'] = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job and job.next_run_time else None

    return render_template('index.html', stats=stats, categorized=categorized,
                           channels=state['channels'],
                           health_alive=state['health']['alive'],
                           health_dead=state['health']['dead'])


# ── Routes: Import ──

@app.route('/api/import/txt', methods=['POST'])
def import_txt():
    """Import a TXT file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    save_path = os.path.join(SOURCES_DIR, file.filename)
    file.save(save_path)
    entries = parse_txt(save_path)
    if not entries:
        return jsonify({'error': 'No valid entries found'}), 400

    merged = process_entries(entries)
    if file.filename not in state['source_files']:
        state['source_files'].append(file.filename)
    save_state()

    stats = get_merge_stats(merged)
    add_log('import', f'导入 {file.filename}', f'{len(entries)} 条, 合并后 {stats["channels"]} 频道, {stats["total_urls"]} URL')
    return jsonify({'success': True, 'entries': len(entries),
                    'channels': stats['channels'], 'total_urls': stats['total_urls']})


@app.route('/api/import/m3u', methods=['POST'])
def import_m3u():
    """Import an M3U file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    save_path = os.path.join(SOURCES_DIR, file.filename)
    file.save(save_path)
    entries = parse_m3u(save_path)
    if not entries:
        return jsonify({'error': 'No valid entries found'}), 400

    merged = process_entries(entries)
    if file.filename not in state['source_files']:
        state['source_files'].append(file.filename)
    save_state()

    stats = get_merge_stats(merged)
    add_log('import', f'导入 {file.filename}', f'{len(entries)} 条, 合并后 {stats["channels"]} 频道, {stats["total_urls"]} URL')
    return jsonify({'success': True, 'entries': len(entries),
                    'channels': stats['channels'], 'total_urls': stats['total_urls']})


# ── Routes: Health Check ──

@app.route('/health')
def health_check():
    """Simple health check endpoint for Docker/monitoring."""
    return jsonify({'status': 'ok', 'channels': len(state['channels'])})


@app.route('/api/health/check', methods=['POST'])
def trigger_health_check():
    """Start health check in background."""
    if state['health_running']:
        return jsonify({'error': 'Health check already running'}), 409

    all_urls = []
    for urls in state['channels'].values():
        all_urls.extend(urls)
    all_urls = list(set(all_urls))

    if not all_urls:
        return jsonify({'error': 'No URLs to check'}), 400

    state['health_running'] = True

    def run_check():
        try:
            add_log('health', '开始活性检测', f'检测 {len(all_urls)} 个URL...')
            alive, dead, latencies = check_urls(
                all_urls, concurrency=30, timeout=5
            )
            state['health']['alive'] = alive
            state['health']['dead'] = dead
            state['health']['latencies'] = latencies
            state['health']['last_check'] = datetime.now().astimezone().isoformat()
            state['health_running'] = False
            state['best_cache'] = {}  # Clear cache, new data available
            save_state()
            add_log('health', '活性检测完成', f'存活 {len(alive)}, 失效 {len(dead)}')
        except Exception as e:
            add_log('health', '活性检测失败', str(e))
            state['health_running'] = False

    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()

    return jsonify({'success': True, 'total': len(all_urls),
                    'message': 'Health check started'})


@app.route('/api/health/status')
def health_status():
    """Get health check status."""
    return jsonify({
        'running': state['health_running'],
        'alive': len(state['health']['alive']),
        'dead': len(state['health']['dead']),
        'last_check': state['health']['last_check'],
    })


# ── Scheduled Health Check ──

def run_scheduled_check():
    """Run health check from scheduler (no return, runs in background thread)."""
    if state['health_running']:
        return

    all_urls = []
    for urls in state['channels'].values():
        all_urls.extend(urls)
    all_urls = list(set(all_urls))
    if not all_urls:
        return

    state['health_running'] = True
    add_log('scheduler', '定时检测触发', f'检测 {len(all_urls)} 个URL...')

    def _run():
        try:
            alive, dead, latencies = check_urls(all_urls, concurrency=30, timeout=5)
            state['health']['alive'] = alive
            state['health']['dead'] = dead
            state['health']['latencies'] = latencies
            state['health']['last_check'] = datetime.now().astimezone().isoformat()
            state['health_running'] = False
            state['best_cache'] = {}
            save_state()
            add_log('scheduler', '定时检测完成', f'存活 {len(alive)}, 失效 {len(dead)}')
        except Exception as e:
            add_log('scheduler', '定时检测失败', str(e))
            state['health_running'] = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def init_scheduler():
    """Initialize or reconfigure the health check scheduler."""
    if state['scheduler_job']:
        state['scheduler_job'].remove()
        state['scheduler_job'] = None

    if not state['scheduler_enabled']:
        add_log('scheduler', '定时检测已关闭')
        return

    sched = state.get('_scheduler')
    if not sched:
        sched = BackgroundScheduler(daemon=True)
        state['_scheduler'] = sched
        sched.start()

    hour = state['scheduler_hour']
    minute = state['scheduler_minute']
    trigger = CronTrigger(hour=hour, minute=minute, second=0)
    state['scheduler_job'] = sched.add_job(
        run_scheduled_check, trigger, id='health_check_daily',
        replace_existing=True, name=f'每日 {hour:02d}:{minute:02d} 健康检测'
    )
    next_run = state['scheduler_job'].next_run_time
    add_log('scheduler', f'定时检测已开启', f'每日 {hour:02d}:{minute:02d} 执行' +
            (f'，下次运行: {next_run.strftime("%m-%d %H:%M")}' if next_run else ''))


@app.route('/api/scheduler/status')
def scheduler_status():
    """Get scheduler status (alias for /api/health/schedule GET)."""
    job = state.get('scheduler_job')
    return jsonify({
        'enabled': state['scheduler_enabled'],
        'hour': state['scheduler_hour'],
        'minute': state['scheduler_minute'],
        'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job and job.next_run_time else None,
    })


@app.route('/api/health/schedule', methods=['GET', 'POST'])
def health_schedule():
    """Get or update health check schedule config."""
    if request.method == 'GET':
        job = state.get('scheduler_job')
        return jsonify({
            'enabled': state['scheduler_enabled'],
            'hour': state['scheduler_hour'],
            'minute': state['scheduler_minute'],
            'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job and job.next_run_time else None,
        })

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    state['scheduler_enabled'] = bool(data.get('enabled', state['scheduler_enabled']))
    state['scheduler_hour'] = int(data.get('hour', state['scheduler_hour']))
    state['scheduler_minute'] = int(data.get('minute', state['scheduler_minute']))
    save_state()
    init_scheduler()

    return jsonify({'success': True, 'message': 'Schedule updated'})


# ══════════════════════════════════════════════════════════
# ★ PROXY - 核心功能：请求频道 → 选最优源 → 重定向
# ══════════════════════════════════════════════════════════

@app.route('/proxy/<path:channel_name>')
def proxy_channel(channel_name):
    """
    Proxy endpoint.
    Request a channel → auto-select best source → 302 redirect.

    Usage: http://localhost:5000/proxy/CCTV-1%20%E7%BB%BC%E5%90%88
    or:    http://localhost:5000/proxy/CCTV-1 综合
    """
    # URL decode the channel name
    name = unquote(channel_name).strip()

    if not name:
        return jsonify({'error': 'Channel name required'}), 400

    best_url = get_best_url(name)

    if not best_url:
        # Try matching by fuzzy name
        matched = None
        for ch_name in state['channels']:
            if name.lower() in ch_name.lower():
                matched = ch_name
                break
        if matched:
            best_url = get_best_url(matched)
            if best_url:
                name = matched

    if not best_url:
        add_log('proxy', f'❌ {name} - 无可用源')
        return jsonify({
            'error': f'No available source for: {name}',
            'note': 'Import sources first, then run health check'
        }), 404

    # Redirect to the best source
    latency = state['health']['latencies'].get(best_url)
    latency_str = f'{latency:.0f}ms' if latency else '无延迟数据'
    short_url = best_url
    if len(short_url) > 90:
        short_url = short_url[:87] + '...'
    add_log('proxy', f'➜ {name}', f'{latency_str} | {short_url}')
    return redirect(best_url, code=302)


@app.route('/play/<path:channel_name>')
def play_channel(channel_name):
    """Alias for /proxy/."""
    return proxy_channel(channel_name)


# ── Routes: Export Subscription ──

@app.route('/api/export/txt')
def export_txt_route():
    """Export unified TXT subscription (每频道一条代理URL)."""
    categorized = get_channels_for_export()
    if not categorized:
        return jsonify({'error': 'No channels to export'}), 400

    proxy_base = request.host_url.rstrip('/')
    output_path = os.path.join(OUTPUT_DIR, 'tvproxy.txt')
    content = export_txt(categorized, proxy_base=proxy_base,
                         filepath=output_path)

    return send_file(
        output_path,
        as_attachment=True,
        download_name='tvproxy.txt',
        mimetype='text/plain; charset=utf-8',
    )


@app.route('/api/export/m3u')
def export_m3u_route():
    """Export unified M3U subscription (每频道一条代理URL)."""
    categorized = get_channels_for_export()
    if not categorized:
        return jsonify({'error': 'No channels to export'}), 400

    proxy_base = request.host_url.rstrip('/')
    output_path = os.path.join(OUTPUT_DIR, 'tvproxy.m3u')
    content = export_m3u(categorized, proxy_base=proxy_base,
                         filepath=output_path)

    return send_file(
        output_path,
        as_attachment=True,
        download_name='tvproxy.m3u',
        mimetype='audio/x-mpegurl; charset=utf-8',
    )


# ── Routes: API ──

@app.route('/api/channel/<path:channel_name>')
def channel_detail(channel_name):
    """Get detailed info for a single channel, including all URLs with latencies."""
    name = unquote(channel_name).strip()
    urls = state['channels'].get(name)
    if not urls:
        # Try fuzzy match
        for ch_name in state['channels']:
            if name.lower() in ch_name.lower():
                name = ch_name
                urls = state['channels'][ch_name]
                break
    if not urls:
        return jsonify({'error': 'Channel not found'}), 404

    from urllib.parse import quote
    url_list = []
    for u in urls:
        alive = u in state['health']['alive']
        latency = state['health']['latencies'].get(u)
        url_list.append({
            'url': u,
            'alive': alive,
            'latency': round(latency, 1) if latency else None,
        })

    # Sort: alive first, then by latency asc
    url_list.sort(key=lambda x: (not x['alive'], x['latency'] if x['latency'] else 999999))

    path_prefix = '/proxy/'
    return jsonify({
        'name': name,
        'total_urls': len(urls),
        'alive_urls': sum(1 for u in urls if u in state['health']['alive']),
        'dead_urls': sum(1 for u in urls if u in state['health']['dead']),
        'proxy_url': f'{request.host_url.rstrip("/")}{path_prefix}{quote(name)}',
        'urls': url_list,
    })

@app.route('/api/channels')
def list_channels():
    """List all channels with URL counts and health status."""
    channels = []
    path_prefix = '/proxy/'
    for name, urls in state['channels'].items():
        alive_count = sum(1 for u in urls if u in state['health']['alive'])
        best_url = get_best_url(name)
        proxy_url = f'{request.host_url.rstrip("/")}{path_prefix}{quote(name)}' if best_url else None
        channels.append({
            'name': name,
            'total_urls': len(urls),
            'alive_urls': alive_count,
            'proxy_url': proxy_url,
            'has_source': best_url is not None,
        })
    channels.sort(key=lambda x: x['name'])
    return jsonify(channels)


@app.route('/api/sources')
def list_sources():
    """List imported source files."""
    return jsonify(state['source_files'])


@app.route('/api/logs')
def get_logs():
    """Get the in-memory activity logs."""
    return jsonify(state['logs'])


@app.route('/logs')
def log_page():
    """Render the log viewer page."""
    stats = {
        'total_channels': len(state['channels']),
        'total_urls': sum(len(u) for u in state['channels'].values()),
        'alive_urls': len(state['health']['alive']),
        'dead_urls': len(state['health']['dead']),
        'export_channels': sum(len(e) for e in get_channels_for_export().values()),
        'proxy_base': request.host_url.rstrip('/'),
    }
    return render_template('logs.html', stats=stats)


@app.route('/api/reset', methods=['POST'])
def reset():
    """Clear all data."""
    state['channels'] = {}
    state['source_files'] = []
    state['health']['alive'] = set()
    state['health']['dead'] = set()
    state['health']['latencies'] = {}
    state['health']['last_check'] = None
    state['last_updated'] = None
    state['best_cache'] = {}
    state['logs'] = []
    save_state()
    add_log('system', '数据已重置')
    return jsonify({'success': True})


# ── Startup ──
load_state()

# Cleanup: remove channels not in target categories (央视/卫视/少儿/影视)
before = len(state['channels'])
state['channels'] = {
    name: urls for name, urls in state['channels'].items()
    if is_target_channel(name)
}
after = len(state['channels'])
if before != after:
    removed = before - after
    # Also clean stale health data
    all_alive = set()
    for urls in state['channels'].values():
        all_alive.update(urls)
    state['health']['alive'] = state['health']['alive'] & all_alive
    state['health']['dead'] = state['health']['dead'] & all_alive
    state['health']['latencies'] = {
        u: l for u, l in state['health']['latencies'].items()
        if u in all_alive
    }
    save_state()
    print(f'  [Cleanup] 移除 {removed} 个非目标频道 → 保留 {after} 个频道')

# Initialize daily scheduled health check
if state['scheduler_enabled']:
    init_scheduler()

if __name__ == '__main__':
    print('=' * 55)
    print('  TVproxy - 电视直播源代理服务器')
    print('=' * 55)
    print(f'  已导入频道: {len(state["channels"])}')
    total_u = sum(len(u) for u in state['channels'].values())
    print(f'  总URL数: {total_u}')
    print(f'  存活/失效: {len(state["health"]["alive"])}/{len(state["health"]["dead"])}')
    print()
    print(f'  ★ 订阅地址:')
    print(f'    TXT: http://localhost:5000/api/export/txt')
    print(f'    M3U: http://localhost:5000/api/export/m3u')
    print(f'  ★ 代理示例:')
    print(f'    http://localhost:5000/proxy/CCTV-1 综合')
    print(f'    http://localhost:5000/proxy/北京卫视')
    print(f'    http://localhost:5000/proxy/金鹰卡通')
    print('=' * 55)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

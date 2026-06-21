# TVproxy 代理指南

## 一句话

Flask 直播源代理服务：导入 TXT/M3U → 自动匹配同一频道 → 归类排序 → 302 重定向到最优源。只有 302 模式，无全流量代理。

---

## 启动

```bash
pip install flask aiohttp requests apscheduler
python app.py    # 监听 0.0.0.0:5000, debug=True
```

- 无构建步骤，无数据库迁移
- `use_reloader=False`（改代码不会自动重启）
- `preload.py` 是单次脚本，内有硬编码的本地绝对路径（`C:\Users\yu\Desktop\github仓库\电视直播`），对其他机器无意义

## 依赖（requirements.txt）

- flask>=3.0, aiohttp>=3.9, requests>=2.31, apscheduler>=3.10
- **无类型检查配置**，**无 linter**，**无 formatter**，**无测试**（整个仓库零测试文件）

## 架构要点

### 状态模型

- 全局 `state` dict 是唯一数据源，存内存
- 异步持久化到 `data/db/channels.json`（JSON 文件，非数据库）
- 启动时 `load_state()` → 清理非目标频道 → 恢复调度器
- 日志是内存环形缓冲区（500 条上限），重启丢失

### 只保留 4 个分类

`app.py` 51 行 `EXPORT_CATEGORIES` 定义：央视频道、卫视频道、少儿频道、影视频道

导入和导出**只输出**这 4 类，其他频道（凤凰、CGTN、本地台等）在导入时丢弃。
启动时也会清理持久化数据中的非目标频道（`app.py` 666-685 行）。

### 数据流

```
TXT/M3U parse → normalize() → merge_entries() → is_target_channel() 过滤
                                                        ↓
                                            state['channels'] (内存)
                                                        ↓
                              export: get_channels_for_export() → categorize → sort
                              proxy:  get_best_url() → pick_best_url() → 302 redirect
```

### normalizer.py 注意事项

- 频道名标准化逻辑高度耦合，修改前必须通读全文件
- 匹配顺序有依赖：CCTV-4K 正则必须在 CCTV 数字正则之前（否则 4K 被误匹配为 4）
- `EXCLUDE_PATTERNS` 列表有硬编码的江西地名（`江西都市`, `南昌`, `九江`...）—— 这是原作者的本地约束，改时需要确认
- Phoenix TV 和 CGTN 最终会被 `categorizer.py` 归为「其他频道」→ 在 merge 阶段丢弃

### categorizer.py 注意事项

- `KEEP_CATEGORIES` 数组仅 4 个值，`CATEGORY_ORDER` 多加了一个「其他频道」用于分类但不输出
- 判断逻辑：CCTV-/CETV-/CNC → 央视；含`卫视` → 卫视；卡通/动画/宝贝 → 少儿；CHC/电影/剧场/影院 → 影视；其余 → 其他

### 健康检测

- `channel_manager/health.py`：asyncio + aiohttp，默认 30 并发，5s 超时
- 使用 `asyncio.new_event_loop()` 在线程中运行（非 asyncio.run）
- 检测逻辑：GET 状态 < 400 或 206 → 存活；否则尝试 Range 请求；再失败 → 失效
- 定时检测由 APScheduler `BackgroundScheduler` 驱动，默认每天 06:00

### 代理

- `GET /proxy/<频道名>` → 查 `best_cache`（5 分钟 TTL）→ 选最低延迟源 → 302 重定向
- 频道名模糊匹配：如果精确匹配不到，会对所有频道名做 `name.lower() in ch_name.lower()` 查找
- `GET /play/<频道名>` 是 `/proxy/` 的别名

### Logo 系统

- 94/104 个频道有本地 logo（从 `vircloud/TVLogo` 仓库下载）
- Logo 文件存储在 `tvlogo/` 目录，文件名 = `{频道标准名称}.png`
- 通过 `GET /logo/<频道名>` 路由提供（`app.py` 520 行 `serve_logo`）
- 无 logo 的频道会返回 1x1 透明 PNG 占位
- M3U 导出时 `tvg-logo` 指向 `/logo/<name>` 本地地址
- 匹配不上的频道（CETV-1/2/4, CHC影迷电影, 品质大剧 等）在 vircloud 仓库中不存在对应 logo
- `scripts/fetch_logos.py`：拉取 vircloud/TVLogo 全部 PNG 并映射到本地频道名

## API 路由速查

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/` | 仪表盘 (HTML) |
| GET | `/logs` | 运行日志 (HTML) |
| POST | `/api/import/txt` | 上传 TXT |
| POST | `/api/import/m3u` | 上传 M3U |
| POST | `/api/health/check` | 触发活性检测 |
| GET | `/api/health/status` | 检测进度 |
| GET/POST | `/api/health/schedule` | 定时检测配置 |
| GET | `/api/scheduler/status` | 调度器状态 |
| GET | `/api/channels` | 频道 JSON |
| GET | `/health` | 健康检查（Docker 探测用） |
| POST | `/api/reset` | 清空数据 |
| GET | `/api/export/txt` | TXT 订阅 |
| GET | `/api/export/m3u` | M3U 订阅 |
| GET | `/proxy/<name>` | 核心代理端点 |
| GET | `/logo/<name>` | 频道 Logo（本地 PNG） |

## CI / Docker

- `.github/workflows/docker.yml`：push 到 master 或打 v* tag 时自动构建 amd64+arm64 推送到 `ghcr.io/yufanpin/tvproxy:latest`
- Docker Compose 挂载了 `/etc/localtime:ro` 解决时区问题
- Docker 使用 `VOLUME ["/app/data"]` 持久化数据
- **不支持 `./data:/app/data` 相对路径挂载**（Docker 报错 `invalid characters`），必须用 named volume 或绝对路径

## 代码约定

- 全部中文注释、中文日志、中文模板（index.html / logs.html 全中文）
- `__init__.py` 都是空文件
- 全局 `state` 直接 import 使用（无依赖注入，无工厂模式）
- 修改频道匹配/分类逻辑后，必须检查 `normalizer.py` → `categorizer.py` → `sorter.py` 三层的联动影响
- 路由函数直接引用 `state` 全局变量，无 request-scoped context

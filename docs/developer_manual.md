# NexusAI 开发与运维手册（Ubuntu 24.04）

## 1. 运行基线

- **操作系统**: Ubuntu 22.04 / 24.04（推荐 24.04）
- **Python**: 3.12+
- **Node.js**: 20.x LTS（项目根目录有 `.nvmrc` 文件）
- **数据库**: SQLite 3（系统内置，默认）/ PostgreSQL（生产推荐）
- **Web 服务器**: Nginx + systemd
- **前端框架**: Next.js 14.2.5（使用 standalone 模式部署）
- **域名**: nexusai.rhyme17.top
- **协议**: HTTP（无 SSL 证书版本）

## 2. 环境要求

| 资源  | 最低配置 | 推荐配置 |
| --- | ---- | ---- |
| CPU | 1 核  | 2 核  |
| 内存  | 2GB  | 4GB  |
| 磁盘  | 20GB | 40GB |

## 3. 首次部署

### 3.1 安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl build-essential nginx

# Python 3.12（Ubuntu 24.04 默认已包含）
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Node.js 20.x LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# C 扩展编译依赖
sudo apt install -y gcc libssl-dev libpq-dev ca-certificates

# 验证版本
python3 --version    # 应显示 Python 3.12.x
node --version       # 应显示 v20.x.x
npm --version        # 应显示 10.x+
```

### 3.2 创建部署用户和目录

```bash
# 创建专用用户（不要直接用 root 运行服务）
sudo adduser --disabled-password --gecos "NexusAI" nexusai
sudo usermod -aG sudo nexusai

# 创建项目目录
sudo mkdir -p /opt/nexusai
sudo chown -R nexusai:nexusai /opt/nexusai

# 创建数据目录（用于 SQLite 数据库和 JSON 文件）
sudo mkdir -p /var/lib/nexusai
sudo chown -R nexusai:nexusai /var/lib/nexusai

# 切换到部署用户
sudo su - nexusai
```

### 3.3 拉取代码

```bash
cd /opt/nexusai
git clone https://github.com/rhyme17/NexusAI.git .
```

### 3.4 后端安装与配置

```bash
cd /opt/nexusai/backend

# 创建 Python 虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env
```

**关键配置项修改**（修改 `.env` 文件）：

```env
# ===== 必须修改 =====

# 服务器监听地址（保持默认即可）
NEXUSAI_HOST=0.0.0.0
NEXUSAI_PORT=8000

# CORS 允许源（HTTP 版本）
NEXUSAI_CORS_ORIGINS=http://nexusai.rhyme17.top

# 存储后端（sqlite 或 postgres）
NEXUSAI_STORAGE_BACKEND=sqlite
NEXUSAI_SQLITE_PATH=/var/lib/nexusai/nexusai.db

# 数据目录
NEXUSAI_DATA_DIR=/var/lib/nexusai

# 管理员密码（必须改为强密码！）
NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD=你的强密码

# API Key 鉴权（生产建议开启）
NEXUSAI_API_AUTH_ENABLED=true
NEXUSAI_API_KEYS=admin-key-随机字符串

# AI 执行配置（使用模拟模式，无需 API Key）
NEXUSAI_AGENT_EXECUTION_BASE_URL=https://api-inference.modelscope.cn/v1
NEXUSAI_AGENT_EXECUTION_MODEL=deepseek-ai/DeepSeek-V3.2
NEXUSAI_AGENT_EXECUTION_FALLBACK=simulate

# 日志级别
LOG_LEVEL=info
ENVIRONMENT=production
```

### 3.5 前端安装与构建

```bash
cd /opt/nexusai/frontend

# 安装依赖
npm ci

# ⚠️ 关键：构建时注入环境变量（HTTP 版本）
NEXT_PUBLIC_API_BASE_URL=http://nexusai.rhyme17.top \
NEXT_PUBLIC_WS_BASE_URL=ws://nexusai.rhyme17.top \
npm run build
```

> **重要说明**：`NEXT_PUBLIC_*` 变量在 `next build` 时被内联到客户端 JS 中，运行时设置无效。

## 4. systemd 服务配置

### 4.1 后端服务

```bash
sudo tee /etc/systemd/system/nexusai-backend.service > /dev/null <<'EOF'
[Unit]
Description=NexusAI Backend
After=network.target

[Service]
Type=simple
User=nexusai
WorkingDirectory=/opt/nexusai/backend
EnvironmentFile=/opt/nexusai/backend/.env
ExecStart=/opt/nexusai/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### 4.2 前端服务（standalone 模式）

```bash
sudo tee /etc/systemd/system/nexusai-frontend.service > /dev/null <<'EOF'
[Unit]
Description=NexusAI Frontend
After=network.target

[Service]
Type=simple
User=nexusai
WorkingDirectory=/opt/nexusai/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/node /opt/nexusai/frontend/.next/standalone/server.js
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### 4.3 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable nexusai-backend nexusai-frontend
sudo systemctl start nexusai-backend nexusai-frontend

# 查看状态
sudo systemctl status nexusai-backend
sudo systemctl status nexusai-frontend
```

## 5. Nginx 配置（HTTP 版本）

```bash
sudo tee /etc/nginx/sites-available/nexusai > /dev/null <<'EOF'
server {
    listen 80;
    server_name nexusai.rhyme17.top;

    client_max_body_size 10M;

    # 前端静态页面
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # WebSocket 实时事件流
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

# 启用站点
sudo ln -sf /etc/nginx/sites-available/nexusai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 重启 Nginx
sudo systemctl restart nginx
```

## 6. PostgreSQL 配置（可选）

如果选择 PostgreSQL 作为存储后端：

```bash
# 安装 PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 创建数据库和用户
sudo -u postgres psql
```

在 psql 中执行：

```sql
CREATE USER nexusai WITH PASSWORD '你的数据库密码';
CREATE DATABASE nexusai OWNER nexusai;
\q
```

更新后端 `.env`：

```env
NEXUSAI_STORAGE_BACKEND=postgres
NEXUSAI_POSTGRES_DSN=postgresql://nexusai:你的数据库密码@127.0.0.1:5432/nexusai
```

重启后端：

```bash
sudo systemctl restart nexusai-backend
```

## 7. 验证部署

```bash
# 检查后端健康状态
curl http://nexusai.rhyme17.top/api/health
# 期望输出: {"status":"ok","read_only":false,"storage_backend":"sqlite"}

# 检查前端可访问
curl -I http://nexusai.rhyme17.top

# 检查服务状态
sudo systemctl status nexusai-backend nexusai-frontend nginx

# 查看端口占用
sudo ss -lntp | grep -E '(:80|:3000|:8000)'
```

## 8. 日常运维命令

### 8.1 重启服务

```bash
sudo systemctl restart nexusai-backend
sudo systemctl restart nexusai-frontend
sudo systemctl restart nginx
```

### 8.2 查看状态

```bash
sudo systemctl status nexusai-backend --no-pager -l
sudo systemctl status nexusai-frontend --no-pager -l
```

### 8.3 查看日志

```bash
# 实时查看后端日志
sudo journalctl -u nexusai-backend -f

# 查看最近 200 行前端日志
sudo journalctl -u nexusai-frontend -n 200 --no-pager
```

### 8.4 健康检查

```bash
curl -i http://nexusai.rhyme17.top/api/health
curl -i http://nexusai.rhyme17.top
```

### 8.5 端口排查

```bash
sudo ss -lntp | grep -E '(:80|:3000|:8000)'
```

## 9. 更新代码流程

```bash
cd /opt/nexusai
git fetch --all
git pull --rebase origin main

# 更新后端
cd /opt/nexusai/backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart nexusai-backend

# 更新前端（注意重新注入环境变量）
cd /opt/nexusai/frontend
npm ci
NEXT_PUBLIC_API_BASE_URL=http://nexusai.rhyme17.top \
NEXT_PUBLIC_WS_BASE_URL=ws://nexusai.rhyme17.top \
npm run build
sudo systemctl restart nexusai-frontend
```

## 10. 常见问题

### 10.1 前端报错：缺少 `.next`

```bash
cd /opt/nexusai/frontend
npm ci
npm run build
sudo systemctl restart nexusai-frontend
```

### 10.2 任务执行出现 504 超时

```bash
# 查看后端日志
sudo journalctl -u nexusai-backend -n 200 --no-pager
```

检查：

- 模型 API 是否可达
- `NEXUSAI_AGENT_EXECUTION_TIMEOUT_SECONDS` 是否足够（默认 45 秒）
- Nginx 的 `proxy_read_timeout` 设置

### 10.3 CORS 错误

确保后端 `.env` 中配置了正确的 CORS 允许源：

```env
NEXUSAI_CORS_ORIGINS=http://nexusai.rhyme17.top
```

### 10.4 WebSocket 连接失败

确保 Nginx 配置中包含 WebSocket 升级头：

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

### 10.5 数据库文件权限问题

```bash
sudo chown -R nexusai:nexusai /var/lib/nexusai
sudo chmod -R 755 /var/lib/nexusai
```

### 10.6 克隆仓库失败（SSH 连接问题）

```bash
# 添加 GitHub 公钥到 known_hosts
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts

# 重新克隆
git clone https://github.com/rhyme17/NexusAI.git .
```

## 11. 升级到 HTTPS（后续添加证书时）

当你获取到 SSL 证书后，按以下步骤升级：

### 11.1 安装 Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 11.2 获取证书

```bash
sudo certbot --nginx -d nexusai.rhyme17.top
```

### 11.3 更新后端配置

修改 `.env` 文件：

```env
NEXUSAI_CORS_ORIGINS=https://nexusai.rhyme17.top
```

重启后端：

```bash
sudo systemctl restart nexusai-backend
```

### 11.4 重新构建前端

```bash
cd /opt/nexusai/frontend
NEXT_PUBLIC_API_BASE_URL=https://nexusai.rhyme17.top \
NEXT_PUBLIC_WS_BASE_URL=wss://nexusai.rhyme17.top \
npm run build
sudo systemctl restart nexusai-frontend
```

## 12. 代码修复说明

### 12.1 已修复的兼容性问题

| 修复项                   | 文件                                     | 说明                                |
| --------------------- | -------------------------------------- | --------------------------------- |
| CORS 环境变量配置           | `backend/app/main.py`                  | 支持 `NEXUSAI_CORS_ORIGINS` 配置多个允许源 |
| Next.js standalone 模式 | `frontend/next.config.mjs`             | 部署体积减少约 70%                       |
| Cookie Secure 属性      | `frontend/src/lib/api/client.ts`       | HTTPS 环境自动添加 Secure 属性            |
| 原子文件写入                | `backend/app/services/auth_service.py` | 认证数据防崩溃损坏                         |
| Node.js 版本锁定          | `.nvmrc`                               | 锁定 Node.js 20.x                   |

### 12.2 环境变量优先级

1. **前端**：构建时通过 `NEXT_PUBLIC_*` 环境变量注入
2. **后端**：`.env` 文件中的配置优先于系统环境变量

## 13. 本地开发验证命令

### 13.1 后端测试（PowerShell）

```powershell
Set-Location "D:\Projects\TraeCNProjects\NexusAI\backend"
.\.venv\Scripts\python.exe -m pytest -q
```

### 13.2 前端构建（PowerShell）

```powershell
Set-Location "D:\Projects\TraeCNProjects\NexusAI\frontend"
npm run build
```

### 13.3 类型检查（PowerShell）

```powershell
Set-Location "D:\Projects\TraeCNProjects\NexusAI\frontend"
npx tsc --noEmit
```

***

**文档版本**: v3.0（HTTP 版本，域名：nexusai.rhyme17.top）
**最后更新**: 2024-04-15

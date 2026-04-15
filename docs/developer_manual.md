# NexusAI 开发与运维手册（Ubuntu）

## 1. 运行基线

- Ubuntu 22.04/24.04
- Python 3.12
- Node.js 20.x
- SQLite 3（系统内置）
- Nginx + systemd

## 2. 首次部署

### 2.1 安装依赖

```bash
sudo apt update
sudo apt install -y git curl build-essential nginx postgresql postgresql-contrib python3.12 python3.12-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

### 2.2 拉取代码

```bash
sudo mkdir -p /opt/nexusai
sudo chown -R $USER:$USER /opt/nexusai
cd /opt/nexusai
git clone https://github.com/rhyme17/NexusAI.git .
```

### 2.3 后端安装

```bash
cd /opt/nexusai/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 前端安装与构建

```bash
cd /opt/nexusai/frontend
npm ci
npm run build
```

## 3. SQLite 数据文件准备

```bash
sudo mkdir -p /opt/nexusai/backend/data
sudo chown -R admin:admin /opt/nexusai/backend/data
```

可选：如果你要自定义数据库文件路径，在后端 `.env` 中设置 `NEXUSAI_SQLITE_PATH`。

## 4. 环境变量

### 4.1 后端

```bash
cd /opt/nexusai/backend
cp .env.example .env
nano .env
```

```env
NEXUSAI_STORAGE_BACKEND=sqlite
# 可选：不填则默认使用 backend/data/nexusai.db
# NEXUSAI_SQLITE_PATH=/opt/nexusai/backend/data/nexusai.db
NEXUSAI_API_AUTH_ENABLED=true
NEXUSAI_AGENT_EXECUTION_PROVIDER=openai_compatible
NEXUSAI_AGENT_EXECUTION_BASE_URL=https://api-inference.modelscope.cn/v1
NEXUSAI_AGENT_EXECUTION_MODEL=deepseek-ai/DeepSeek-V3.2
NEXUSAI_AGENT_EXECUTION_TIMEOUT_SECONDS=120
```

### 4.2 前端

```bash
cd /opt/nexusai/frontend
cp .env.local.example .env.local
nano .env.local
```

```env
NEXT_PUBLIC_API_BASE_URL=https://nexusai.rhyme17.top
NEXT_PUBLIC_WS_BASE_URL=wss://nexusai.rhyme17.top
```

改完前端环境变量必须重建：

```bash
cd /opt/nexusai/frontend
npm run build
```

## 5. systemd 服务

### 5.1 后端

```bash
sudo tee /etc/systemd/system/nexusai-backend.service > /dev/null <<'EOF'
[Unit]
Description=NexusAI Backend
After=network.target

[Service]
User=admin
WorkingDirectory=/opt/nexusai
EnvironmentFile=/opt/nexusai/backend/.env
ExecStart=/opt/nexusai/backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --app-dir /opt/nexusai
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 前端

```bash
sudo tee /etc/systemd/system/nexusai-frontend.service > /dev/null <<'EOF'
[Unit]
Description=NexusAI Frontend
After=network.target

[Service]
User=admin
WorkingDirectory=/opt/nexusai/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run start -- -p 3000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### 5.3 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable nexusai-backend
sudo systemctl enable nexusai-frontend
sudo systemctl restart nexusai-backend
sudo systemctl restart nexusai-frontend
```

## 6. Nginx 配置

```bash
sudo tee /etc/nginx/sites-available/nexusai > /dev/null <<'EOF'
server {
	listen 80;
	server_name nexusai.rhyme17.top;

	location /api/ {
		proxy_pass http://127.0.0.1:8000;
		proxy_http_version 1.1;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
	}

	location /ws/ {
		proxy_pass http://127.0.0.1:8000;
		proxy_http_version 1.1;
		proxy_set_header Upgrade $http_upgrade;
		proxy_set_header Connection "upgrade";
		proxy_set_header Host $host;
	}

	location / {
		proxy_pass http://127.0.0.1:3000;
		proxy_http_version 1.1;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
	}
}
EOF
sudo ln -sf /etc/nginx/sites-available/nexusai /etc/nginx/sites-enabled/nexusai
sudo nginx -t
sudo systemctl reload nginx
```

## 7. SSL（可选）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d nexusai.rhyme17.top
```

## 8. 日常命令

### 8.1 重启网站服务

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
sudo journalctl -u nexusai-backend -n 200 --no-pager
sudo journalctl -u nexusai-frontend -n 200 --no-pager
```

### 8.4 健康检查

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:3000
curl -i https://nexusai.rhyme17.top
```

### 8.5 检查 SQLite 数据库文件

```bash
ls -lh /opt/nexusai/backend/data/nexusai.db
```

### 8.6 端口排查

```bash
sudo ss -lntp | grep -E '(:80|:443|:3000|:8000)'
```

## 9. 更新代码流程

```bash
cd /opt/nexusai
git fetch --all
git pull --rebase origin main
```

后端更新后：

```bash
cd /opt/nexusai/backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart nexusai-backend
```

前端更新后：

```bash
cd /opt/nexusai/frontend
npm ci
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

### 10.2 任务执行出现 504

```bash
sudo journalctl -u nexusai-backend -n 200 --no-pager
```

重点检查模型 API 可达性、超时设置、后端是否阻塞。

### 10.3 需要切换到 PostgreSQL（可选）

```bash
cd /opt/nexusai/backend
nano .env
```

写入/修改：

```env
NEXUSAI_STORAGE_BACKEND=postgres
NEXUSAI_POSTGRES_DSN=postgresql://user:password@127.0.0.1:5432/nexusai
```

然后重启后端：

```bash
sudo systemctl restart nexusai-backend
```

## 11. 本地开发验证命令（PowerShell）

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\backend"
..\.venv\Scripts\python.exe -m pytest -q
```

```powershell
Set-Location "D:\Projects\PycharmProjects\NexusAI\frontend"
npm run build
```


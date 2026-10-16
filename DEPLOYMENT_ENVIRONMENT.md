# Zephyr ERP 部署环境清单

## 必需软件

| 组件 | 版本建议 | 用途 |
| --- | --- | --- |
| Windows 10/11 64 位或 Linux | 最新补丁 | 运行环境 |
| Python | 3.11+（建议 3.12） | FastAPI 后端、迁移、脚本 |
| Node.js | 18+（建议 LTS） | Vue 前端和移动 H5 |
| npm | 随 Node.js | 安装前端依赖 |
| PostgreSQL | 14+ | 主业务数据库 |
| Redis | 7+（可选但推荐） | 缓存/队列；本地开发可关闭相关功能 |
| Git | 2.40+ | 版本管理（压缩包保留 `.git`） |

可选：Docker Desktop（使用 `docker-compose.yml` 一键启动 Redis 和应用容器）、现代浏览器（Chrome 或 Edge）用于验收。

## 端口与服务

- 后端 FastAPI：`8000`
- 前端 Vite：`5173`
- Redis：`6379`
- PostgreSQL：`5432`

## Windows 初始化

```powershell
# 后端
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# 前端
cd ..\frontend
npm install

# 移动 H5
cd ..\mobile-h5
npm install
```

将 `.env` 与 `backend/.env` 的 `DATABASE_URL` 指向新电脑可访问的 PostgreSQL；确认 `SECRET_KEY`、Redis 地址和 CORS 配置。若沿用包内凭据，仍应在首次部署后轮换。

## 数据库准备

1. 新建 PostgreSQL 数据库和用户。
2. 需要保留现有数据时，从 `backups/` 中选择对应 SQL 备份恢复；只需要结构时直接执行迁移。
3. 在项目根目录执行：

   ```powershell
   .\backend\.venv\Scripts\Activate.ps1
   alembic upgrade head
   ```

   如果 Alembic 未找到配置，可先设置 `$env:ALEMBIC_CONFIG = 'alembic.ini'`。

## 启动

```powershell
# 终端 1：后端
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.main

# 终端 2：前端
cd frontend
npm run dev

# 可选：移动 H5
cd mobile-h5
npm run dev
```

浏览器访问 `http://localhost:5173`。首次启动后检查登录、客户/零件、报价、价格管理、出货和移动 H5 等核心页面。

## 不随包搬运的内容

Python 虚拟环境、`node_modules`、运行日志/缓存和本机数据库文件依赖当前操作系统或机器路径，已排除；必须在新电脑按上面命令重新安装/生成。业务 SQL 备份、Excel、静态资源和迁移脚本已保留。

## 安全注意

压缩包内包含本机 `.env`、`.mcp.json`、令牌和测试账号，禁止上传公共网盘或提交到公开仓库。迁移完成后应：轮换数据库密码和令牌、生成新的 `SECRET_KEY`、删除不再需要的测试账号，并限制 PostgreSQL/Redis 仅内网访问。

# Zephyr ERP 跨电脑开发包

本包包含当前项目源码、数据库迁移、文档、测试、静态资源及业务数据。

## 已排除内容

- 本机依赖和缓存：`node_modules/`、`backend/.venv/`、`backend/.runtime312/`、`__pycache__/`、`.pytest_cache/`
- 运行日志及 Playwright 日志：`logs/`、`*.log`、`.playwright-mcp/`
- Windows 设备名文件：`NUL`、`CON`、`PRN`、`AUX`

## 已纳入的敏感/本机配置

为便于你在另一台电脑继续工作，本包保留了 `.env`、`backend/.env`、`.mcp.json`、`.auth_token*` 和 `shipping_test_accounts.local.txt`。这些文件含数据库凭据、令牌或测试账号，只能通过安全介质传输；完成迁移后建议立即轮换密码、令牌和 `SECRET_KEY`。

## 在新电脑上启动

1. 安装 Python 3.11+、Node.js 18+、PostgreSQL 14+；如需缓存再安装 Redis。
2. 检查包内 `.env`、`backend/.env` 和 `.mcp.json` 中的主机/凭据是否适用于新电脑；若不适用，使用 `.env.example` 和 `backend/.env.example` 重建并轮换密钥。
3. 安装后端依赖：

   ```bash
   cd backend
   python -m venv .venv
   # Windows PowerShell: .venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   ```

4. 安装前端依赖：

   ```bash
   cd frontend && npm install
   cd ../mobile-h5 && npm install
   ```

5. 配置好 PostgreSQL 后，在项目根目录按现有迁移配置执行数据库迁移：

   ```bash
   alembic upgrade head
   ```

6. 启动后端和前端：

   ```bash
   # backend
   cd backend && python -m app.main
   # frontend（另开终端）
   cd frontend && npm run dev
   ```

如果使用 Docker，可参考 `docker-compose.yml`；建议不要把生产密钥写入镜像或提交到 Git。

## 数据说明

包内保留了当前项目的迁移脚本、`backups/`、`data/`、`excel/`、`uploads/`（如有内容）和现有文档。数据库连接凭据不会随包提供。

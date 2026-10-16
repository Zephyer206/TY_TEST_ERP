# Windows 云服务器测试部署

适用：前后端部署在 Windows 云服务器上，继续连接现有 PostgreSQL；保留项目当前的免登录测试方式。服务器需有 Python 3.11 或 3.12、Node.js 22 或以上、Git，首次安装项目依赖需要能访问 PyPI 和 npm。服务器安装了 Codex 也可以直接让它按照本文操作。

## 首次部署

1. 本机提交当前业务源码和本次启动文件，推送 GitHub；服务器拉取完整项目。不要把本机虚拟环境、`node_modules`、`logs/cloud-runtime` 一起同步。
2. 在服务器项目的 `backend/.env` 配置现有数据库连接。可单独复制本机已经使用的这份配置，不通过 GitHub 传递密码。保留当前测试模式时，确认 `ENVIRONMENT=development`、`AUTH_DISABLED=true`；连接信息不需要发给 Codex。仅根目录有 `.env` 不够，当前后端读取的是 `backend/.env`。
3. 如需访问现有附件，单独同步本机 `backend/uploads`、项目根目录 `static` 以及 `UPLOAD_DIR` 指定的其他实际存储目录。数据库和代码不包含本地附件文件。
4. 双击项目根目录 **`start-cloud.cmd`**。首次自动创建独立 Python 环境、安装项目依赖、只读验证数据库连接、安装和构建前端，再在后台启动服务。等待出现 `READY`。
5. 在 Windows 防火墙入站规则、云平台安全组／防火墙中允许 **TCP 8080**。需要管理员权限时，在管理员 PowerShell 执行一次：

   ```powershell
   New-NetFirewallRule -DisplayName 'Zephyr ERP Test 8080' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080
   ```

6. 服务器自身访问 `http://localhost:8080`，其他电脑访问 `http://服务器公网IP:8080`。在实际浏览器验证页面加载、业务数据、页面刷新、保存和附件操作。

不需要另外配置 Nginx、启动 Vite 开发服务器或开放后端的另一个端口；一个 Python 进程直接提供已构建前端、原有 `/api/v1` 接口、`/uploads` 和 `/static`。Redis 沿用 `backend/.env` 中的现有配置，脚本不安装或启动 Redis；普通数据页面是否可用及依赖 Redis 的具体功能需分别验收。

## 日常启动、停止与更新

- 启动：双击 `start-cloud.cmd`。重复点击会重新启动本脚本管理的 ERP，不会再启动一份占用端口。源码变化自动重建前端，依赖未变化时使用缓存。
- 停止：双击 **`stop-cloud.cmd`**。仅停止本启动入口记录并核验身份的进程，数据库、其他 Python 项目和原有本地开发服务不受影响。
- 更新：先双击停止文件，执行 `git pull --ff-only`，再双击启动文件。脚本不自行拉取 GitHub，方便你选择更新时机。
- 关闭启动窗口后，ERP 继续运行。**此入口不是 Windows 服务，不提供崩溃自动重启、开机自启或注销后保持运行保证**；服务器重启或会话注销后应重新登录并启动。
- 启动不会建库、初始化业务数据、运行 Alembic 或修改数据库连接信息。包含数据库表结构变更的版本需另外备份并按该版本迁移说明执行。

## 端口、Python 与故障排查

默认端口 8080 被占用时，在项目目录运行：

```powershell
.\start-cloud.cmd -Port 8081
```

同时放行 TCP 8081，使用 `http://服务器公网IP:8081`。不需要改前端接口地址。

Python 未加入 PATH 或需明确选择版本时：

```powershell
.\start-cloud.cmd -PythonPath 'C:\Python311\python.exe'
```

启动器优先通过 Python Launcher 查找 3.11／3.12，然后查找 PATH 中的 Python。不会修改系统 Python 的现有依赖；虚拟环境建立后继续复用。当前固定的部分依赖较旧，不支持直接使用 Python 3.13 或更高版本。

需要强制重新安装项目依赖并构建时：

```powershell
.\start-cloud.cmd -Rebuild
```

运行日志和缓存状态在 `logs/cloud-runtime/logs/`：

| 文件 | 内容 |
| --- | --- |
| `python-environment.log` / `python-install.log` | Python 环境创建／依赖安装 |
| `database-check.log` | 数据库只读检查结果，隐藏连接信息 |
| `frontend-install.log` / `frontend-build.log` | npm 安装／前端构建 |
| `server.stdout.log` / `server.stderr.log` | 服务运行和启动错误 |

依赖安装或构建失败，启动器报错退出，不把失败状态显示成启动成功。`READY` 仅表示数据库连接、API 健康检查和前端 HTML 返回正常；实际业务操作需浏览器验收。

若 `localhost` 能打开而公网不能打开，检查端口放行、服务器公网 IP 和云平台网络设置。数据库检查失败时核对服务器上的 `backend/.env`、数据库监听地址及访问规则，不需要重新建库。

## 本地验收记录（2026-10-16）

实现结果：新增双击启动／停止入口，独立安装环境和依赖缓存，构建前端并由原后端进程提供页面；未修改业务界面、认证模式和数据库结构。原有本地启动文件保留。

验收结果：Windows 上首次准备依赖和构建成功；SELECT 1 数据库连接检查、重复启动、构建缓存、实际 .cmd 启动／停止、端口释放、已占用端口拒绝启动均通过。API 使用扫描为 0 项违规。

浏览器验收：使用本机 Playwright Chromium 149.0.7827.55，在独立测试端口 18080 实测零件列表读取、业务页面直接访问和刷新、前端 JS 资源、缺失接口／文件返回 404、同源请求及无浏览器运行错误，均通过。仅做读取，没有提交业务修改。云服务器部署和公网访问仍需拉取后在目标服务器验证。

可在已安装仓库根目录 Playwright 开发依赖和浏览器后复验默认 8080 服务：

    node tests/playwright/accept-cloud-deployment.cjs

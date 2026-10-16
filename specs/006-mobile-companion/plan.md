# Implementation Plan: 移动辅助工作台

## Phase 1: foundation (completed)

- 建立 Vue/Vant 移动壳层、四项底部导航和统一 JWT API 客户端。
- 将旧登录和旧硬编码地址迁移到 `/auth/login`、`/auth/me` 与 `/api/v1`。
- 完成价格、零件、生产、库存、包装/发货、扫码页面。
- 以移动卡片和底部抽屉适配单手操作，禁止售后入口进入移动端。

## Phase 2: acceptance and hardening (current)

- 在本地实际浏览器中验收主要视口和核心交互。
- 校验后端返回结构；对空数据、401、网络错误提供明确状态。
- 隐藏尚未完成生产会话依赖的现场报工入口。
- 保留生产计划只读查看，排产和业务编辑继续在电脑 ERP 完成。

## Phase 3: QR and field operations

- 定义二维码载荷版本和对象类型（零件、模具、机台、包装）。
- 接入摄像头扫描并复用 `/qr/lookup`，手动输入继续作为兜底。
- 扫码结果提供只读详情和允许角色范围内的现场动作。
- 生产会话建立后再接通报工提交。

## Phase 4: deployment

- 生产构建部署到独立 `/m` 路径或独立静态站点。
- 通过环境变量配置 API 地址，反向代理统一处理 HTTPS、缓存和 `/api` 转发。
- 不在构建产物中写入 token、密码、数据库连接串或 `.env`。

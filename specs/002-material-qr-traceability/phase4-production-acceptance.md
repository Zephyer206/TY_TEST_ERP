# 机台生产阶段交付与验收

日期：2026-10-26（Asia/Hong_Kong）。本批完成T022～T028共7项，累计27/59；31个新领域设计端点中18个active，余13个待实现。保留既有三条业务确认，示例路线和角色均为隔离夹具，没有新增真实业务回答。

## 实现结果

| 有序阶段 | 代码结果 | 独立验收结果 |
|---|---|---|
| 1. 订单配置 | product_order_service原子保存主/配对件、负责人、路线/机台份额；严格整数、完整覆盖、已分配需求下限、发布版本不可变；预授权事实由服务端产生 | 配置47项测试通过，实际HTTP配置读写及字段白名单通过 |
| 2. 扫码与数量 | product_production_service保存摘要票据、30分钟上下文、独立机台状态、覆盖值、首次产出来源/默认用途、重扫完成意向及版本锁；主管原因更正、授权用途分配和审计同事务 | 生产27项及API7项通过，包括并发需求、失效/跨用户、完成差异、回滚、旧路线和下游事实保护 |
| 3. API接入 | 7项新registry、schema、认证路由、typed domain wrapper；bigint规范字符串、旧ID整数、strict quantity/boolean及extra禁止 | API扫描0违规；32旧QR映射和4辅助wrapper检查通过 |
| 4. 实际页面 | 制造执行新增机台生产；机台→订单→框→数量；多机内存选单、差异确认、更正及授权用途分配；业务信息主层级、框号辅助 | Chrome及恢复后的应用内Chromium实际交互通过，详见[浏览器逐项证据](./acceptance-production.md) |
| 5. 收尾 | 文档/合同/任务同步，脱敏证据与截图哈希；只清理本批拥有原创建凭证的库及专用进程 | 两个本批UI库已清理；业务库只读基线通过；历史无凭证残留单列INCOMPLETE |

路由/schema位于backend/app/api/product_boxes.py、backend/app/schemas/product_box.py；前端使用frontend/src/api/productProduction.ts、types/productProduction.ts及views/product-box-qr/production.vue，仍经过共享registry和唯一request client。配置管理UI、连续推进及完整追溯不属于本批已交付入口。

## 自动化证据和修复

完整QR回归209项首次208通过、1项旧版本选单失败。修复为按显式state_id对应的固定已发布路线校验，而非强迫旧框使用产品最新路线；最新生产27项+API7项复验34/34通过。两份XML按classname/name取最后结果后为209个独立用例全部通过，不将209+34相加。XML为runtime/qr-production-full.xml与runtime/qr-production-routes-final.xml；[机器证据](./phase4-evidence.json)保留每次原始失败数，未篡改历史结果。

初始服务测试曾因夹具缺少Part的select-in Inventory依赖及合成Material缺grade失败；补齐测试先决表/字段，未削弱业务模型。配置HTTP空machine_ids/types默认值按空限制规范化，避免将未变化的发布路线误判为新内容。实际浏览器InputNumber无障碍状态问题已修复并复验。前端构建还发现旧workbench响应类型有相同source_assignee重复声明，仅移除重复行，原字段合同保留。

最终npm run build（vue-tsc + Vite）通过；现有Sass legacy API、Rollup注释、bundle体积提示仍在，不阻断构建。scripts/check_api_usage.ps1 -FailOnViolation为0违规，相关diff空白检查通过。设计检查不替代运行或浏览器证据。

## 数据与边界

数据库验收使用随机qrtmp合成库。第一段中断恢复快照确认25件、101完成且另一状态pending；第二段只读快照确认主管102更正25→20并保留原因，负责人104分配10订单+10备货，无跨单改写。操作时间和身份由数据库/服务端记录，没有客户端自报操作人。

业务库只读结果仍为20261020_ppap，23张新领域表存在数0，旧QR枚举9项；业务写入0。正常配置AUTH_DISABLED仍true，新QR接口在该模式拒绝生产写入，隔离服务只在自身进程使用真实合成JWT。没有升级业务库、修改真实能力、关闭正常认证绕过或宣称上线。

本批两次UI库original OID 178490/196973已按创建凭证清理，专用18124/18125服务停止。仍有1个历史测试库缺原创建名称/OID凭证，未推断删除，其清理为INCOMPLETE。此限制与本批实现/验收通过分开记录。

T021仍缺系统打印窗口、设备出纸/纸质扫码和整段绑定耗时证据；T029起的连续工艺、原料反查及性能验收尚未实现。本批暂停异常守卫及保留下游事实更正测试只证明现有生产保护，不等于异常/通知/US4已交付。下一实现范围为T029～T033，不将27/59表述为整个系统完成。

# 产品框权限与通知范围合同

**日期**：2026-10-13  
**性质**：D-P006 的设计默认值，不代表已向真实账号授权或通过运行权限测试。

## 服务端判定

每次操作联合检查有效登录、role_level、dept、明确能力、订单范围、实体状态与需要时的扫码上下文。复用现有 require_role 作最低等级检查，并补领域范围检查；现有仅按等级检查不能替代本合同。

能力授权独立持久化（用户、能力、授权人、时间、停用状态），未授权默认拒绝。订单业务范围取 ProductOrderContext.business_owner_id，不能从 created_by、账号等级或客户端传入的角色推断。已有全局查询规则保留；二维码业务写入按下表。

| 动作 | 允许条件 |
|---|---|
| 追溯查询、扫码查询、事件 | 当前订单可见性 + qr.trace；生产/仓库日常操作权限同时包含其现场必要查询；LV3/LV4 沿用全局查询 |
| 生成 QR | prod LV2+ + qr.generate，或 LV4 + qr.admin + qr.generate |
| 打印/补打/打印确认 | prod 或 warehouse LV1+ + qr.print；LV4 同样需 qr.print；确认人必须为作业申请人 |
| 生产绑定 | prod LV1+ + qr.production + 有效选单上下文 |
| 仓库绑定 | warehouse LV1+ + qr.bind + 可见且配置完整的订单 |
| 同单拆框 | prod/warehouse LV1+ + qr.split；检查父框可见性、用途余额及下游状态 |
| 跨单拆框、订单/备货分配 | prod LV2+ + qr.supervise，或 sales LV2+ 且为源单负责人；目标单有效且产品工艺兼容 |
| 在产数量登记、工艺推进、完成 | prod LV1+ + qr.production + 当前用户有效生产上下文；完成后的旧工艺登记拒绝 |
| 完成后数量更正 | prod LV2+ + qr.supervise；必须有原因、历史工艺版本和框版本；不改写下游事实 |
| 标签业务快照编辑 | prod/warehouse + qr.metadata，或 sales LV2+ 为本单负责人 + qr.metadata；身份、订单、产品引用不可编辑 |
| 规格异常创建 | prod LV1+ + qr.production + 有效生产上下文；用服务端订单/卷料事实生成 |
| 异常确认、暂停恢复 | prod LV2+ + qr.supervise，或 sales LV2+ 为本单负责人 |
| 人工发起转换 | prod LV2+ + qr.supervise，或 sales LV2+ 为本单负责人 |
| 转换实物确认 | prod LV1+ + qr.production + 当前用户匹配机台、订单、产品和步骤的上下文；LV3/LV4 不能仅凭等级绕过 |
| 取消待确认转换 | 有该框有效上下文的操作工，或授权主管/本单负责人；已确认不能取消 |
| 路线/负责人/目标量配置 | prod/engineering LV2+ + qr.configure，或 LV4 + qr.admin |
| 能力授权维护、人工通知重试 | LV4 + qr.admin；不扩大其他业务写入权限 |

本期没有代理确认、质量结论录入、任意跳工艺、转换结果撤销或已绑定二维码作废接口。仓库拆框权限不包含跨单订单量分配。角色称谓只用于说明，后端不能信任前端隐藏按钮来保障权限。

## 站内收件人

异常事务保存生产主管收件组与订单业务负责人收件组的解析结果。已启用 prod LV2+ 且 qr.supervise 的账号收到主管待办；明确有效订单负责人收到业务待办。相同账号去重，只有实际允许确认的人才显示确认动作。

每个收件组缺配置时保存 resolution_status=pending_configuration 和缺失原因，异常仍可查询；配置补齐后重解析、幂等回补 outbox。两组配置齐全才能标为 resolved，不把“通知已发送给一人”当成全部收件人都已覆盖。收件组、投递尝试及业务确认状态分别记录。

GET /notifications 仅返回当前用户通知；LV4 管理重试通过独立端点查询失败投递，不借普通用户列表读取他人通知正文。通知日志不输出账号隐私或认证信息。

## 反向验收

1. engineering LV2 没有 qr.configure 时不能配置；无 qr.supervise 不能凭 LV2 确认异常。
2. sales LV2 是单1负责人时可调整单1；对单2返回 FORBIDDEN，不更改数据。
3. warehouse LV1 + qr.split 可同单拆框；带另一 target_order_id 的请求返回 FORBIDDEN。
4. 完成后普通操作工登记旧状态返回 STATE_CONFLICT；授权主管通过更正入口保留前后值和原因。
5. LV4 没有匹配生产上下文时不能确认 B/C 实物数量。
6. 缺业务负责人时保留待配置收件组；补齐后同事件仅补发一次，确认状态不变。
7. AUTH_DISABLED 的 LV4 替身不能用来证明以上权限行为；测试需真实身份或隔离的明确角色夹具。

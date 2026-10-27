# 连续工艺与材料追溯浏览器验收

验收日期：2026-10-26～27（Asia/Hong_Kong）。范围T032/T033；实现及自动化证据见[本阶段报告](./phase5-trace-acceptance.md)。全部写入仅限本批随机自有qrtmp数据库，使用真实Vue页面、registry/domain API和后端认证路由。

## 会话与角色

可控应用内Chromium浏览器2、tab 3；机台页面为 `http://127.0.0.1:18125/product-box-production`，独立追溯页为 `http://127.0.0.1:18125/product-box-trace`。用户未指定浏览器，按本项目本地验收规则选择会话；没有执行或宣称Chrome专属Windows身份核对。JWT只在内存，未保存页面源码。

合成101为生产操作工，105为订单402负责人。顶部旧user store显示“管理员”，不作为请求身份或授权证据；服务端token主体、allowed_actions及持久化operator_id证明实际身份。真实账号授权及正常服务AUTH_DISABLED设置没有更改。

## 实际观察

| 顺序 | 操作与验收 | 结果 |
|---|---|---|
| 1 | 101扫601，明确选订单401/CUT；池项1一次绑定；核对MAT:9502:20261026为TRACE-CHILD，保存30件 | PASS |
| 2 | 再扫601、确认-70差异，完成CUT；框仍可查询与后续流转 | PASS |
| 3 | 扫602，明确选401/FINISH；扫描同一框，核对CUT→FINISH/入量30后确认；保存FINISH为25 | PASS |
| 4 | 扫601，明确选401/PACK；沿用同一码，核对FINISH→PACK/入量25并确认 | PASS |
| 5 | 页面和追溯显示CUT 0→30、FINISH入30/保存25、PACK入25/保存25；当前PACK、数量25 | PASS |
| 6 | 同框从PACK尝试回到FINISH，被“只能进入固定路线的下一道工艺”拒绝；无第三次handoff或数量变化 | PASS |
| 7 | 追溯显示真实产品、订单401、客户件号、路线v1、机台和操作人；材料显示TRACE-CHILD直接用料及TRACE-MOTHER上溯1层，余重30/70kg | PASS |
| 8 | 初始历史5/12，点击读取更早事件后12/12，包含CUT完成、两次出入量快照和保存25；后续查询会新增scan事件 | PASS |
| 9 | 独立追溯页连续三次查询，输入/点击至材料祖先可见为1659、1619、1716ms | PASS |
| 10 | 另选402/CUT并绑定池项2；先核对子卷，再改为母卷但不重新核对，保存被拒绝，DB仍0件/version1 | PASS |
| 11 | 伪造MAT:9501:20010101被完整身份核对拒绝；改正为MAT:9501:20261026重新核对并保存7件，DB来源确为9501 | PASS |
| 12 | 105先查本单框2可见7件及母卷，再查401框1被拒绝，旧402详情数量为0个，不残留旧资料 | PASS |
| 13 | 独立只读DB核验框1同源ID、材料9502、三步数量/入量、唯一30件首次产出分配及两条handoff；原材料重量未扣减 | PASS |

时限测量包括浏览器自动化输入/点击及真实请求至材料表DOM可见，属于loopback合成单用户结果，未测试现场网络、设备和并发负载。该场景在3秒内完成完整材料反查，同时低于5分钟目标；不能据此宣称所有规模或实际现场性能通过。

跳步、跨用户、过期版本、暂停、并发竞争、审计失败回滚、首产出位于后续步骤、材料断链/循环/空字段和历史更正保护由PostgreSQL/API测试证明；不冒称每种情况都已在浏览器逐项操作。当前没有生产拆框、异常处理或B/C转换入口，不把“暂无关联记录”当作这些流程验收。

## 证据与收尾

- [订单与数量主视图](./phase5-trace-overview.png)、[材料子卷母卷](./phase5-material-lineage.png)、[历史翻页](./phase5-trace.png)
- [非法回流拒绝](./phase5-invalid-flow.png)
- [错误材料后仍0件](./phase5-material-guard.png)、[正确来源恢复为7件](./phase5-material-recovered.png)
- [其他订单拒绝且旧资料清空](./phase5-other-owner.png)
- [拒绝阶段DB](./phase5-guard-db.json)、[最终DB快照](./phase5-db.json)、[原始时限记录](./phase5-performance.json)

截图为实际可视区域，不将调用fullPage选项称为完整长图。自有库original OID 214584已核对清理；专用18124 Vite与18125 API已停止。业务库只读仍为20261020_ppap、23新表存在数0；历史1个无原始创建凭证测试库仍保留，其清理单列INCOMPLETE。文件哈希、测试去重和清理结果见[机器证据](./phase5-evidence.json)。

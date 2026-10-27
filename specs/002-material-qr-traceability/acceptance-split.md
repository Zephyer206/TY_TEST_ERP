# 产品框拆分浏览器验收

日期：2026-10-27，Asia/Hong_Kong。会话为应用内Chromium browser 2 / tab 4，URL为loopback 18125的/product-box-trace和/product-box-production，实际Vue页面连接本次自有随机PostgreSQL库。账号101工人、102生产主管、103仓库、104本单负责人、105其他单负责人均为隔离合成身份，JWT仅在内存。用户没有指定浏览器，按本地验收规则使用可控应用内会话。

实现：独立拆分服务、注册端点、领域wrapper、严格类型和拆框弹窗已接通；订单/产品/工艺/数量主显示，二维码和快照作为折叠辅助。以下是独立浏览器操作观察，不由编译或API结果代替。

| 用例 | 实际观察 | 结果 |
|---|---|---|
| 1. business_hierarchy | 订单、产品、工艺、数量为主，来源快照及标签编号折叠辅助 | PASS |
| 2. cancel | 100件父框核对子标签后取消，DB仍1框/100件、子标签unused | PASS |
| 3. same_order | 100拆30后父70子30，同单用途及材料继承 | PASS |
| 4. repeated_split | 父70再拆10后父60，已拆正余量可继续拆 | PASS |
| 5. cross_order | 主管明确选403/CUT/TEST-M601，拆20后父40属401、子20属403 | PASS |
| 6. zero_balance | 10件子框全拆后原框0/empty，标签与来源保留、无拆框入口 | PASS |
| 7. overdraw | 10件框输入11件，确认按钮不可用 | PASS |
| 8. invalid_child | 已绑定标签提示已使用，池外标签提示不在系统池中，均不可确认 | PASS |
| 9. changed_child | 核对后修改子标签立即清空核对结果并禁用确认 | PASS |
| 10. source_readonly | 工人选401/CUT后父框首次数量只读，没有保存入口 | PASS |
| 11. continued_production | 工人明确选择401/FINISH，父40及子30分别进入，合计70且材料来源继承 | PASS |
| 12. zero_handoff | 0件框提示无余量且进入所选工艺按钮禁用 | PASS |
| 13. scope | 工人无拆框入口，其他订单负责人105查询401被拒绝 | PASS |
| 14. owner_preview | 源单负责人104可在子框5拆框范围预览unused标签6，未选目标不能提交，取消不绑定 | PASS |
| 15. relation_navigation | 父子与跨单导航显示正确订单、余量和来源快照，导航后旧扫码输入清空 | PASS |

只读DB最终核对：5框数量40/30/0/20/10合计100；有效来源及用途合计100，源单401用途80、目标403用途20；4个关系、8条父/子拆分事件，操作者103/103/102/103。父40及子30进入FINISH，入量40/30，原料均9502并上溯9501，材料台账70/30不变。取消阶段独立快照证明标签未占用；负责人预览标签6后取消，仍仅5个bound池项。详见[只读快照](./phase6-db.json)。

界面验收发现并修复数量控件输入显示与计算值不同步、弹窗超出可视区域，以及关联导航仍显示旧扫码输入的问题；改为直接受控数字输入、固定标题/底部且内容滚动，导航清空旧输入。最终页面重验通过。

混合订单/备货用途、并发扣量/目标需求竞争、事务回滚、幂等重放、过期版本与工艺不兼容等由PostgreSQL及实际HTTP测试验证，未冒称全部通过浏览器点击。实体打印、工业扫码器、US6通知/异常及B/C转换不在本批验收范围。

截图：[拆分确认](./phase6-split-confirm.png)、[跨单核对](./phase6-cross-confirm.png)、[零余量](./phase6-zero-trace.png)、[零框拒绝流转](./phase6-zero-handoff.png)、[来源只读](./phase6-source-readonly.png)、[父子流转](./phase6-parent-child-handoff.png)、[其他订单拒绝](./phase6-other-owner.png)、[负责人范围内预览](./phase6-owner-preview.png)、[父框总览](./phase6-split-overview.png)、[跨单子框来源](./phase6-child-trace.png)。

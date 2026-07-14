# 左右件共享材料/规格纠正任务

## 业务规则

- 左件和右件仍是两个内部零件。
- Excel 中相邻左右件经常使用合并单元格保存同一材料和用料规格；读取时必须把合并值传播给合并范围内的两行。
- 同一副模具一次出左、右各一个时，`1出2/一出二/左右各一个`表示穴数 2，不是步骤数。
- 列表 T/W/P 规格值只显示数字相乘，例如 `0.8×34×34.5`，不要显示 `T/W/P` 字母。
- 组合规格可能只有部分数值，例如 `0.4*`只代表已知厚度 0.4，W/P 为空；不得因为不完整而丢掉厚度，也不得猜 W/P。

## 已确认样本

Excel sheet `上海万向钱潮A-A`：

- row 135: TYAA-Q0093-1，左件，材料 `SUS301-CSP 3/4H（JIS G4305）`，规格 `0.4*`
- row 136: TYAA-Q0093-2，右件；材料和规格单元格与上一行纵向合并，因此 xlrd 普通读取为空
- parts.id 19036 左件当前有材料但 T/W/P 为空
- parts.id 19037 右件当前材料、T/W/P 为空
- 原文件这两行的普通备注列为空；不得伪称文件中存在可读取的 `1出2`

数据库中约有 258 组 `同sheet + tooling基础号相同 + -1/-2 + 左右件`候选，必须通过严格条件处理，不能只修样本。

## 模型与安全

- 默认 `claude-sonnet-5`；同一问题连续失败才切 Fable。
- 先读 `CLAUDE.md` 和权威 `data-model.md`。
- 正式数据库更新前必须备份，先 dry-run；不得删除、清表或覆盖现有不同的非空数据。
- 本任务不自动合并 tooling 主记录或改模具号；物理模具归并另行设计。
- 工作树已有大量修改，不回退无关文件，不提交 Git。

## 一、修复未来 Excel 解析

修改 `backend/scripts/import_excel_authoritative.py`：

1. 读取 `.xls` 时识别 `sheet.merged_cells`，任何合并范围内的非左上角行都应取得左上角值；至少对 material/spec/remark/cavity/position 等业务字段生效。
2. 组合规格解析支持完整和部分规格：
   - `0.8*34*34.5` -> T=.8 W=34 P=34.5
   - `0.4*` -> T=.4, W/P NULL
   - `4.0**155*43`必须进入 REVIEW/不猜测，除非格式含义有明确规则
   - 支持 `* × x X`，但不能把客户件号中的 X 当乘号；只能解析明确 spec 列
   - 支持公差括号和尾部说明
3. 独立 T/W/P 列优先；为空时才从明确 spec 列补充。
4. cavity_count 只从明确 `1出N/一出N/左右各一个`解析。
5. 为真实格式、合并单元格和客户件号反例增加测试/断言。

## 二、左右件共享纠正脚本

创建专用脚本，默认 dry-run，按原始 Excel 表头和合并范围重新解析，不能扫描 raw_data 任意列。

候选组至少满足：

- 同一 source_sheet；
- tooling_number 去掉末尾 `-1/-2` 后相同；
- 同时存在左、右语义的内部名称；
- resolved_part_id 均存在；
- Excel 行相邻或属于同一个明确合并范围。

每组处理规则：

- material：合并范围或组内只有一个唯一非空值时，可填充缺失 sibling；多个不同材料则 CONFLICT。
- T/W/P：按明确 spec 列解析；每个维度可部分存在。组内每个维度只有一个唯一非空值时，可填充对应缺失字段；不同则 CONFLICT。
- position：明确左/右名称时，补 `parts.part_position` 与 `tooling_parts.position` 为 left/right，仅填空值。
- cavity_count：只有来源明确写 `1出2/一出二/左右各一个`时，才可设置为 2；无明确来源的组不自动写入。
- staging：同步补充 `parsed_material/parsed_thickness/parsed_width/parsed_pitch/parsed_position/parsed_cavity_count` 的空字段并备份。
- parts/tooling：只填 NULL/空值；任何不同非空值都不覆盖，列入冲突报告。

特别处理 TYAA-Q0093：

- 两个零件都应得到相同材料。
- 两个零件 thickness=0.4，width/pitch 保持 NULL。
- position 分别 left/right。
- 因文件普通备注为空，不得仅凭脚本声称 cavity_count 来源于 Excel；报告中说明用户确认的业务规则与文件缺失之间的差异，暂不自动合并 tooling。

执行前备份所有将更新的 staging、parts、tooling_parts、tooling 行；单一事务执行，生成回滚信息。

## 三、前端显示

修改 `frontend/src/views/parts/index.vue`：

- 完整 T/W/P：`0.8×34×34.5`
- 只有 T：`0.4`
- T+W：`0.4×92`
- 中间维度缺失但后续存在时必须保留占位避免歧义，如 `0.4×-×53`
- 不再显示 `T0.8×W34×P34.5`
- 全空仍显示 `-`

详情页保留“厚度/宽度/节距”字段标签，但数值与列表一致。

## 四、强制验收

必须使用 PostgreSQL MCP/只读 SQL 和 Playwright 浏览器 MCP：

1. SQL/Excel 对照 TYAA-Q0093 左右件：材料相同、T=.4、W/P NULL、position left/right。
2. 浏览器用模具号 `TYAA-Q0093` 搜索，应返回左右两件。
3. 列表两行规格均显示 `0.4`，材料均显示 `SUS301-CSP 3/4H（JIS G4305）`。
4. 打开左右两件详情，字段与数据库一致。
5. 再抽样至少 3 组含完整 `1出2`规格的左右件，确认两边材料/T/W/P一致，且明确来源的 cavity_count=2。
6. 默认页面已有完整规格的值不带 T/W/P 字母。
7. 相关网络请求 200、控制台相关错误 0。
8. 截图保存 `screenshots/left-right-shared-spec/`，真实 PNG 并检查签名。

## 报告

生成 `LEFT_RIGHT_SHARED_SPEC_RESULT.md`，包含：

- 候选组、可安全更新组、冲突组、无明确 cavity 来源组数量
- 实际更新的 staging/parts/tooling_parts/tooling 行数
- TYAA-Q0093 逐字段前后对照
- 3 组 `1出2`抽样
- 备份和回滚路径
- Playwright 操作、网络、控制台、截图
- 未完成项；不得用用户口述冒充 Excel 文件内容

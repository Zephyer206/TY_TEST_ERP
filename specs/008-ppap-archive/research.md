# Research decisions

1. **Decision**: 复用现有公司和 API client。**Rationale**: 前后端已有共享 registry，避免直接后端路径。
2. **Decision**: 质量部门判定服务端执行，正式身份按 dept 校验；验收模式明确返回该模式。**Rationale**: 本机现有 AUTH_DISABLED 管理员身份，不能靠前端按钮证明权限；用身份覆盖的服务端测试补充正式权限验收。
3. **Decision**: 本地 LibreOffice 转 PDF 供浏览器阅读。**Rationale**: 现有系统无 Excel 预览器，也未安装 Excel。保留原件、中文、图片、合并区域和工作表输出，不将客户文件发送外部服务。
   官方依据：[命令行转换与独立 profile](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html?DbPAR=BASIC&System=WIN)、[官方下载](https://www.libreoffice.org/download/)。
   **Alternative**: 简单 HTML 单元格表格会丢失图片及排版；第三方云预览涉及外部数据传输，本期不用。
4. **Decision**: 提交快照引用不可变文件版本并保存当时目录/关联名称。**Rationale**: 后续改名、更新关联和文件不会篡改客户已收到的资料。

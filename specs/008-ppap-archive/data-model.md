# PPAP data model

- `ppap_archives`: id、company、record_no、name、customer_key/name、owner、planned_date、remark、links(JSON)、revision、created/updated。
- `ppap_folders`: id、archive_id、parent_id、name。根目录用 null 表示；同父目录名称唯一。
- `ppap_documents`: id、archive_id、folder_id、name、linked_key、current_version。文件名保持原名。
- `ppap_file_versions`: id、document_id、version、storage_key、sha256、size、extension、created_at/by。内容不可变。
- `ppap_submissions`: id、archive_id、round_no、submitted_date、status、feedback、approved_date、valid_until、conditions、evidence_version_id、snapshot(JSON)、updated_at/by。
- `ppap_audit_logs`: id、archive_id、action、detail、actor_id/name、created_at。

修改档案及子资源前锁住档案行并核对 revision；每次修改加一。同一公司/客户下的关联对象在服务端校验。提交快照包含目录、文件版本、关联及安装包组成、档案名称和客户。

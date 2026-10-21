# PPAP API contract

All paths below are relative to the single request-client base. Authenticated reads; quality-department writes.

- GET `/ppap?company=&search=&status=&part_id=&requirement_id=&package_id=&page=&page_size=`: paginated ledger and identity/can_write.
- GET `/ppap/options?company=&customer_key=&search=`: company customers and eligible part/package references.
- POST `/ppap/{company}/archives`: create name/customer/owner/planned_date/remark/links.
- GET `/ppap/{company}/archives/{archive_id}`: archive, folders, documents+versions, submissions, audit.
- PATCH `/ppap/{company}/archives/{archive_id}`: update editable fields with expected revision.
- POST `/ppap/{company}/archives/{archive_id}/folders`: create folder with parent_id/name/revision.
- PATCH `/ppap/{company}/archives/{archive_id}/folders/{folder_id}`: rename with revision.
- POST `/ppap/{company}/archives/{archive_id}/files`: multipart file/folder_id/linked_key/mode/revision. mode=new or version; default rejects existing same-name document with 409.
- GET `/ppap/{company}/archives/{archive_id}/versions/{version_id}/preview`: PDF blob (Excel conversion cache) for all authenticated readers.
- GET `/ppap/{company}/archives/{archive_id}/versions/{version_id}/original`: original blob, quality only.
- POST `/ppap/{company}/archives/{archive_id}/submissions`: submitted_date/remark/revision; freezes current directory, links and file versions.
- PATCH `/ppap/{company}/archives/{archive_id}/submissions/{submission_id}`: overall result/feedback/approved_date/valid_until/conditions/evidence_version_id/revision.

Errors: 403 department forbidden; 404 company/archive/resource mismatch; 409 stale revision/name conflict; 400 invalid scope/dates/files; 413 >100MiB; 503 converter unavailable/timeout. A failed conversion never deletes source files.

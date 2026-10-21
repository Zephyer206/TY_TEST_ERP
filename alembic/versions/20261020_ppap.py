"""Add private customer PPAP archives, file versions and submission snapshots."""
from alembic import op
revision = '20261020_ppap'
down_revision = '20261017_nonconforming'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE TABLE ppap_archives (\n\tid VARCHAR(32) NOT NULL, \n\tcompany VARCHAR(20) NOT NULL, \n\trecord_no VARCHAR(50) NOT NULL, \n\tname VARCHAR(500) NOT NULL, \n\tcustomer_key VARCHAR(80) NOT NULL, \n\tcustomer_name VARCHAR(200) NOT NULL, \n\towner VARCHAR(100) NOT NULL, \n\tplanned_date DATE, \n\tremark TEXT NOT NULL, \n\tlinks JSONB NOT NULL, \n\trevision INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_ppap_company CHECK (company IN ('tianyue','gaibo')), \n\tUNIQUE (record_no)\n)")
    op.execute('CREATE INDEX ix_ppap_archives_company ON ppap_archives (company)')
    op.execute('CREATE TABLE ppap_folders (\n\tid VARCHAR(32) NOT NULL, \n\tarchive_id VARCHAR(32) NOT NULL, \n\tparent_id VARCHAR(32), \n\tname VARCHAR(200) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(archive_id) REFERENCES ppap_archives (id), \n\tFOREIGN KEY(parent_id) REFERENCES ppap_folders (id)\n)')
    op.execute('CREATE INDEX ix_ppap_folders_archive_id ON ppap_folders (archive_id)')
    op.execute("CREATE UNIQUE INDEX uq_ppap_folder_sibling ON ppap_folders (archive_id, coalesce(parent_id, ''), lower(name))")
    op.execute('CREATE TABLE ppap_documents (\n\tid VARCHAR(32) NOT NULL, \n\tarchive_id VARCHAR(32) NOT NULL, \n\tfolder_id VARCHAR(32), \n\tname VARCHAR(255) NOT NULL, \n\tlinked_key VARCHAR(80), \n\tcurrent_version INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(archive_id) REFERENCES ppap_archives (id), \n\tFOREIGN KEY(folder_id) REFERENCES ppap_folders (id)\n)')
    op.execute('CREATE INDEX ix_ppap_documents_archive_id ON ppap_documents (archive_id)')
    op.execute("CREATE UNIQUE INDEX uq_ppap_document_sibling ON ppap_documents (archive_id, coalesce(folder_id, ''), lower(name))")
    op.execute('CREATE TABLE ppap_file_versions (\n\tid VARCHAR(32) NOT NULL, \n\tdocument_id VARCHAR(32) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstorage_key VARCHAR(255) NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tsize INTEGER NOT NULL, \n\textension VARCHAR(10) NOT NULL, \n\tsheets JSONB NOT NULL, \n\tcreated_by VARCHAR(100) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_ppap_document_version UNIQUE (document_id, version), \n\tFOREIGN KEY(document_id) REFERENCES ppap_documents (id), \n\tUNIQUE (storage_key)\n)')
    op.execute('CREATE INDEX ix_ppap_file_versions_document_id ON ppap_file_versions (document_id)')
    op.execute('CREATE TABLE ppap_submissions (\n\tid VARCHAR(32) NOT NULL, \n\tarchive_id VARCHAR(32) NOT NULL, \n\tround_no INTEGER NOT NULL, \n\tsubmitted_date DATE, \n\tstatus VARCHAR(30) NOT NULL, \n\tfeedback TEXT NOT NULL, \n\tapproved_date DATE, \n\tvalid_until DATE, \n\tconditions TEXT NOT NULL, \n\tevidence_version_id VARCHAR(32), \n\tsnapshot JSONB NOT NULL, \n\tupdated_by VARCHAR(100) NOT NULL, \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_ppap_submission_round UNIQUE (archive_id, round_no), \n\tFOREIGN KEY(archive_id) REFERENCES ppap_archives (id), \n\tFOREIGN KEY(evidence_version_id) REFERENCES ppap_file_versions (id)\n)')
    op.execute('CREATE INDEX ix_ppap_submissions_archive_id ON ppap_submissions (archive_id)')
    op.execute('CREATE TABLE ppap_audit_logs (\n\tid VARCHAR(32) NOT NULL, \n\tarchive_id VARCHAR(32) NOT NULL, \n\taction VARCHAR(100) NOT NULL, \n\tdetail JSONB NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tactor_name VARCHAR(100) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(archive_id) REFERENCES ppap_archives (id)\n)')
    op.execute('CREATE INDEX ix_ppap_audit_logs_archive_id ON ppap_audit_logs (archive_id)')

def downgrade():
    op.drop_table('ppap_audit_logs')
    op.drop_table('ppap_submissions')
    op.drop_table('ppap_file_versions')
    op.drop_table('ppap_documents')
    op.drop_table('ppap_folders')
    op.drop_table('ppap_archives')

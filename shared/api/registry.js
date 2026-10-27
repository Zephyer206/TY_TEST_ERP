/**
 * Shared API contract metadata.
 *
 * Both frontends consume this registry before issuing a request.  The request
 * clients own transport and authentication details; this file is deliberately
 * limited to endpoint identity and lifecycle information.
 */
export const apiRegistry = Object.freeze({
  'machines.scanProduction': { key: 'machines.scanProduction', method: 'POST', path: '/machines/scan-production', auth: true, lifecycle: 'active', description: 'Issue a user-scoped machine ticket or validate an explicit completion rescan' },
  'machines.selectProduction': { key: 'machines.selectProduction', method: 'POST', path: '/machines/production-contexts', auth: true, lifecycle: 'active', description: 'Select an active assignment, actual product and process from the current machine ticket' },
  'machines.productionComplete': { key: 'machines.productionComplete', method: 'POST', path: '/machines/{machine_id}/production-complete', auth: true, lifecycle: 'active', description: 'Complete only the selected machine process after rescan and quantity difference confirmation' },
  'production.saveQrContext': { key: 'production.saveQrContext', method: 'PUT', path: '/production/plans/{order_id}/qr-context', auth: true, lifecycle: 'active', description: 'Atomically publish versioned QR order products, routes and machine targets without replacing bound identity' },
  'production.allocateOutput': { key: 'production.allocateOutput', method: 'POST', path: '/production/output-allocations', auth: true, lifecycle: 'active', description: 'Authorized production supervisors or the order owner allocate an effective output source to order and stock' },
  'productBoxes.saveQuantity': { key: 'productBoxes.saveQuantity', method: 'POST', path: '/product-boxes/{box_id}/quantities', auth: true, lifecycle: 'active', description: 'Overwrite a current process quantity with live user context and box/state versions' },
  'productBoxes.correctQuantity': { key: 'productBoxes.correctQuantity', method: 'POST', path: '/product-boxes/{box_id}/quantity-corrections', auth: true, lifecycle: 'active', description: 'Production supervisors correct completed historical quantity with reason without rewriting downstream facts' },
  'productBoxes.advance': { key: 'productBoxes.advance', method: 'POST', path: '/product-boxes/{box_id}/advance', auth: true, lifecycle: 'active', description: 'Enter only the next fixed-route process using its live machine context and preserve output/material sources' },
  'productBoxes.trace': { key: 'productBoxes.trace', method: 'GET', path: '/product-boxes/{box_id}/trace', auth: true, lifecycle: 'active', description: 'Read scoped order, route, quantities, material ancestry and paginated related trace facts' },
  'productBoxes.events': { key: 'productBoxes.events', method: 'GET', path: '/product-boxes/{box_id}/events', auth: true, lifecycle: 'active', description: 'Read append-only process events with timestamp and ID keyset pagination' },
  'productBoxes.split': { key: 'productBoxes.split', method: 'POST', path: '/product-boxes/{parent_id}/split', auth: true, lifecycle: 'active', description: 'Atomically partition a parent balance into an unused child identity with conserved order/stock uses and scoped compatible cross-order transfer' },
  'materialQr.create': { key: 'materialQr.create', method: 'POST', path: '/warehouse/material-batches', auth: true, lifecycle: 'active', description: 'Register an incoming material batch with stored QR identity; legacy LV2 guard' },
  'materialQr.list': { key: 'materialQr.list', method: 'GET', path: '/warehouse/material-batches', auth: true, lifecycle: 'active', description: 'List material batches with status/material filters and skip/limit pagination' },
  'materialQr.detail': { key: 'materialQr.detail', method: 'GET', path: '/warehouse/material-batches/{batch_id}', auth: true, lifecycle: 'active', description: 'Read material batch detail and compatible child-roll entries' },
  'materialQr.byNo': { key: 'materialQr.byNo', method: 'GET', path: '/warehouse/material-batches/by-no/{batch_no}', auth: true, lifecycle: 'active', description: 'Resolve a stored material batch number to its detail' },
  'materialQr.iqc': { key: 'materialQr.iqc', method: 'PUT', path: '/warehouse/material-batches/{batch_id}/iqc', auth: true, lifecycle: 'active', description: 'Record incoming quality result and current actor; legacy LV2 guard' },
  'materialQr.split': { key: 'materialQr.split', method: 'POST', path: '/warehouse/material-batches/{batch_id}/split', auth: true, lifecycle: 'active', description: 'Split material weight into independently identified child batches; legacy LV2 guard' },
  'materialQr.consume': { key: 'materialQr.consume', method: 'POST', path: '/warehouse/material-batches/{batch_id}/consume', auth: true, lifecycle: 'active', description: 'Consume a positive material weight with source reference; legacy LV1 guard' },
  'materialQr.scrap': { key: 'materialQr.scrap', method: 'POST', path: '/warehouse/material-batches/{batch_id}/scrap', auth: true, lifecycle: 'active', description: 'Scrap remaining material with reason; legacy LV3 guard' },
  'materialQr.trace': { key: 'materialQr.trace', method: 'GET', path: '/warehouse/material-batches/{batch_id}/trace', auth: true, lifecycle: 'active', description: 'Read material batch detail and weight transaction history' },
  'materialQr.scan': { key: 'materialQr.scan', method: 'GET', path: '/warehouse/material-batches/scan/{batch_id}', auth: true, lifecycle: 'active', description: 'Read material QR ledger and record the current actor query scan' },
  'materialQr.childScan': { key: 'materialQr.childScan', method: 'GET', path: '/warehouse/material-batches/scan/child/{child_id}', auth: true, lifecycle: 'active', description: 'Read an independent child batch with parent and siblings and record its query scan' },
  'materialQr.children': { key: 'materialQr.children', method: 'GET', path: '/warehouse/material-batches/{batch_id}/children', auth: true, lifecycle: 'active', description: 'List current and compatible legacy child rolls of one material batch' },
  'qrScans.create': { key: 'qrScans.create', method: 'POST', path: '/warehouse/scans', auth: true, lifecycle: 'active', description: 'Record an entity scan using the current server-authenticated actor' },
  'qrScans.list': { key: 'qrScans.list', method: 'GET', path: '/warehouse/scans/{entity_type}/{entity_id}', auth: true, lifecycle: 'active', description: 'Read paginated scan history for an entity type and integer ID' },
  'materialQr.reprint': { key: 'materialQr.reprint', method: 'POST', path: '/warehouse/material-batches/{batch_id}/reprint-qr', auth: true, lifecycle: 'active', description: 'Render the stored material QR identity and append a query audit marked as QR code reprint' },
  'machines.repairScan': { key: 'machines.repairScan', method: 'POST', path: '/machines/{machine_id}/scan', auth: true, lifecycle: 'active', description: 'Advance the existing two-scan fault/repair workflow using query parameters; legacy LV2 guard' },
  'machines.generateQr': { key: 'machines.generateQr', method: 'POST', path: '/machines/{machine_id}/generate-qr', auth: true, lifecycle: 'active', description: 'Render the existing machine QR identity and machine information' },
  'machines.scanQr': { key: 'machines.scanQr', method: 'GET', path: '/machines/scan/{machine_id}', auth: true, lifecycle: 'active', description: 'Read machine ledger and recent query scan history' },
  'production.verifyMaterial': { key: 'production.verifyMaterial', method: 'POST', path: '/production/sessions/verify-material', auth: true, lifecycle: 'active', description: 'Verify machine/part/material compatibility using query parameters' },
  'production.startSession': { key: 'production.startSession', method: 'POST', path: '/production/sessions/start', auth: true, lifecycle: 'active', description: 'Start a material-verified production session for the current operator; legacy LV1 guard' },
  'production.closeSession': { key: 'production.closeSession', method: 'POST', path: '/production/sessions/{session_id}/close', auth: true, lifecycle: 'active', description: 'Close an existing production session and generate its process flow card; legacy LV1 guard' },
  'production.processFlowCards': { key: 'production.processFlowCards', method: 'GET', path: '/production/process-flow-cards', auth: true, lifecycle: 'active', description: 'List process flow cards with part/machine/status filters and pagination' },
  'production.scanProcessFlow': { key: 'production.scanProcessFlow', method: 'GET', path: '/production/process-flow-cards/scan/{card_id}', auth: true, lifecycle: 'active', description: 'Read a process flow card QR ledger and recent scan history' },
  'production.reverseTraceProcessFlow': { key: 'production.reverseTraceProcessFlow', method: 'GET', path: '/production/process-flow-cards/{card_id}/reverse-trace', auth: true, lifecycle: 'active', description: 'Trace a process flow card through its production session to material and supplier' },
  'production.inboundProcessFlow': { key: 'production.inboundProcessFlow', method: 'PUT', path: '/production/process-flow-cards/{card_id}/inbound', auth: true, lifecycle: 'active', description: 'Confirm process flow card inbound using the current authenticated actor' },
  'production.reprintProcessFlow': { key: 'production.reprintProcessFlow', method: 'POST', path: '/production/process-flow-cards/{card_id}/reprint-qr', auth: true, lifecycle: 'active', description: 'Reprint the existing process flow card QR identity and append audit history' },
  'qr.generate': { key: 'qr.generate', method: 'POST', path: '/qr/generate', auth: true, lifecycle: 'active', description: 'Generate a legacy prefixed QR image; may use the configured external image uploader' },
  'qr.material': { key: 'qr.material', method: 'GET', path: '/qr/material/{batch_id}', auth: true, lifecycle: 'active', description: 'Render a material batch QR via the legacy generic QR endpoint' },
  'qr.machine': { key: 'qr.machine', method: 'GET', path: '/qr/machine/{machine_id}', auth: true, lifecycle: 'active', description: 'Render a machine QR via the legacy generic QR endpoint' },
  'qr.processFlow': { key: 'qr.processFlow', method: 'GET', path: '/qr/process-flow/{card_id}', auth: true, lifecycle: 'active', description: 'Render a process flow QR via the legacy generic QR endpoint' },
  'qr.part': { key: 'qr.part', method: 'GET', path: '/qr/part/{part_id}', auth: true, lifecycle: 'active', description: 'Render a part QR using the approved customer part number; returns conflict when none exists' },
  'warehouse.qrMaterials': { key: 'warehouse.qrMaterials', method: 'GET', path: '/warehouse/materials', auth: true, lifecycle: 'active', description: 'List the warehouse material catalogue used by material QR inbound; not the separate engineering master' },
  'warehouse.qrSuppliers': { key: 'warehouse.qrSuppliers', method: 'GET', path: '/warehouse/suppliers', auth: true, lifecycle: 'active', description: 'List suppliers for material QR inbound with active filtering and pagination' },
  'production.plans': { key: 'production.plans', method: 'GET', path: '/production/plans', auth: true, lifecycle: 'active', description: 'List production plans with stored human-readable plan numbers and pagination' },
  'productBoxes.metadata': { key: 'productBoxes.metadata', method: 'PATCH', path: '/product-boxes/{box_id}/metadata', auth: true, lifecycle: 'active', description: 'Update allowed product-box metadata with current capability, version and idempotency checks' },
  'production.qrContext': { key: 'production.qrContext', method: 'GET', path: '/production/plans/{order_id}/qr-context', auth: true, lifecycle: 'active', description: 'Read visible configured actual products and order ownership for one product QR binding order' },
  'productQrPool.list': { key: 'productQrPool.list', method: 'GET', path: '/product-qr-pool', auth: true, lifecycle: 'active', description: 'List product QR pool items within current order visibility' },
  'productQrPool.generateBatch': { key: 'productQrPool.generateBatch', method: 'POST', path: '/product-qr-pool/batches', auth: true, lifecycle: 'active', description: 'Generate a capability-checked batch of stable product QR identities with durable idempotency' },
  'productQrPool.reprint': { key: 'productQrPool.reprint', method: 'POST', path: '/product-qr-pool/{item_id}/reprint', auth: true, lifecycle: 'active', description: 'Issue a reprint job using the original stored QR identity' },
  'productQrPool.printData': { key: 'productQrPool.printData', method: 'POST', path: '/product-qr-pool/print-data', auth: true, lifecycle: 'active', description: 'Persist A4 print job items and snapshots without confirming physical printing' },
  'productQrPool.confirmPrint': { key: 'productQrPool.confirmPrint', method: 'POST', path: '/product-qr-pool/print-confirmations', auth: true, lifecycle: 'active', description: 'The print requester confirms job items once, preserving first print time and counts' },
  'productBoxes.bind': { key: 'productBoxes.bind', method: 'POST', path: '/product-boxes/bind', auth: true, lifecycle: 'active', description: 'Bind an unused pool identity once to one configured actual product and order' },
  'productBoxes.scan': { key: 'productBoxes.scan', method: 'POST', path: '/product-boxes/scan', auth: true, lifecycle: 'active', description: 'Validate the full product QR identity and visible box; optional split_parent_id narrowly previews unused child identity without granting bind or pool access' },
  'qrAdmin.capabilities': { key: 'qrAdmin.capabilities', method: 'GET', path: '/qr-admin/capabilities', auth: true, lifecycle: 'active', description: 'QR administrators query versioned explicit capability sets without account secrets' },
  'qrAdmin.saveCapabilities': { key: 'qrAdmin.saveCapabilities', method: 'PUT', path: '/qr-admin/capabilities/{user_id}', auth: true, lifecycle: 'active', description: 'QR administrators replace a version-checked capability set while retaining grant and revocation history' },
  'ppap.list': { key: 'ppap.list', method: 'GET', path: '/ppap', auth: true, lifecycle: 'active', description: 'List company PPAP archives with exact source-reference filters and server write capability' },
  'ppap.options': { key: 'ppap.options', method: 'GET', path: '/ppap/options', auth: true, lifecycle: 'active', description: 'Search company customers and customer-scoped part/package references' },
  'ppap.create': { key: 'ppap.create', method: 'POST', path: '/ppap/{company}/archives', auth: true, lifecycle: 'active', description: 'Quality creates a customer PPAP archive with verified multi-object links' },
  'ppap.detail': { key: 'ppap.detail', method: 'GET', path: '/ppap/{company}/archives/{archive_id}', auth: true, lifecycle: 'active', description: 'Read archive folders, immutable file versions, submissions and audit history' },
  'ppap.update': { key: 'ppap.update', method: 'PATCH', path: '/ppap/{company}/archives/{archive_id}', auth: true, lifecycle: 'active', description: 'Quality updates revision-checked archive metadata and linked objects' },
  'ppap.folderCreate': { key: 'ppap.folderCreate', method: 'POST', path: '/ppap/{company}/archives/{archive_id}/folders', auth: true, lifecycle: 'active', description: 'Quality creates a nested PPAP folder scoped to an archive' },
  'ppap.folderRename': { key: 'ppap.folderRename', method: 'PATCH', path: '/ppap/{company}/archives/{archive_id}/folders/{folder_id}', auth: true, lifecycle: 'active', description: 'Quality renames a folder without changing existing submission snapshots' },
  'ppap.upload': { key: 'ppap.upload', method: 'POST', path: '/ppap/{company}/archives/{archive_id}/files', auth: true, lifecycle: 'active', description: 'Quality uploads validated PDF/XLS/XLSX, explicitly resolving same-name versions' },
  'ppap.preview': { key: 'ppap.preview', method: 'GET', path: '/ppap/{company}/archives/{archive_id}/versions/{version_id}/preview', auth: true, lifecycle: 'active', description: 'Read a private PDF preview of an immutable PDF or Excel source version' },
  'ppap.original': { key: 'ppap.original', method: 'GET', path: '/ppap/{company}/archives/{archive_id}/versions/{version_id}/original', auth: true, lifecycle: 'active', description: 'Quality downloads the original private source file version' },
  'ppap.submit': { key: 'ppap.submit', method: 'POST', path: '/ppap/{company}/archives/{archive_id}/submissions', auth: true, lifecycle: 'active', description: 'Quality records a customer submission and freezes directory, references, composition and file versions' },
  'ppap.feedback': { key: 'ppap.feedback', method: 'PATCH', path: '/ppap/{company}/archives/{archive_id}/submissions/{submission_id}', auth: true, lifecycle: 'active', description: 'Quality records whole-package customer feedback and temporary approval conditions, expiry and evidence' },
  'nonconforming.workspace': {
    key: 'nonconforming.workspace', method: 'GET', path: '/nonconforming', auth: true, lifecycle: 'active',
    description: 'Read company nonconforming records, source batch metadata, rework molds and server identity from PostgreSQL',
  },
  'nonconforming.create': {
    key: 'nonconforming.create', method: 'POST', path: '/nonconforming/{company}/records', auth: true, lifecycle: 'active',
    description: 'Quality creates a pending-confirmation record with server validation',
  },
  'nonconforming.action': {
    key: 'nonconforming.action', method: 'POST', path: '/nonconforming/{company}/records/{record_id}/actions', auth: true, lifecycle: 'active',
    description: 'Execute a revision-checked workflow command with server permissions, quantities and audit history',
  },
  'nonconforming.saveMold': {
    key: 'nonconforming.saveMold', method: 'POST', path: '/nonconforming/{company}/molds', auth: true, lifecycle: 'active',
    description: 'Development saves a revision-checked rework mold and validates company/part/history links and photos',
  },
  'workbench.list': {
    key: 'workbench.list', method: 'GET', path: '/workbench', auth: true, lifecycle: 'active',
    description: 'Read source-derived role tasks, assignments, handoff requirements, blocked counts and integration coverage for the authenticated effective identity',
  },
  'workbench.claim': { key: 'workbench.claim', method: 'POST', path: '/workbench/tasks/claim', auth: true, lifecycle: 'active', description: 'Claim an eligible current source task with source revision and assignment version checks' },
  'workbench.release': { key: 'workbench.release', method: 'POST', path: '/workbench/tasks/release', auth: true, lifecycle: 'active', description: 'Release an owned or manager-controlled task with version checks and an audit record' },
  'workbench.assign': { key: 'workbench.assign', method: 'POST', path: '/workbench/tasks/assign', auth: true, lifecycle: 'active', description: 'An authorized source queue manager assigns an eligible user with concurrency checks and audit history' },
  'workbench.assignees': { key: 'workbench.assignees', method: 'GET', path: '/workbench/tasks/assignees', auth: true, lifecycle: 'active', description: 'An authorized queue manager lists users eligible to receive the current source task' },
  'auth.login': {
    key: 'auth.login',
    method: 'POST',
    path: '/auth/login',
    auth: false,
    lifecycle: 'active',
    description: 'Authenticate a user and return access and refresh tokens',
  },
  'auth.me': {
    key: 'auth.me',
    method: 'GET',
    path: '/auth/me',
    auth: true,
    lifecycle: 'active',
    description: 'Return the authenticated user profile',
  },
  'auth.logout': {
    key: 'auth.logout',
    method: 'POST',
    path: '/auth/logout',
    auth: true,
    lifecycle: 'active',
    description: 'Invalidate the current authentication session',
  },
  'machines.list': {
    key: 'machines.list', method: 'GET', path: '/machines', auth: true, lifecycle: 'active',
    description: 'List active production machines',
  },
  'machines.pressTypes': {
    key: 'machines.pressTypes', method: 'GET', path: '/machines/press-types', auth: true, lifecycle: 'active',
    description: 'List installed press types grouped by tonnage and standard/dual-axis; no individual machine assignment',
  },
  'machines.detail': {
    key: 'machines.detail', method: 'GET', path: '/machines/{machine_id}', auth: true, lifecycle: 'active',
    description: 'Load production machine detail',
  },
  'machines.update': {
    key: 'machines.update', method: 'PATCH', path: '/machines/{machine_id}', auth: true, lifecycle: 'active',
    description: 'Update editable production machine master data',
  },
  'admin.contextInfo': {
    key: 'admin.contextInfo', method: 'GET', path: '/admin/context-info', auth: true, lifecycle: 'active',
    description: 'Return the current administration context switch',
  },
  'admin.departments': {
    key: 'admin.departments', method: 'GET', path: '/admin/departments', auth: true, lifecycle: 'active',
    description: 'List departments available for context switching',
  },
  'admin.switchContext': {
    key: 'admin.switchContext', method: 'POST', path: '/admin/switch-context', auth: true, lifecycle: 'active',
    description: 'Switch the current administrator context',
  },
  'admin.switchBack': {
    key: 'admin.switchBack', method: 'POST', path: '/admin/switch-back', auth: true, lifecycle: 'active',
    description: 'Return to the administrator context',
  },
  'parts.list': {
    key: 'parts.list',
    method: 'GET',
    path: '/parts',
    auth: true,
    lifecycle: 'active',
    description: 'List parts with pagination and filters; search matches customer name/code, customer part number, part name, and tooling number',
  },
  'customers.list': {
    key: 'customers.list',
    method: 'GET',
    path: '/customers',
    auth: true,
    lifecycle: 'active',
    description: 'List customers and optionally restrict to customers with parts',
  },
  'customerPrices.yearPrices': {
    key: 'customerPrices.yearPrices',
    method: 'GET',
    path: '/customer-prices/customers/{customer_id}/year-prices',
    auth: true,
    lifecycle: 'active',
    description: 'Return the current yearly prices for a customer\'s parts',
  },
  'production.report': {
    key: 'production.report',
    method: 'POST',
    path: '/production/reports',
    auth: true,
    lifecycle: 'active',
    description: 'Submit a production report for a production session',
  },
  'packaging.inventory': {
    key: 'packaging.inventory',
    method: 'GET',
    path: '/packaging/inventory',
    auth: true,
    lifecycle: 'active',
    description: 'List inventory records available for delivery',
  },
  'warehouse.finishedGoods': {
    key: 'warehouse.finishedGoods', method: 'GET', path: '/warehouse/finished-goods', auth: true, lifecycle: 'active',
    description: 'List formal finished-goods inventory balances with part and customer data',
  },
  'warehouse.finishedGoodsReview': {
    key: 'warehouse.finishedGoodsReview', method: 'GET', path: '/warehouse/finished-goods/review', auth: true, lifecycle: 'active',
    description: 'List isolated review rows from the latest finished-goods snapshot',
  },
  'warehouse.finishedGoodsLedger': {
    key: 'warehouse.finishedGoodsLedger', method: 'GET', path: '/warehouse/finished-goods/{inventory_id}/ledger', auth: true, lifecycle: 'active',
    description: 'Return daily finished-goods incoming and outgoing ledger',
  },
  'warehouse.finishedGoodsLedgerEntry': {
    key: 'warehouse.finishedGoodsLedgerEntry', method: 'POST', path: '/warehouse/finished-goods/{inventory_id}/ledger/entry', auth: true, lifecycle: 'active',
    description: 'Register a finished-goods income or expense, including historical backfill',
  },
  'warehouse.finishedGoodsLedgerReconcile': {
    key: 'warehouse.finishedGoodsLedgerReconcile', method: 'POST', path: '/warehouse/finished-goods/{inventory_id}/ledger/reconcile', auth: true, lifecycle: 'active',
    description: 'Reconcile physical finished-goods stock and record a stocktake difference',
  },
  'warehouse.finishedGoodsLocation': {
    key: 'warehouse.finishedGoodsLocation', method: 'PATCH', path: '/warehouse/finished-goods/{inventory_id}/location', auth: true, lifecycle: 'active',
    description: 'Update a finished-goods storage location',
  },
  'warehouse.finishedGoodsAdjust': {
    key: 'warehouse.finishedGoodsAdjust', method: 'POST', path: '/warehouse/finished-goods/{inventory_id}/adjust', auth: true, lifecycle: 'active',
    description: 'Apply an audited finished-goods stock adjustment',
  },
  'warehouse.finishedGoodsReviewResolve': {
    key: 'warehouse.finishedGoodsReviewResolve', method: 'POST', path: '/warehouse/finished-goods/review/{row_id}/resolve', auth: true, lifecycle: 'active',
    description: 'Confirm a review row into formal finished-goods inventory',
  },
  'qr.lookup': {
    key: 'qr.lookup',
    method: 'GET',
    path: '/qr/lookup',
    auth: true,
    lifecycle: 'active',
    description: 'Resolve a scanned QR code to its business entity',
  },
  'parts.grouped': {
    key: 'parts.grouped', method: 'GET', path: '/parts/grouped', auth: true, lifecycle: 'active',
    description: 'List grouped parts for the parts workspace; search matches customer name/code, customer part number, part name, and tooling number',
  },
  'parts.create': {
    key: 'parts.create', method: 'POST', path: '/parts', auth: true, lifecycle: 'active',
    description: 'Create a part record',
  },
  'parts.delete': {
    key: 'parts.delete', method: 'DELETE', path: '/parts/{part_id}', auth: true, lifecycle: 'active',
    description: 'Delete a part record',
  },
  'parts.editor.detail': {
    key: 'parts.editor.detail', method: 'GET', path: '/parts/{part_id}/editor/detail', auth: true, lifecycle: 'active',
    description: 'Load the part editor detail and optional tooling catalog',
  },
  'parts.editor.update': {
    key: 'parts.editor.update', method: 'PATCH', path: '/parts/{part_id}/editor', auth: true, lifecycle: 'active',
    description: 'Update editable part fields',
  },
  'parts.editor.bulk': {
    key: 'parts.editor.bulk', method: 'PUT', path: '/parts/{part_id}/editor/bulk', auth: true, lifecycle: 'active',
    description: 'Save part aliases, tooling associations, and TWP specs',
  },
  'parts.editor.history': {
    key: 'parts.editor.history', method: 'GET', path: '/parts/{part_id}/editor/history', auth: true, lifecycle: 'active',
    description: 'List part editor change history',
  },
  'parts.toolingSpec.primary': {
    key: 'parts.toolingSpec.primary', method: 'PATCH', path: '/parts/tooling-specs/{spec_id}/primary', auth: true, lifecycle: 'active',
    description: 'Set a tooling specification as primary',
  },
  'customers.create': {
    key: 'customers.create', method: 'POST', path: '/customers', auth: true, lifecycle: 'active',
    description: 'Create a customer',
  },
  'customers.update': {
    key: 'customers.update', method: 'PATCH', path: '/customers/{customer_id}', auth: true, lifecycle: 'active',
    description: 'Update a customer',
  },
  'customers.delete': {
    key: 'customers.delete', method: 'DELETE', path: '/customers/{customer_id}', auth: true, lifecycle: 'active',
    description: 'Delete a customer',
  },
  'partNames.list': {
    key: 'partNames.list', method: 'GET', path: '/part-names', auth: true, lifecycle: 'active',
    description: 'List part-name dictionary values',
  },
  'partNames.create': {
    key: 'partNames.create', method: 'POST', path: '/part-names', auth: true, lifecycle: 'active',
    description: 'Create a part-name dictionary value',
  },
  'partNames.update': {
    key: 'partNames.update', method: 'PATCH', path: '/part-names/{item_id}', auth: true, lifecycle: 'active',
    description: 'Update a part-name dictionary value',
  },
  'partNames.delete': {
    key: 'partNames.delete', method: 'DELETE', path: '/part-names/{item_id}', auth: true, lifecycle: 'active',
    description: 'Delete a part-name dictionary value',
  },
  'materials.list': {
    key: 'materials.list', method: 'GET', path: '/materials', auth: true, lifecycle: 'active',
    description: 'List material master data',
  },
  'materials.create': {
    key: 'materials.create', method: 'POST', path: '/materials', auth: true, lifecycle: 'active',
    description: 'Create a material',
  },
  'materials.update': {
    key: 'materials.update', method: 'PATCH', path: '/materials/{item_id}', auth: true, lifecycle: 'active',
    description: 'Update a material',
  },
  'materials.delete': {
    key: 'materials.delete', method: 'DELETE', path: '/materials/{item_id}', auth: true, lifecycle: 'active',
    description: 'Delete a material',
  },
  'machineTonnages.list': {
    key: 'machineTonnages.list', method: 'GET', path: '/machine-tonnages', auth: true, lifecycle: 'active',
    description: 'List machine tonnage dictionary values',
  },
  'machineTonnages.create': {
    key: 'machineTonnages.create', method: 'POST', path: '/machine-tonnages', auth: true, lifecycle: 'active',
    description: 'Create a machine tonnage value',
  },
  'machineTonnages.update': {
    key: 'machineTonnages.update', method: 'PATCH', path: '/machine-tonnages/{item_id}', auth: true, lifecycle: 'active',
    description: 'Update a machine tonnage value',
  },
  'machineTonnages.delete': {
    key: 'machineTonnages.delete', method: 'DELETE', path: '/machine-tonnages/{item_id}', auth: true, lifecycle: 'active',
    description: 'Delete a machine tonnage value',
  },
  'moldTypes.list': {
    key: 'moldTypes.list', method: 'GET', path: '/mold-types', auth: true, lifecycle: 'active',
    description: 'List mold type dictionary values',
  },
  'moldTypes.create': {
    key: 'moldTypes.create', method: 'POST', path: '/mold-types', auth: true, lifecycle: 'active',
    description: 'Create a mold type value',
  },
  'moldTypes.update': {
    key: 'moldTypes.update', method: 'PATCH', path: '/mold-types/{item_id}', auth: true, lifecycle: 'active',
    description: 'Update a mold type value',
  },
  'moldTypes.delete': {
    key: 'moldTypes.delete', method: 'DELETE', path: '/mold-types/{item_id}', auth: true, lifecycle: 'active',
    description: 'Delete a mold type value',
  },
  'partDisplayGroups.list': {
    key: 'partDisplayGroups.list', method: 'GET', path: '/part-display-groups', auth: true, lifecycle: 'active',
    description: 'List part display groups',
  },
  'partDisplayGroups.create': {
    key: 'partDisplayGroups.create', method: 'POST', path: '/part-display-groups', auth: true, lifecycle: 'active',
    description: 'Create a part display group',
  },
  'partDisplayGroups.delete': {
    key: 'partDisplayGroups.delete', method: 'DELETE', path: '/part-display-groups/{group_id}', auth: true, lifecycle: 'active',
    description: 'Delete a part display group',
  },
  'quotes.list': {
    key: 'quotes.list', method: 'GET', path: '/quotes', auth: true, lifecycle: 'active',
    description: 'List quotes',
  },
  'quotes.detail': {
    key: 'quotes.detail', method: 'GET', path: '/quotes/{quote_id}', auth: true, lifecycle: 'active',
    description: 'Load quote details',
  },
  'quotes.create': {
    key: 'quotes.create', method: 'POST', path: '/quotes', auth: true, lifecycle: 'active',
    description: 'Create a quote',
  },
  'quotes.pricing': {
    key: 'quotes.pricing', method: 'POST', path: '/quotes/{quote_id}/pricing', auth: true, lifecycle: 'active',
    description: 'Save quote pricing',
  },
  'quotes.submitReview': {
    key: 'quotes.submitReview', method: 'POST', path: '/quotes/{quote_id}/submit-review', auth: true, lifecycle: 'active',
    description: 'Submit a quote for technical review',
  },
  'quotes.submitBoss': {
    key: 'quotes.submitBoss', method: 'POST', path: '/quotes/{quote_id}/submit-boss', auth: true, lifecycle: 'active',
    description: 'Submit a quote for boss approval',
  },
  'quotes.bossApprove': {
    key: 'quotes.bossApprove', method: 'POST', path: '/quotes/{quote_id}/boss-approve', auth: true, lifecycle: 'active',
    description: 'Approve or reject a quote',
  },
  'quotes.fix': {
    key: 'quotes.fix', method: 'POST', path: '/quotes/{quote_id}/fix', auth: true, lifecycle: 'active',
    description: 'Complete quote nomination fixing',
  },
  'quotes.revokeNomination': {
    key: 'quotes.revokeNomination', method: 'POST', path: '/quotes/{quote_id}/revoke-nomination', auth: true, lifecycle: 'active',
    description: 'Revoke quote nomination',
  },
  'customerInquiries.list': {
    key: 'customerInquiries.list', method: 'GET', path: '/customer-inquiries', auth: true, lifecycle: 'active',
    description: 'List customer inquiries with optional technical-review and search filters',
  },
  'customerInquiries.detail': {
    key: 'customerInquiries.detail', method: 'GET', path: '/customer-inquiries/{inquiry_id}', auth: true, lifecycle: 'active',
    description: 'Load a customer inquiry and its uploaded attachments',
  },
  'customerInquiries.create': {
    key: 'customerInquiries.create', method: 'POST', path: '/customer-inquiries', auth: true, lifecycle: 'active',
    description: 'Create a customer inquiry with uploaded technical-review files',
  },
  'customerInquiries.technicalReview': {
    key: 'customerInquiries.technicalReview', method: 'POST', path: '/customer-inquiries/{inquiry_id}/technical-review', auth: true, lifecycle: 'active',
    description: 'Save inquiry technical data with validated press-type/tonnage snapshots; omit status for a draft or submit a review decision',
  },
  'quoteGroups.list': {
    key: 'quoteGroups.list', method: 'GET', path: '/quote-groups', auth: true, lifecycle: 'active',
    description: 'List quotation groups with engineering press type, tonnage, dual-axis snapshots and final customer prices',
  },
  'quoteGroups.detail': {
    key: 'quoteGroups.detail', method: 'GET', path: '/quote-groups/{group_id}', auth: true, lifecycle: 'active',
    description: 'Load a quotation group with press engineering metadata, tooling estimate and final prices',
  },
  'quoteGroups.create': {
    key: 'quoteGroups.create', method: 'POST', path: '/quote-groups', auth: true, lifecycle: 'active',
    description: 'Create a quotation group from technical review; shared tooling is counted once in the initial price',
  },
  'quoteGroups.update': {
    key: 'quoteGroups.update', method: 'PATCH', path: '/quote-groups/{group_id}', auth: true, lifecycle: 'active',
    description: 'Update final customer tooling price, quotation scheme and part prices; preserve engineering snapshots',
  },
  'quoteGroups.syncPress': {
    key: 'quoteGroups.syncPress', method: 'POST', path: '/quote-groups/{group_id}/sync-press', auth: true, lifecycle: 'active',
    description: 'Synchronize press type, tonnage and axis metadata from the approved inquiry; preserve all prices, other technical fields and status; reject locked groups',
  },
  'production.workbench': {
    key: 'production.workbench', method: 'GET', path: '/production/plans/workbench', auth: true, lifecycle: 'active',
    description: 'List production workbench plans; optional plan_id focuses a single unscheduled plan from the personal workbench',
  },
  'production.planningPartOptions': {
    key: 'production.planningPartOptions', method: 'GET', path: '/production/planning-part-options', auth: true, lifecycle: 'active',
    description: 'Search parts available for production planning',
  },
  'production.plansCount': {
    key: 'production.plansCount', method: 'GET', path: '/production/plans-count', auth: true, lifecycle: 'active',
    description: 'Count production plans by status',
  },
  'production.plansBatch': {
    key: 'production.plansBatch', method: 'POST', path: '/production/plans/batch', auth: true, lifecycle: 'active',
    description: 'Create production plans in batch',
  },
  'production.materialConfirmations': {
    key: 'production.materialConfirmations', method: 'POST', path: '/production/plans/material-confirmations', auth: true, lifecycle: 'active',
    description: 'Confirm production plan materials',
  },
  'production.planUpdate': {
    key: 'production.planUpdate', method: 'PATCH', path: '/production/plans/{plan_id}', auth: true, lifecycle: 'active',
    description: 'Update production plan settings',
  },
  'production.planCancel': {
    key: 'production.planCancel', method: 'POST', path: '/production/plans/{plan_id}/cancel', auth: true, lifecycle: 'active',
    description: 'Cancel a production plan',
  },
  'production.schedulingWorkbench': {
    key: 'production.schedulingWorkbench', method: 'GET', path: '/production/scheduling-workbench', auth: true, lifecycle: 'active',
    description: 'Load the production scheduling board with shared press type keys, labels and dual-axis classification',
  },
  'production.schedule': {
    key: 'production.schedule', method: 'POST', path: '/production/plans/{plan_id}/schedule', auth: true, lifecycle: 'active',
    description: 'Schedule a production plan',
  },
  'production.unschedule': {
    key: 'production.unschedule', method: 'POST', path: '/production/plans/{plan_id}/unschedule', auth: true, lifecycle: 'active',
    description: 'Remove a production plan from schedule',
  },
  'production.reorder': {
    key: 'production.reorder', method: 'POST', path: '/production/scheduling/reorder', auth: true, lifecycle: 'active',
    description: 'Reorder scheduled plans on a machine',
  },
  'packaging.records': {
    key: 'packaging.records', method: 'GET', path: '/packaging/records', auth: true, lifecycle: 'active',
    description: 'List packaging records',
  },
  'packaging.scan': {
    key: 'packaging.scan', method: 'POST', path: '/packaging/scan', auth: true, lifecycle: 'active',
    description: 'Register a packaging scan',
  },
  'packaging.inspect': {
    key: 'packaging.inspect', method: 'POST', path: '/packaging/inspect/{record_id}', auth: true, lifecycle: 'active',
    description: 'Submit packaging inspection results',
  },
  'customerPrices.priceHistory': {
    key: 'customerPrices.priceHistory', method: 'GET', path: '/customer-prices/customers/{customer_id}/parts/{part_id}/price-history', auth: true, lifecycle: 'active',
    description: 'Return historical prices for a customer part',
  },
  'priceAdjustments.list': {
    key: 'priceAdjustments.list', method: 'GET', path: '/price-adjustments', auth: true, lifecycle: 'active',
    description: 'List price adjustment requests',
  },
  'priceAdjustments.create': {
    key: 'priceAdjustments.create', method: 'POST', path: '/price-adjustments', auth: true, lifecycle: 'active',
    description: 'Create a price adjustment request',
  },
  'priceAdjustments.approve': {
    key: 'priceAdjustments.approve', method: 'POST', path: '/price-adjustments/{adjustment_id}/approve', auth: true, lifecycle: 'active',
    description: 'Approve or reject a price adjustment',
  },
  'treatments.list': {
    key: 'treatments.list', method: 'GET', path: '/treatments', auth: true, lifecycle: 'active',
    description: 'List treatment dictionary values',
  },
  'treatments.create': {
    key: 'treatments.create', method: 'POST', path: '/treatments', auth: true, lifecycle: 'active',
    description: 'Create a treatment dictionary value',
  },
  'treatments.update': {
    key: 'treatments.update', method: 'PUT', path: '/treatments/{treatment_id}', auth: true, lifecycle: 'active',
    description: 'Update a treatment dictionary value',
  },
  'afterSales.workspaces': {
    key: 'afterSales.workspaces', method: 'GET', path: '/after-sales/gaibo/workspaces', auth: true, lifecycle: 'active',
    description: 'List after-sales workspaces',
  },
  'afterSales.workspace.create': {
    key: 'afterSales.workspace.create', method: 'POST', path: '/after-sales/gaibo/workspaces', auth: true, lifecycle: 'active',
    description: 'Create an after-sales workspace',
  },
  'afterSales.workspace.columns': {
    key: 'afterSales.workspace.columns', method: 'GET', path: '/after-sales/gaibo/workspaces/{workspace_id}/column-config', auth: true, lifecycle: 'active',
    description: 'Load after-sales workspace column configuration',
  },
  'afterSales.workspace.columns.update': {
    key: 'afterSales.workspace.columns.update', method: 'PUT', path: '/after-sales/gaibo/workspaces/{workspace_id}/column-config', auth: true, lifecycle: 'active',
    description: 'Save after-sales workspace column configuration',
  },
  'afterSales.search': {
    key: 'afterSales.search', method: 'GET', path: '/after-sales/gaibo/search', auth: true, lifecycle: 'active',
    description: 'Search after-sales records',
  },
  'afterSales.filterOptions': {
    key: 'afterSales.filterOptions', method: 'GET', path: '/after-sales/gaibo/filter-options', auth: true, lifecycle: 'active',
    description: 'Load after-sales filter options',
  },
  'afterSales.viewPreference': {
    key: 'afterSales.viewPreference', method: 'GET', path: '/after-sales/gaibo/view-preferences/{view_key}', auth: true, lifecycle: 'active',
    description: 'Load an after-sales view preference',
  },
  'afterSales.viewPreference.update': {
    key: 'afterSales.viewPreference.update', method: 'PUT', path: '/after-sales/gaibo/view-preferences/{view_key}', auth: true, lifecycle: 'active',
    description: 'Save an after-sales view preference',
  },
  'afterSales.package.detail': {
    key: 'afterSales.package.detail', method: 'GET', path: '/after-sales/gaibo/packages/{package_id}', auth: true, lifecycle: 'active',
    description: 'Load an installation package dossier',
  },
  'afterSales.package.update': {
    key: 'afterSales.package.update', method: 'PATCH', path: '/after-sales/gaibo/packages/{package_id}', auth: true, lifecycle: 'active',
    description: 'Update an installation package dossier',
  },
  'afterSales.package.item.create': {
    key: 'afterSales.package.item.create', method: 'POST', path: '/after-sales/gaibo/packages/{package_id}/items', auth: true, lifecycle: 'active',
    description: 'Create an installation package item',
  },
  'afterSales.package.item.update': {
    key: 'afterSales.package.item.update', method: 'PATCH', path: '/after-sales/gaibo/packages/{package_id}/items/{item_id}', auth: true, lifecycle: 'active',
    description: 'Update an installation package item',
  },
  'afterSales.requirement.detail': {
    key: 'afterSales.requirement.detail', method: 'GET', path: '/after-sales/gaibo/requirements/{requirement_id}', auth: true, lifecycle: 'active',
    description: 'Load a single-part after-sales dossier',
  },
  'afterSales.requirement.update': {
    key: 'afterSales.requirement.update', method: 'PATCH', path: '/after-sales/gaibo/requirements/{requirement_id}/dossier', auth: true, lifecycle: 'active',
    description: 'Update a single-part after-sales dossier',
  },
  'afterSales.requirement.drawing.create': {
    key: 'afterSales.requirement.drawing.create', method: 'POST', path: '/after-sales/gaibo/requirements/{requirement_id}/drawings', auth: true, lifecycle: 'active',
    description: 'Create an after-sales drawing version',
  },
  'afterSales.drawing.update': {
    key: 'afterSales.drawing.update', method: 'PATCH', path: '/after-sales/gaibo/drawings/{drawing_id}', auth: true, lifecycle: 'active',
    description: 'Update an after-sales drawing version',
  },
  'afterSales.requirement.route.create': {
    key: 'afterSales.requirement.route.create', method: 'POST', path: '/after-sales/gaibo/requirements/{requirement_id}/process-routes', auth: true, lifecycle: 'active',
    description: 'Create an after-sales process route',
  },
  'afterSales.route.update': {
    key: 'afterSales.route.update', method: 'PATCH', path: '/after-sales/gaibo/process-routes/{route_id}', auth: true, lifecycle: 'active',
    description: 'Update an after-sales process route',
  },
  'afterSales.requirement.document.create': {
    key: 'afterSales.requirement.document.create', method: 'POST', path: '/after-sales/gaibo/requirements/{requirement_id}/documents', auth: true, lifecycle: 'active',
    description: 'Create an after-sales requirement document',
  },
  'afterSales.package.document.create': {
    key: 'afterSales.package.document.create', method: 'POST', path: '/after-sales/gaibo/packages/{package_id}/documents', auth: true, lifecycle: 'active',
    description: 'Create an after-sales package document',
  },
  'afterSales.document.update': {
    key: 'afterSales.document.update', method: 'PATCH', path: '/after-sales/gaibo/documents/{document_id}', auth: true, lifecycle: 'active',
    description: 'Update an after-sales document',
  },
  'afterSales.installationKits.list': {
    key: 'afterSales.installationKits.list', method: 'GET', path: '/after-sales/installation-kits', auth: true, lifecycle: 'active',
    description: 'List installation kits',
  },
  'afterSales.installationKits.detail': {
    key: 'afterSales.installationKits.detail', method: 'GET', path: '/after-sales/installation-kits/{fmg_code}', auth: true, lifecycle: 'active',
    description: 'Load an installation kit detail',
  },
  'afterSales.installationKits.update': {
    key: 'afterSales.installationKits.update', method: 'PUT', path: '/after-sales/installation-kits/{fmg_code}', auth: true, lifecycle: 'active',
    description: 'Update installation kit fields',
  },
  'afterSales.installationKits.component.update': {
    key: 'afterSales.installationKits.component.update', method: 'PUT', path: '/after-sales/installation-kits/{fmg_code}/components/{source_kind}/{sequence}', auth: true, lifecycle: 'active',
    description: 'Update an installation kit component',
  },
  'afterSales.installationKits.componentPair.update': {
    key: 'afterSales.installationKits.componentPair.update', method: 'PUT', path: '/after-sales/installation-kits/{fmg_code}/component-pairs/{sequence}', auth: true, lifecycle: 'active',
    description: 'Update an installation kit component pair status',
  },
  'shippingOrders.list': {
    key: 'shippingOrders.list', method: 'GET', path: '/shipping-orders', auth: true, lifecycle: 'active',
    description: 'List shipping orders',
  },
  'shippingOrders.create': {
    key: 'shippingOrders.create', method: 'POST', path: '/shipping-orders', auth: true, lifecycle: 'active',
    description: 'Create a shipping order',
  },
  'shippingOrders.update': {
    key: 'shippingOrders.update', method: 'PATCH', path: '/shipping-orders/{order_id}', auth: true, lifecycle: 'active',
    description: 'Update a shipping order',
  },
  'shippingOrders.submit': {
    key: 'shippingOrders.submit', method: 'POST', path: '/shipping-orders/{order_id}/submit', auth: true, lifecycle: 'active',
    description: 'Submit a shipping order',
  },
  'shippingOrders.detail': {
    key: 'shippingOrders.detail', method: 'GET', path: '/shipping-orders/{order_id}', auth: true, lifecycle: 'active',
    description: 'Load a shipping order',
  },
  'shippingOrders.customerParts': {
    key: 'shippingOrders.customerParts', method: 'GET', path: '/shipping-orders/customer-parts/search', auth: true, lifecycle: 'active',
    description: 'Search customer parts for shipping',
  },
  'shippingOrders.labelConfirm': {
    key: 'shippingOrders.labelConfirm', method: 'POST', path: '/shipping-orders/lines/{line_id}/label-confirm', auth: true, lifecycle: 'active',
    description: 'Confirm a shipping label',
  },
  'shippingOrders.cancelLine': {
    key: 'shippingOrders.cancelLine', method: 'POST', path: '/shipping-orders/lines/{line_id}/cancel', auth: true, lifecycle: 'active',
    description: 'Cancel a shipping line',
  },
  'shippingOrders.cancellationConsent': {
    key: 'shippingOrders.cancellationConsent', method: 'POST', path: '/shipping-orders/lines/{line_id}/cancellation-consent', auth: true, lifecycle: 'active',
    description: 'Record shipping line cancellation consent',
  },
  'shippingOrders.confirmShipment': {
    key: 'shippingOrders.confirmShipment', method: 'POST', path: '/shipping-orders/{order_id}/shipments/confirm', auth: true, lifecycle: 'active',
    description: 'Confirm shipment for a shipping order',
  },
  'shippingOrders.history': {
    key: 'shippingOrders.history', method: 'GET', path: '/shipping-orders/{order_id}/history', auth: true, lifecycle: 'active',
    description: 'List shipping order history',
  },
  'shippingOrders.shipmentLogistics': {
    key: 'shippingOrders.shipmentLogistics', method: 'PATCH', path: '/shipping-shipments/{shipment_id}/logistics', auth: true, lifecycle: 'active',
    description: 'Update shipment logistics',
  },
})

export const getApiDefinition = (key) => {
  const definition = apiRegistry[key]
  if (!definition) throw new Error(`Unknown API registry key: ${key}`)
  return definition
}

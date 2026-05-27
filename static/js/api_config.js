/**
 * API Dispatcher - 前端网络请求集中化管理
 * 所有页面必须通过 sendApiRequest() 调用接口，禁止硬编码 fetch URL
 */
(function (global) {
    'use strict';

    // ── API 路由注册表 ──────────────────────────────────────────────
    var API_MAP = {

        // ── 业务部 ──
        'sales.calc_pricing':         { url: '/api/calc-pricing',                method: 'POST' },
        'sales.part_create':          { url: '/api/parts/create',                method: 'POST' },
        'sales.part_detail':          { url: '/api/part/{id}',                   method: 'GET'  },
        'sales.part_override':        { url: '/api/part/{id}/override',          method: 'POST' },
        'sales.sample_judgment':      { url: '/api/part/{id}/sample-judgment',  method: 'POST' },
        'sales.part_unbind':          { url: '/api/part/{id}/unbind',            method: 'POST' },
        'sales.pricing_mode':         { url: '/api/part/{id}/pricing-mode',      method: 'POST' },
        'sales.die_link':             { url: '/parts/die-link/json',          method: 'GET'  },
        'sales.materials_list':       { url: '/api/materials',                       method: 'GET'  },
        'sales.materials_quick_add':  { url: '/api/materials',                       method: 'POST' },
        'sales.materials_update':    { url: '/api/materials/{name}',                method: 'PUT'  },
        'sales.materials_prices_save':{ url: '/api/materials/prices',           method: 'POST' },
        'sales.materials_prices_del': { url: '/api/materials/prices/{name}',   method: 'DELETE'},
        'sales.material_delete':       { url: '/api/materials/prices/{name}',   method: 'DELETE'},
        'sales.materials_draft_parts':{ url: '/api/materials/prices/{name}/parts', method: 'GET' },
        'sales.materials_sync_draft': { url: '/api/materials/prices/sync-draft', method: 'POST' },
        'sales.dict_items':           { url: '/api/dict/{type}',               method: 'GET'  },
        'sales.dict_add':             { url: '/api/dict',                      method: 'POST' },
        'sales.dict_delete':          { url: '/api/dict/{type}/{id}',          method: 'DELETE'},
        'sales.treatments_list':     { url: '/api/dict/treatments',           method: 'GET'  },
        'sales.treatments_upsert':    { url: '/api/dict/treatments',           method: 'POST' },
        'sales.treatments_delete':    { url: '/api/dict/treatments/{id}',      method: 'DELETE'},

        // ── 库存体系（v12）──
        'sales.inventory_summary':         { url: '/api/parts/{partId}/inventory',              method: 'GET'  },
        'sales.finished_inventory':        { url: '/api/parts/{partId}/finished-inventory',     method: 'POST' },
        'sales.remnant_inventory':         { url: '/api/parts/{partId}/remnant-inventory',      method: 'POST' },
        'sales.inventory_finished_list':   { url: '/api/inventory/finished',                    method: 'GET'  },
        'sales.inventory_remnant_list':    { url: '/api/inventory/remnant',                     method: 'GET'  },
        'sales.inventory_finished_adjust': { url: '/api/inventory/finished/{partId}/adjust',    method: 'POST' },
        'sales.inventory_remnant_adjust':  { url: '/api/inventory/remnant/{partId}/adjust',     method: 'POST' },

        // ── 报价工作流（quotes 状态机）──
        'sales.quote_update':   { url: '/api/quotes/{id}',                     method: 'PUT'   },
        'sales.quote_delete':   { url: '/api/quotes/{id}',                     method: 'DELETE'  },
        'sales.quote_submit':   { url: '/api/quotes/{id}/submit',             method: 'POST'  },
        'sales.quote_approve':  { url: '/api/quotes/{id}/approve',            method: 'POST'  },
        'sales.quote_reject':   { url: '/api/quotes/{id}/reject',             method: 'POST'  },
        'sales.quote_create':   { url: '/api/part/{id}/quote',                method: 'POST'  },

        // ── 零件管理 ──
        'sales.part_delete':    { url: '/api/parts/{id}',                     method: 'DELETE'  },
        'sales.customers_list': { url: '/api/customers',                      method: 'GET'  },
        'sales.drawing_upload': { url: '/api/parts/drawing-upload',           method: 'POST' },
        'sales.customer_create': { url: '/api/customers',                     method: 'POST' },
        'sales.customer_update': { url: '/api/customers/{id}',                method: 'PUT'  },
        'sales.customer_delete': { url: '/api/customers/{id}',                method: 'DELETE'},

        // ── 技术部 ──
        'tech.pool_json':             { url: '/tech/pool/json',                  method: 'GET'  },
        'tech.pool_start':            { url: '/tech/pool/start',                 method: 'POST' },
        'tech.pool_complete':         { url: '/tech/pool/complete',              method: 'POST' },
        'tech.scan_process':          { url: '/tech/scan/process',               method: 'POST' },

        // ── 技术参数填写（业务提交图纸后，开发填写 T/W/P、模具费、穴数、吨位）──
        'tech.pending_quotes':        { url: '/api/tech/pending-quotes',        method: 'GET'  },
        'tech.quote_detail':         { url: '/api/tech/quote/{id}',           method: 'GET'  },
        'tech.update_params':        { url: '/api/tech/quote/{id}/params',     method: 'PUT'  },
        'tech.sdr_upload':           { url: '/api/tech/quote/{id}/sdr-upload', method: 'POST' },

        // ── 喷涂 ──
        'spray.submit':               { url: '/spray/scan/submit',               method: 'POST' },
        'spray.manager_submit':       { url: '/spray/manager/submit',            method: 'POST' },
        'spray.balance':              { url: '/api/spray/balance',               method: 'GET'  },
        'spray.recipe_list':          { url: '/api/spray/recipe',                method: 'GET'  },
        'spray.recipe_save':          { url: '/api/spray/recipe',                method: 'POST' },
        'spray.sync_part':            { url: '/api/spray/sync/{partId}',         method: 'POST' },

        // ── 仓库 ──
        'whse.materials':             { url: '/materials',                       method: 'GET'  },
        'whse.materials_add':         { url: '/materials/add',                   method: 'POST' },
        'whse.materials_detail':     { url: '/materials/{id}',                  method: 'GET'  },
        'whse.materials_update':     { url: '/materials/{id}/update',           method: 'POST' },
        'whse.whse_confirm':          { url: '/materials/{id}/whse-confirm',     method: 'POST' },
        'whse.slit':                  { url: '/materials/{id}/slit',             method: 'POST' },
        'whse.slit_fine':             { url: '/materials/{id}/slit-fine',        method: 'POST' },
        'whse.scrap':                 { url: '/materials/{id}/scrap',            method: 'POST' },

        // ── IQC ──
        'iqc.submit':                 { url: '/iqc/submit',                      method: 'POST' },

        // ── QC ──
        'qc.submit':                  { url: '/qc/submit',                       method: 'POST' },
        'qc.inspect':                { url: '/qc/inspect',                      method: 'POST' },

        // ── 模具（dies） ──
        'mold.cavity_confirm':        { url: '/cavity_review/confirm',           method: 'POST' },
        'mold.cavity_reset':          { url: '/cavity_review/reset',             method: 'POST' },
        'mold.add':                   { url: '/molds/add',                       method: 'POST' },
        'mold.update':                { url: '/molds/{id}/update',               method: 'POST' },
        'mold.delete':                { url: '/molds/{id}/delete',               method: 'POST' },
        'mold.link_add':              { url: '/tooling/{moldId}/link',           method: 'POST' },
        'mold.link_remove':           { url: '/tooling/{moldId}/unlink',         method: 'POST' },
        'mold.link_update_seq':       { url: '/tooling/{moldId}/link/{partId}/seq', method: 'POST' },
        'mold.tooling_detail':        { url: '/tooling/{moldId}',               method: 'GET'  },
        'die.add':                    { url: '/molds/add',                       method: 'POST' },
        'die.update':                 { url: '/molds/{id}/update',               method: 'POST' },
        'die.delete':                 { url: '/molds/{id}/delete',               method: 'POST' },

        // ── 生产 ──
        'prod.operator_scan':         { url: '/prod/operator/scan',              method: 'POST' },
        'prod.report':                { url: '/prod/report',                     method: 'POST' },
        'prod.plans':                 { url: '/prod/plans',                      method: 'GET'  },
        'prod.progress':              { url: '/prod/progress',                   method: 'GET'  },
        'prod.scrap_logs':           { url: '/prod/scrap',                      method: 'GET'  },
        'prod.machines':             { url: '/prod/machines',                   method: 'GET'  },
        'prod.machines_json':        { url: '/prod/machines/json',              method: 'GET'  },
        'prod.orders':               { url: '/prod/orders',                     method: 'GET'  },
        'prod.orders_json':          { url: '/prod/orders/json',                method: 'GET'  },
        'prod.sf_report':            { url: '/prod/shopfloor/report',           method: 'POST' },
        'prod.fp_approve':          { url: '/prod/shopfloor/first-piece/approve', method: 'POST' },
        'prod.fp_check':             { url: '/prod/shopfloor/first-piece/check/{woId}', method: 'GET' },

        // ── 技术部 — 双轨维修 ──
        'tech.maint_list':           { url: '/tech/maintenance/list',           method: 'GET'  },
        'tech.maint_list_json':     { url: '/tech/maintenance/list/json',       method: 'GET'  },
        'tech.maint_report':        { url: '/tech/maintenance/report',          method: 'POST' },
        'tech.maint_complete':      { url: '/tech/maintenance/complete',        method: 'POST' },
        'tech.maint_open':          { url: '/tech/maintenance/open/{equipId}', method: 'GET'  },
        'tech.quote_tech_approve':  { url: '/tech/quote/{id}/tech-approve',    method: 'POST' },
        'tech.quote_tech_reject':   { url: '/tech/quote/{id}/tech-reject',     method: 'POST' },

        // ── 包装发货 ──
        'pkg.scan':                   { url: '/pkg/scan',                        method: 'POST' },
        'pkg.entry':                  { url: '/pkg/entry',                      method: 'POST' },
        'pkg.shipping':               { url: '/pkg/shipping',                   method: 'GET'  },
        'pkg.shipping_submit':        { url: '/pkg/shipping/submit',             method: 'POST' },
        'pkg.delivery':              { url: '/pkg/delivery',                    method: 'GET'  },
        'pkg.delivery_json':         { url: '/pkg/delivery/json',               method: 'GET'  },
        'pkg.delivery_create':        { url: '/pkg/delivery/create',             method: 'POST' },
        'pkg.delivery_items':        { url: '/pkg/delivery/{dnId}/items',       method: 'GET'  },
        'pkg.delivery_notes_alias':  { url: '/pkg/delivery/notes/with-alias-status', method: 'GET' },
        'pkg.delivery_confirm':      { url: '/pkg/delivery/{dnId}/confirm',     method: 'POST' },
        'pkg.delivery_cancel':        { url: '/pkg/delivery/{dnId}/cancel',      method: 'POST' },
        'pkg.alias_upsert':         { url: '/pkg/alias/upsert',               method: 'POST' },
        'pkg.alias_query':          { url: '/pkg/alias/{partId}',             method: 'GET'  },

        // ── QC 首件 ──
        'qc.first_piece':           { url: '/qc/first-piece',                  method: 'GET'  },

        // ── 包装 ──
        'pkg.scan':                   { url: '/pkg/scan',                        method: 'POST' },
        'pkg.entry':                  { url: '/pkg/entry',                      method: 'POST' },
        'pkg.shipping':               { url: '/pkg/shipping',                   method: 'GET'  },
        'pkg.shipping_submit':        { url: '/pkg/shipping/submit',             method: 'POST' },

        // ── 管理员 ──
        'admin.machines':             { url: '/admin/machines',                  method: 'GET'  },
        'admin.machine_update':       { url: '/admin/machine/{id}',             method: 'POST' },
        'admin.audit':               { url: '/audit_production',               method: 'POST' },

        // ── QA 审计 ──
        'qa.fp_release':              { url: '/qa/first-piece/release',        method: 'POST' },
        'qa.emergency_release':       { url: '/qa/emergency-release',          method: 'POST' },
        'qa.audit_logs':              { url: '/qa/audit-logs/json',            method: 'GET'  },

        // ── 老板报价审批 ──
        'boss.quotes_list':    { url: '/api/boss/quotes',                    method: 'GET'    },
        'boss.quote_edit':     { url: '/api/boss/quotes/{id}',              method: 'PUT'    },
        'boss.quote_approve':  { url: '/api/boss/quotes/{id}/approve',     method: 'POST'   },
        'boss.quote_reject':   { url: '/api/boss/quotes/{id}/reject',       method: 'POST'   },

        // ── 生产会话 ──
        'prod.session_start':         { url: '/prod/sessions/start',           method: 'POST' },
        'prod.session_close':         { url: '/prod/sessions/close',           method: 'POST' },
        'prod.session_takeover':      { url: '/prod/sessions/takeover',        method: 'POST' },
        'prod.session_by_machine':     { url: '/prod/sessions/machine/{machineId}/sessions', method: 'GET' },
        'prod.session_active':        { url: '/prod/sessions/machine/{machineId}/active',   method: 'GET' },

        // ── 打样 ──
        'tech.part_profile_create':   { url: '/tech/parts/profile',         method: 'POST' },
        'tech.prototype_start':     { url: '/tech/prototype/start',       method: 'POST' },
        'tech.prototype_report':     { url: '/tech/prototype/report',      method: 'POST' },
        'tech.prototype_simple':    { url: '/tech/prototype/simple',      method: 'POST' },
        'tech.prototype_inventory': { url: '/tech/prototype/inventory',   method: 'GET'  },
        'tech.part_profile':        { url: '/tech/parts/{partId}/profile', method: 'GET'  },

        // ── 全检入库 ──
        'pkg.wip_stock_in':          { url: '/pkg/wip/stock-in',           method: 'POST' },
        'pkg.wip_overview':          { url: '/pkg/wip/json',              method: 'GET'  },
        'pkg.defect_logs':           { url: '/pkg/defects/json',           method: 'GET'  },
        'pkg.force_close_packing':   { url: '/pkg/wip/{workOrderId}/force-close', method: 'POST' },
    };

    /**
     * 统一 API 请求分发函数
     * @param {string} module  API_MAP 中的 key，如 'tech.pool_start'
     * @param {object} payload 请求参数对象
     * @param {object} opts    可选配置 { pathParams: {}, queryParams: {}, headers: {} }
     * @returns {Promise}
     */
    function sendApiRequest(module, payload, opts) {
        opts = opts || {};
        var cfg = API_MAP[module];
        if (!cfg) {
            return Promise.reject(new Error('[API Dispatcher] 未注册的模块: ' + module));
        }

        // URL 路径参数替换（如 /api/part/{id}/override → /api/part/123/override）
        var url = cfg.url;
        var pathParams = opts.pathParams || {};
        for (var key in pathParams) {
            url = url.replace('{' + key + '}', pathParams[key]);
        }

        // GET query string 拼接（如 ?customer=万宝）
        var queryParams = opts.queryParams || {};
        var qKeys = Object.keys(queryParams).filter(function(k) { return queryParams[k] !== undefined && queryParams[k] !== null && queryParams[k] !== ''; });
        if (qKeys.length) {
            url += '?' + qKeys.map(function(k) { return encodeURIComponent(k) + '=' + encodeURIComponent(queryParams[k]); }).join('&');
        }

        var fetchOpts = {
            method: cfg.method,
            credentials: 'same-origin',
            headers: Object.assign(
                { 'Content-Type': 'application/json' },
                opts.headers || {}
            ),
        };

        if (cfg.method !== 'GET' && payload) {
            // 如果已有 FormData（文件上传场景），不设置 JSON Content-Type
            if (payload instanceof FormData) {
                delete fetchOpts.headers['Content-Type'];
                fetchOpts.body = payload;
            } else {
                fetchOpts.body = JSON.stringify(payload);
            }
        }

        return fetch(url, fetchOpts)
            .then(function (r) {
                var ct = (r.headers.get('Content-Type') || '').toLowerCase();
                if (ct.indexOf('application/json') !== -1) return r.json();
                return r.text().then(function (t) { return { _text: t }; });
            });
    }

    /**
     * 快捷方法：GET 请求
     */
    function apiGet(module, pathParams) {
        return sendApiRequest(module, null, { pathParams: pathParams });
    }

    /**
     * 快捷方法：POST 请求（JSON body）
     */
    function apiPost(module, payload, pathParams) {
        return sendApiRequest(module, payload, { pathParams: pathParams });
    }

    /**
     * 快捷方法：PUT 请求（JSON body）
     */
    function apiPut(module, payload, pathParams) {
        return sendApiRequest(module, payload, { pathParams: pathParams });
    }

    /**
     * 快捷方法：DELETE 请求
     */
    function apiDelete(module, pathParams) {
        return sendApiRequest(module, null, { pathParams: pathParams });
    }

    // ── 全局挂载 ──────────────────────────────────────────────────
    global.sendApiRequest = sendApiRequest;
    global.apiGet         = apiGet;
    global.apiPost        = apiPost;
    global.apiPut         = apiPut;
    global.apiDelete      = apiDelete;

})(window);

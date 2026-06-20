export default {
  // 通用
  common: {
    confirm: '确认',
    cancel: '取消',
    save: '保存',
    delete: '删除',
    edit: '编辑',
    add: '新增',
    search: '搜索',
    reset: '重置',
    submit: '提交',
    back: '返回',
    success: '成功',
    error: '失败',
    loading: '加载中...',
    noData: '暂无数据',
    actions: '操作',
    status: '状态',
    createdAt: '创建时间',
    updatedAt: '更新时间',
  },

  // 登录
  login: {
    title: '云冲压 ERP 系统',
    username: '用户名',
    password: '密码',
    loginButton: '登录',
    loggingIn: '登录中...',
    usernamePlaceholder: '请输入用户名',
    passwordPlaceholder: '请输入密码',
    loginFailed: '登录失败，请检查用户名和密码',
  },

  // 菜单
  menu: {
    dashboard: '首页',
    quotes: '报价管理',
    parts: '零件管理',
    production: '生产计划',
    machines: '机台管理',
    warehouse: '仓库管理',
    quality: '质量管控',
    settings: '系统设置',
    logout: '退出登录',
  },

  // 报价管理
  quote: {
    title: '报价管理',
    newQuote: '新建报价',
    quoteNo: '报价单号',
    customer: '客户',
    productNo: '客户品号',
    vehicleModel: '车型',
    status: '审批状态',
    price: '单价',
    quantity: '数量',
    totalPrice: '总价',
    submit: '提交报价',
    approve: '审批通过',
    reject: '驳回',
    pendingTechReview: '待技术审核',
    techApproved: '技术已审核',
    pendingBossReview: '待老板审批',
    approved: '已审批',
    rejected: '已驳回',
  },

  // 零件管理
  part: {
    title: '零件管理',
    newPart: '新增零件',
    partNumber: '零件号',
    partName: '零件名称',
    customer: '客户',
    status: '状态',
    moldNumber: '模具号',
    pressTonnage: '冲压吨位',
    sampling: '打样中',
    massProduction: '量产',
    obsolete: '已淘汰',
  },

  // 生产计划
  production: {
    title: '生产计划',
    newPlan: '新建计划',
    planNo: '计划单号',
    part: '零件',
    plannedQty: '计划数量',
    completedQty: '已完成',
    machine: '机台',
    operator: '操作工',
    startDate: '开始日期',
    endDate: '结束日期',
    inProgress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
    reportProduction: '报工',
  },

  // 机台管理
  machine: {
    title: '机台管理',
    machineNo: '机台编号',
    machineName: '机台名称',
    status: '状态',
    idle: '空闲',
    running: '运行中',
    fault: '故障',
    pendingCheck: '待检',
    repairing: '维修中',
    offline: '离线',
  },

  // 仓库管理
  warehouse: {
    title: '仓库管理',
    material: '物料',
    batch: '批次',
    quantity: '数量',
    unit: '单位',
    location: '库位',
    iqc: '来料检验',
    stock: '库存',
    inbound: '入库',
    outbound: '出库',
  },

  // 质量管控
  quality: {
    title: '质量管控',
    inspection: '检验',
    firstPiece: '首件检验',
    patrol: '巡检',
    oqc: '出货检验',
    qualified: '合格',
    unqualified: '不合格',
    exemption: '免检申请',
    result: '检验结果',
    pass: '通过',
    fail: '不通过',
  },

  // 权限
  permission: {
    noPermission: '无权限',
    accessDenied: '访问被拒绝',
    insufficientPrivilege: '权限不足',
    adminOnly: '仅管理员可操作',
  },

  // 错误消息
  error: {
    networkError: '网络连接失败',
    serverError: '服务器错误',
    unauthorized: '登录已过期，请重新登录',
    forbidden: '您没有权限执行此操作',
    notFound: '请求的资源不存在',
    validationError: '数据验证失败',
    unknownError: '未知错误',
  },
}

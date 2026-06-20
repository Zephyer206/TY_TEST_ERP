/**
 * Element Plus i18n configuration for Chinese localization.
 */

import { ElMessage } from 'element-plus'

const zhCN = {
  name: 'zh-CN',
  el: {
    // Form components
    input: {
      placeholder: '请输入',
    },
    select: {
      placeholder: '请选择',
      noData: '暂无数据',
      noMatch: '无匹配数据',
    },
    datepicker: {
      placeholder: '请选择日期',
    },
    // Pagination
    pagination: {
      goto: '跳至',
      pagesize: '条/页',
      total: '共 {total} 条',
      pageClassifier: '页',
    },
    // Table
    table: {
      emptyText: '暂无数据',
      confirmFilter: '筛选',
      resetFilter: '重置',
      clearFilter: '全部',
    },
    // Dialog
    dialog: {
      confirm: '确定',
      cancel: '取消',
    },
    // Message
    message: {
      success: '操作成功',
      error: '操作失败',
      warning: '警告',
      info: '提示',
    },
    // Button
    button: {
      confirm: '确定',
      cancel: '取消',
      reset: '重置',
      submit: '提交',
      search: '搜索',
      add: '新增',
      edit: '编辑',
      delete: '删除',
      export: '导出',
      import: '导入',
      save: '保存',
      close: '关闭',
      back: '返回',
    },
    // Form validation
    form: {
      required: '该字段为必填项',
      type: {
        string: '格式不正确',
        number: '请输入数字',
        date: '日期格式不正确',
        email: '邮箱格式不正确',
        url: 'URL 格式不正确',
      },
      range: '长度在 {0} 到 {1} 之间',
    },
    // Loading
    loading: {
      loading: '加载中...',
    },
  },
}

// Status type labels
export const statusLabels: Record<string, string> = {
  // Quote statuses
  WAITING_FOR_TECH: '等待技术审核',
  TECH_APPROVED: '技术审核通过',
  TECH_REJECTED: '技术审核驳回',
  DRAFT: '草稿',
  PENDING_BOSS: '待老板审批',
  APPROVED: '已审批',
  REJECTED: '已驳回',

  // Machine statuses
  idle: '空闲',
  running: '运行中',
  fault: '故障',
  pending_check: '待检验',
  repairing: '维修中',
  offline: '离线',

  // Plan statuses
  planned: '已计划',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
  closed: '已关闭',

  // Part statuses
  SAMPLING: '打样中',
  MASS_PRODUCTION: '量产中',
  OBSOLETE: '已淘汰',

  // Active/Inactive
  active: '启用',
  inactive: '停用',

  // Process statuses
  PENDING: '待处理',
  IN_PROGRESS: '进行中',
  COMPLETED: '已完成',
}

// Role labels
export const roleLabels: Record<number, string> = {
  1: '操作工',
  2: '模具工程师',
  3: '组长/主管',
  4: '设计工程师',
  5: '业务经理',
  9: '老板',
  10: '超级管理员',
}

// Department labels
export const deptLabels: Record<string, string> = {
  production: '生产部',
  development: '开发部',
  mold: '模具部',
  design: '设计部',
  sales: '业务部',
  quality: '质量部',
  warehouse: '仓库',
}

// Date formatting
export const dateFormat = 'YYYY-MM-DD'
export const dateTimeFormat = 'YYYY-MM-DD HH:mm:ss'
export const timeFormat = 'HH:mm:ss'

// Number formatting
export const numberFormat = {
  decimals: 2,
  thousandsSep: ',',
}

// Export for use
export { zhCN }

// Vue i18n setup helper
export function setupElementPlusI18n(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  return {
    locale,
    messages: {
      'zh-CN': zhCN,
    },
  }
}

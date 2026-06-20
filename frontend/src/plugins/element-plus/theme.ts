/**
 * Element Plus theme configuration.
 * Custom theme variables for the ERP system.
 */

export const themeVariables = {
  // Brand colors
  '--el-color-primary': '#409EFF',
  '--el-color-primary-light-3': '#79bbff',
  '--el-color-primary-light-5': '#a0cfff',
  '--el-color-primary-light-7': '#c6e2ff',
  '--el-color-primary-light-8': '#d9ecff',
  '--el-color-primary-light-9': '#ecf5ff',
  '--el-color-primary-dark-2': '#337ecc',

  // Success colors
  '--el-color-success': '#67c23a',
  '--el-color-success-light-3': '#95d475',
  '--el-color-success-light-5': '#b3e19d',
  '--el-color-success-light-7': '#d1f2c8',
  '--el-color-success-light-8': '#e1f3d8',
  '--el-color-success-light-9': '#f0f9eb',
  '--el-color-success-dark-2': '#529b2e',

  // Warning colors
  '--el-color-warning': '#e6a23c',
  '--el-color-warning-light-3': '#ebb563',
  '--el-color-warning-light-5': '#f3d19e',
  '--el-color-warning-light-7': '#fbeccd',
  '--el-color-warning-light-8': '#fdf6ec',
  '--el-color-warning-light-9': '#fdfaec',
  '--el-color-warning-dark-2': '#b37b30',

  // Danger colors
  '--el-color-danger': '#f56c6c',
  '--el-color-danger-light-3': '#f89898',
  '--el-color-danger-light-5': '#fab6b6',
  '--el-color-danger-light-7': '#fcd3d3',
  '--el-color-danger-light-8': '#fde2e2',
  '--el-color-danger-light-9': '#fef0f0',
  '--el-color-danger-dark-2': '#c45656',

  // Info colors
  '--el-color-info': '#909399',
  '--el-color-info-light-3': '#b1b3b8',
  '--el-color-info-light-5': '#c8c9cc',
  '--el-color-info-light-7': '#dedfe0',
  '--el-color-info-light-8': '#e9e9eb',
  '--el-color-info-light-9': '#f4f4f5',
  '--el-color-info-dark-2': '#73767a',

  // Typography
  '--el-font-family': "'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif",
  '--el-font-size-base': '14px',
  '--el-font-size-small': '13px',
  '--el-font-size-large': '16px',

  // Border
  '--el-border-radius-base': '4px',
  '--el-border-radius-small': '2px',
  '--el-border-radius-round': '20px',
  '--el-border-color': '#dcdfe6',
  '--el-border-color-light': '#e4e7ed',
  '--el-border-color-lighter': '#ebeef5',
  '--el-border-color-extra-light': '#f2f6fc',

  // Background
  '--el-bg-color': '#ffffff',
  '--el-bg-color-page': '#f2f3f5',
  '--el-bg-color-overlay': '#ffffff',

  // Box shadow
  '--el-box-shadow': '0 2px 12px 0 rgba(0, 0, 0, 0.1)',
  '--el-box-shadow-light': '0 2px 8px 0 rgba(0, 0, 0, 0.06)',
  '--el-box-shadow-lighter': '0 1px 4px 0 rgba(0, 0, 0, 0.04)',

  // Spacing
  '--el-spacing-base': '16px',
  '--el-spacing-small': '12px',
  '--el-spacing-large': '20px',
}

// Status colors for different states
export const statusColors = {
  // Quote statuses
  WAITING_FOR_TECH: { bg: '#fdf6ec', text: '#e6a23c', border: '#f5dab1' },
  TECH_APPROVED: { bg: '#f0f9eb', text: '#67c23a', border: '#c2e7b0' },
  TECH_REJECTED: { bg: '#fef0f0', text: '#f56c6c', border: '#fbc4c4' },
  DRAFT: { bg: '#f4f4f5', text: '#909399', border: '#d3d4d6' },
  PENDING_BOSS: { bg: '#ecf5ff', text: '#409eff', border: '#a0cfff' },
  APPROVED: { bg: '#f0f9eb', text: '#67c23a', border: '#c2e7b0' },
  REJECTED: { bg: '#fef0f0', text: '#f56c6c', border: '#fbc4c4' },

  // Machine statuses
  idle: { bg: '#f0f9eb', text: '#67c23a', border: '#c2e7b0' },
  running: { bg: '#ecf5ff', text: '#409eff', border: '#a0cfff' },
  fault: { bg: '#fef0f0', text: '#f56c6c', border: '#fbc4c4' },
  pending_check: { bg: '#fdf6ec', text: '#e6a23c', border: '#f5dab1' },
  repairing: { bg: '#fdf6ec', text: '#e6a23c', border: '#f5dab1' },
  offline: { bg: '#f4f4f5', text: '#909399', border: '#d3d4d6' },
}

// Apply theme to document
export function applyTheme() {
  const root = document.documentElement

  Object.entries(themeVariables).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })
}

// Status tag helper
export function getStatusTagStyle(status: string): Record<string, string> {
  const colors = statusColors[status as keyof typeof statusColors]
  if (colors) {
    return {
      backgroundColor: colors.bg,
      color: colors.text,
      borderColor: colors.border,
    }
  }
  return {
    backgroundColor: '#f4f4f5',
    color: '#909399',
    borderColor: '#d3d4d6',
  }
}

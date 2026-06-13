/**
 * 通用工具函数
 */

/**
 * 格式化日期时间
 * @param date 日期字符串或 Date 对象
 * @param format 格式字符串，默认 'YYYY-MM-DD HH:mm:ss'
 */
export function formatDate(date: string | Date | null | undefined, format = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!date) return ''

  const d = typeof date === 'string' ? new Date(date) : date

  if (isNaN(d.getTime())) return ''

  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')

  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

/**
 * 格式化日期（仅日期）
 */
export function formatDateOnly(date: string | Date | null | undefined): string {
  return formatDate(date, 'YYYY-MM-DD')
}

/**
 * 格式化时间（仅时间）
 */
export function formatTimeOnly(date: string | Date | null | undefined): string {
  return formatDate(date, 'HH:mm:ss')
}

/**
 * 格式化相对时间
 */
export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (!date) return ''

  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diff = now.getTime() - d.getTime()

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 7) {
    return formatDate(d, 'MM-DD HH:mm')
  } else if (days > 0) {
    return `${days}天前`
  } else if (hours > 0) {
    return `${hours}小时前`
  } else if (minutes > 0) {
    return `${minutes}分钟前`
  } else {
    return '刚刚'
  }
}

/**
 * 格式化金额
 */
export function formatCurrency(amount: number | string | null | undefined, decimals = 2): string {
  if (amount === null || amount === undefined || amount === '') return '-'

  const num = typeof amount === 'string' ? parseFloat(amount) : amount

  if (isNaN(num)) return '-'

  return `¥${num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`
}

/**
 * 格式化数字
 */
export function formatNumber(num: number | string | null | undefined, decimals = 0): string {
  if (num === null || num === undefined || num === '') return '-'

  const n = typeof num === 'string' ? parseFloat(num) : num

  if (isNaN(n)) return '-'

  return n.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/**
 * 格式化百分比
 */
export function formatPercent(value: number | string | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || value === '') return '-'

  const num = typeof value === 'string' ? parseFloat(value) : value

  if (isNaN(num)) return '-'

  return `${(num * 100).toFixed(decimals)}%`
}

/**
 * 截断文本
 */
export function truncate(text: string, maxLength: number, suffix = '...'): string {
  if (!text || text.length <= maxLength) return text
  return text.slice(0, maxLength - suffix.length) + suffix
}

/**
 * 生成随机字符串
 */
export function randomString(length = 8): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

/**
 * 防抖函数
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null

  return function (this: any, ...args: Parameters<T>) {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => {
      func.apply(this, args)
    }, wait)
  }
}

/**
 * 节流函数
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let lastTime: number | null = null

  return function (this: any, ...args: Parameters<T>) {
    const now = Date.now()
    if (!lastTime || now - lastTime >= wait) {
      lastTime = now
      func.apply(this, args)
    }
  }
}

/**
 * 深拷贝
 */
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') return obj

  if (obj instanceof Date) {
    return new Date(obj.getTime()) as any
  }

  if (obj instanceof Array) {
    return obj.map(item => deepClone(item)) as any
  }

  if (obj instanceof Object) {
    const clonedObj: any = {}
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        clonedObj[key] = deepClone(obj[key])
      }
    }
    return clonedObj
  }

  return obj
}

/**
 * 校验手机号
 */
export function isValidPhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone)
}

/**
 * 校验邮箱
 */
export function isValidEmail(email: string): boolean {
  return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email)
}

/**
 * 获取枚举值的中文描述
 */
export function getEnumText(enumValue: string | number, enumMap: Record<string, string>): string {
  return enumMap[enumValue] || String(enumValue)
}

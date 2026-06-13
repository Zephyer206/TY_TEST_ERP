/**
 * 输入校验工具
 * 提供各种输入的安全校验，防止 XSS、SQL注入等问题
 */

/**
 * 移除潜在的 XSS 攻击代码
 */
export function sanitizeHtml(input: string): string {
  if (!input) return ''

  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;')
}

/**
 * 移除 SQL 注入风险字符
 */
export function sanitizeSql(input: string): string {
  if (!input) return ''

  const dangerous = [
    /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE|UNION)\b)/gi,
    /(--|;|'|"|\/\*|\*\/|@@|@)/g,
    /(0x[0-9a-f]+)/gi,
  ]

  let result = input
  for (const pattern of dangerous) {
    result = result.replace(pattern, '')
  }

  return result.trim()
}

/**
 * 校验用户名格式
 */
export function validateUsername(username: string): { valid: boolean; error?: string } {
  if (!username) {
    return { valid: false, error: '用户名不能为空' }
  }

  if (username.length < 3) {
    return { valid: false, error: '用户名至少3个字符' }
  }

  if (username.length > 50) {
    return { valid: false, error: '用户名最多50个字符' }
  }

  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    return { valid: false, error: '用户名只能包含字母、数字和下划线' }
  }

  return { valid: true }
}

/**
 * 校验密码强度
 */
export function validatePassword(password: string): { valid: boolean; error?: string } {
  if (!password) {
    return { valid: false, error: '密码不能为空' }
  }

  if (password.length < 6) {
    return { valid: false, error: '密码至少6个字符' }
  }

  if (password.length > 128) {
    return { valid: false, error: '密码最多128个字符' }
  }

  return { valid: true }
}

/**
 * 校验邮箱格式
 */
export function validateEmail(email: string): { valid: boolean; error?: string } {
  if (!email) {
    return { valid: false, error: '邮箱不能为空' }
  }

  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
  if (!emailRegex.test(email)) {
    return { valid: false, error: '邮箱格式不正确' }
  }

  return { valid: true }
}

/**
 * 校验手机号格式
 */
export function validatePhone(phone: string): { valid: boolean; error?: string } {
  if (!phone) {
    return { valid: false, error: '手机号不能为空' }
  }

  const phoneRegex = /^1[3-9]\d{9}$/
  if (!phoneRegex.test(phone)) {
    return { valid: false, error: '手机号格式不正确' }
  }

  return { valid: true }
}

/**
 * 校验零件号格式
 */
export function validatePartNumber(partNumber: string): { valid: boolean; error?: string } {
  if (!partNumber) {
    return { valid: false, error: '零件号不能为空' }
  }

  if (partNumber.length > 100) {
    return { valid: false, error: '零件号最多100个字符' }
  }

  return { valid: true }
}

/**
 * 校验数量（正整数）
 */
export function validateQuantity(qty: number | string): { valid: boolean; error?: string } {
  const num = typeof qty === 'string' ? parseInt(qty, 10) : qty

  if (isNaN(num)) {
    return { valid: false, error: '数量必须是数字' }
  }

  if (num < 0) {
    return { valid: false, error: '数量不能为负数' }
  }

  if (!Number.isInteger(num)) {
    return { valid: false, error: '数量必须是整数' }
  }

  return { valid: true }
}

/**
 * 校验价格
 */
export function validatePrice(price: number | string): { valid: boolean; error?: string } {
  const num = typeof price === 'string' ? parseFloat(price) : price

  if (isNaN(num)) {
    return { valid: false, error: '价格必须是数字' }
  }

  if (num < 0) {
    return { valid: false, error: '价格不能为负数' }
  }

  return { valid: true }
}

/**
 * 校验日期格式
 */
export function validateDate(dateStr: string): { valid: boolean; error?: string } {
  if (!dateStr) {
    return { valid: false, error: '日期不能为空' }
  }

  const dateRegex = /^\d{4}-\d{2}-\d{2}$/
  if (!dateRegex.test(dateStr)) {
    return { valid: false, error: '日期格式应为 YYYY-MM-DD' }
  }

  const date = new Date(dateStr)
  if (isNaN(date.getTime())) {
    return { valid: false, error: '日期格式不正确' }
  }

  return { valid: true }
}

/**
 * 校验ID（正整数）
 */
export function validateId(id: number | string): { valid: boolean; error?: string } {
  const num = typeof id === 'string' ? parseInt(id, 10) : id

  if (isNaN(num)) {
    return { valid: false, error: 'ID必须是数字' }
  }

  if (num <= 0) {
    return { valid: false, error: 'ID必须大于0' }
  }

  return { valid: true }
}

/**
 * 通用输入校验
 */
export interface ValidationRule {
  required?: boolean
  minLength?: number
  maxLength?: number
  pattern?: RegExp
  custom?: (value: any) => boolean
  message?: string
}

export function validate(value: any, rules: ValidationRule[]): { valid: boolean; errors: string[] } {
  const errors: string[] = []

  for (const rule of rules) {
    // 必填检查
    if (rule.required && (value === null || value === undefined || value === '')) {
      errors.push(rule.message || '此字段必填')
      continue
    }

    // 字符串长度检查
    if (typeof value === 'string') {
      if (rule.minLength !== undefined && value.length < rule.minLength) {
        errors.push(rule.message || `至少${rule.minLength}个字符`)
      }

      if (rule.maxLength !== undefined && value.length > rule.maxLength) {
        errors.push(rule.message || `最多${rule.maxLength}个字符`)
      }
    }

    // 正则检查
    if (rule.pattern && typeof value === 'string' && !rule.pattern.test(value)) {
      errors.push(rule.message || '格式不正确')
    }

    // 自定义校验
    if (rule.custom && !rule.custom(value)) {
      errors.push(rule.message || '校验失败')
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

/**
 * 校验对象中的所有字段
 */
export function validateObject<T extends Record<string, any>>(
  obj: T,
  schema: Record<keyof T, ValidationRule[]>
): { valid: boolean; errors: Record<string, string[]> } {
  const errors: Record<string, string[]> = {}

  for (const [key, rules] of Object.entries(schema)) {
    const result = validate(obj[key], rules)
    if (!result.valid) {
      errors[key] = result.errors
    }
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  }
}

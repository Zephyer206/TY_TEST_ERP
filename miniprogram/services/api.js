/**
 * WeChat Mini Program API service.
 *
 * Wraps backend API calls for the mini program.
 */

const API_BASE_URL = 'https://api.erp.example.com/api/v1'

/**
 * Request wrapper with authentication and error handling.
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = wx.getStorageSync('token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  try {
    const response = await wx.request({
      url: `${API_BASE_URL}${endpoint}`,
      method: options.method || 'GET',
      data: options.body ? JSON.parse(options.body as string) : undefined,
      header: headers,
    })

    if (response.statusCode === 200) {
      return response.data as T
    } else if (response.statusCode === 401) {
      // Unauthorized - redirect to login
      wx.removeStorageSync('token')
      wx.reLaunch({ url: '/pages/login/index' })
      throw new Error('Unauthorized')
    } else if (response.statusCode === 403) {
      throw new Error('Permission denied')
    } else {
      const errMsg = (response.data as any)?.detail || 'Request failed'
      throw new Error(errMsg)
    }
  } catch (error) {
    console.error('API request failed:', error)
    throw error
  }
}

/**
 * Auth APIs
 */
export const authApi = {
  /** Login with username and password */
  login: (username: string, password: string) =>
    request<{
      access_token: string
      token_type: string
      user: {
        id: number
        username: string
        real_name: string
        role_level: number
        department_id: number
      }
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  /** Get current user info */
  getCurrentUser: () =>
    request<{
      id: number
      username: string
      real_name: string
      role_level: number
      department_id: number
    }>('/auth/me'),
}

/**
 * QR Code APIs
 */
export const qrApi = {
  /** Look up entity by QR code */
  lookup: (code: string) =>
    request<{
      qr_code: string
      qr_type: string
      entity_id: string
      entity_name?: string
      entity_type?: string
      details?: Record<string, any>
      timestamp: string
    }>(`/qr/lookup?code=${encodeURIComponent(code)}`),

  /** Get material batch QR code info */
  getMaterialQR: (batchId: string) =>
    request<{
      qr_code: string
      content: string
      image_base64: string
    }>(`/qr/material/${encodeURIComponent(batchId)}`),

  /** Get machine QR code info */
  getMachineQR: (machineId: number) =>
    request<{
      qr_code: string
      content: string
      image_base64: string
    }>(`/qr/machine/${machineId}`),

  /** Get process flow QR code info */
  getProcessFlowQR: (cardId: number) =>
    request<{
      qr_code: string
      content: string
      image_base64: string
    }>(`/qr/process-flow/${cardId}`),
}

/**
 * Production APIs
 */
export const productionApi = {
  /** Report work progress */
  reportProgress: (data: {
    session_id: number
    passed_qty: number
    rejected_qty: number
    notes?: string
  }) =>
    request('/production/report', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  /** Get current session for machine */
  getCurrentSession: (machineId: number) =>
    request<{
      id: number
      plan_id: number
      status: string
      operator_name: string
    }>(`/production/machines/${machineId}/current-session`),
}

/**
 * Material APIs
 */
export const materialApi = {
  /** Get material batch by ID */
  getBatch: (batchId: string) =>
    request<{
      id: string
      material_name: string
      supplier_name: string
      quantity: number
      unit: string
      received_at: string
      status: string
    }>(`/warehouse/materials/batches/${encodeURIComponent(batchId)}`),

  /** Scan material for production */
  scanMaterial: (data: {
    batch_id: string
    quantity: number
  }) =>
    request('/warehouse/materials/scan', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

/**
 * Quality APIs
 */
export const qualityApi = {
  /** Submit first piece inspection */
  submitFirstPieceInspection: (data: {
    session_id: number
    result: 'pass' | 'fail'
    notes?: string
  }) =>
    request('/quality/first-piece', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

export default {
  auth: authApi,
  qr: qrApi,
  production: productionApi,
  material: materialApi,
  quality: qualityApi,
}

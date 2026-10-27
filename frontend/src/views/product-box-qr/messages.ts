export function qrError(error: unknown): string {
  const response = (error as { response?: { status?: number; data?: { code?: string; message?: string; errors?: string[]; details?: { missing_configuration?: string[] } } } })?.response
  if (response?.data?.code === 'STALE_BOX_VERSION') return '信息已被其他人更新。请重新读取，核对后再次保存。'
  if (response?.status === 503 && response.data?.code === 'STATE_CONFLICT') return response.data.message || '二维码服务暂不可用，请联系管理员检查登录与配置。'
  return response?.data?.message || response?.data?.errors?.join('；') || (error instanceof Error ? error.message : '操作未完成，请重试。')
}

import { request } from './request'

export const listWorkbenchPlans = (params = {}) => request('production.workbench', { params })
export const submitProductionReport = (sessionId, payload) => request('production.report', {
  params: { session_id: sessionId },
  data: payload,
})

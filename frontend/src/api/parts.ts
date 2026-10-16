import { callApi, callApiRaw, type ApiParams } from './client'

export const partsApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('parts.list', { params }),
  listGrouped: <T = unknown>(params: ApiParams = {}) => callApi<T>('parts.grouped', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('parts.create', { data: payload }),
  remove: <T = unknown>(partId: number | string) => callApi<T>('parts.delete', { pathParams: { part_id: partId } }),
  editorDetail: <T = unknown>(partId: number | string, params: ApiParams = {}) => callApi<T>('parts.editor.detail', { pathParams: { part_id: partId }, params }),
  updateEditor: <T = unknown>(partId: number | string, payload: unknown) => callApi<T>('parts.editor.update', { pathParams: { part_id: partId }, data: payload }),
  updateEditorRaw: <T = unknown>(partId: number | string, payload: unknown) => callApiRaw<T>('parts.editor.update', { pathParams: { part_id: partId }, data: payload, allowErrorResponse: true }),
  updateEditorBulk: <T = unknown>(partId: number | string, payload: unknown) => callApi<T>('parts.editor.bulk', { pathParams: { part_id: partId }, data: payload }),
  updateEditorBulkRaw: <T = unknown>(partId: number | string, payload: unknown) => callApiRaw<T>('parts.editor.bulk', { pathParams: { part_id: partId }, data: payload, allowErrorResponse: true }),
  editorHistory: <T = unknown>(partId: number | string) => callApi<T>('parts.editor.history', { pathParams: { part_id: partId } }),
  setPrimaryToolingSpec: <T = unknown>(specId: number | string) => callApi<T>('parts.toolingSpec.primary', { pathParams: { spec_id: specId } }),
}

export const partDisplayGroupsApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('partDisplayGroups.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('partDisplayGroups.create', { data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('partDisplayGroups.delete', { pathParams: { group_id: id } }),
}

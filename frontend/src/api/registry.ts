/**
 * Typed desktop bridge to the repository-level API contract.
 *
 * The source of truth is shared/api/registry.js so the desktop and mobile
 * clients cannot silently drift apart. This file only provides TypeScript
 * types and a stable import path for frontend modules.
 */

export type ApiMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
export type ApiLifecycle = 'active' | 'deprecated' | 'removed'

export interface ApiDefinition {
  key: string
  method: ApiMethod
  path: string
  auth: boolean
  lifecycle: ApiLifecycle
  description: string
}

export type ApiRegistry = Record<string, ApiDefinition>

// The shared contract is plain JavaScript by design for mobile H5 consumers.
// @ts-ignore: no declaration file is needed for this repository-local bridge.
import { apiRegistry as sharedApiRegistry, getApiDefinition as getSharedApiDefinition } from '../../../shared/api/registry.js'

export const apiRegistry = sharedApiRegistry as ApiRegistry

export function getApiDefinition(key: string): ApiDefinition {
  return getSharedApiDefinition(key) as ApiDefinition
}


import { request } from './request'

export const lookupQrCode = (code) => request('qr.lookup', { params: { code } })

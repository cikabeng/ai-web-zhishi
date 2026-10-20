import axios, { AxiosError } from 'axios'

import type { HealthResponse } from './types'

/**
 * 统一 HTTP 客户端。
 * baseURL 留空，走相对路径 /api，由 Vite 代理转发到后端（生产可挂在同域 nginx 下）。
 */
export const http = axios.create({
  baseURL: '',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

/** 把后端统一错误结构 {code,message,detail} 或网络错误转成人话。 */
export function toErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const payload = error.response?.data as { message?: string } | undefined
    if (payload?.message) return payload.message
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    if (!error.response) return '无法连接后端服务，请确认服务已启动'
    return `请求失败（HTTP ${error.response.status}）`
  }
  return '发生未知错误'
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/api/health')
  return data
}

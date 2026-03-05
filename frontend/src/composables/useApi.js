import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.DEV ? '/api' : '/api',
  timeout: 30000,
})

/**
 * 获取商品列表
 * @param {Object} params - 查询参数
 * @param {string} params.platform - 平台筛选 (JD/TAOBAO)
 * @param {string} params.sort_by - 排序字段
 * @param {string} params.sort_order - 排序方向 (asc/desc)
 * @param {number} params.limit - 返回数量
 * @param {number} params.offset - 偏移量
 */
export async function getProducts(params = {}) {
  const response = await api.get('/products', { params })
  return response.data
}

/**
 * 获取统计信息
 */
export async function getStats() {
  const response = await api.get('/stats')
  return response.data
}

/**
 * 手动触发同步
 */
export async function syncProducts() {
  const response = await api.post('/sync')
  return response.data
}

export default api

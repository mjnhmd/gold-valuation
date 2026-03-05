<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center py-4">
          <!-- Logo -->
          <div class="flex items-center space-x-3">
            <img src="/gold.svg" alt="Logo" class="w-10 h-10" />
            <div>
              <h1 class="text-xl font-bold text-gray-900">黄金优惠监控</h1>
              <p class="text-sm text-gray-500">实时追踪最低克价</p>
            </div>
          </div>

          <!-- Stats -->
          <div v-if="stats" class="hidden sm:flex items-center space-x-6">
            <div class="text-center">
              <p class="text-xs text-gray-500">今日最低克价</p>
              <p class="text-2xl font-bold text-red-600">
                ¥{{ stats.lowest_price_per_gram?.toFixed(2) || '--' }}
                <span class="text-sm font-normal">/克</span>
              </p>
            </div>
            <div class="text-center">
              <p class="text-xs text-gray-500">收录商品</p>
              <p class="text-lg font-semibold text-gray-700">{{ stats.total_products }}</p>
            </div>
            <div class="text-center">
              <p class="text-xs text-gray-500">最后更新</p>
              <p class="text-sm text-gray-600">{{ formatTime(stats.last_update_time) }}</p>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Mobile Stats Bar -->
    <div v-if="stats" class="sm:hidden bg-gradient-to-r from-amber-500 to-orange-500 text-white px-4 py-3">
      <div class="flex justify-between items-center">
        <span class="text-sm">今日最低克价</span>
        <span class="text-xl font-bold">¥{{ stats.lowest_price_per_gram?.toFixed(2) || '--' }}/克</span>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="bg-white border-b">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div class="flex flex-wrap items-center gap-3">
          <!-- Platform Filter -->
          <div class="flex items-center space-x-2">
            <span class="text-sm text-gray-600">平台:</span>
            <button
              v-for="p in platforms"
              :key="p.value"
              @click="selectedPlatform = p.value"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                selectedPlatform === p.value
                  ? 'bg-amber-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              ]"
            >
              {{ p.label }}
            </button>
          </div>

          <!-- Sort -->
          <div class="flex items-center space-x-2 ml-auto">
            <span class="text-sm text-gray-600">排序:</span>
            <select
              v-model="sortBy"
              class="px-3 py-1.5 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="price_per_gram">克价最低</option>
              <option value="final_price">价格最低</option>
              <option value="weight_grams">克重最大</option>
              <option value="update_time">最近更新</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div v-for="i in 8" :key="i" class="bg-white rounded-xl p-4 shadow-sm">
          <div class="skeleton h-40 rounded-lg mb-3"></div>
          <div class="skeleton h-4 rounded mb-2"></div>
          <div class="skeleton h-4 rounded w-2/3"></div>
        </div>
      </div>

      <!-- Product Grid -->
      <div v-else-if="products.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <ProductCard
          v-for="product in products"
          :key="product.item_id"
          :product="product"
        />
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <div class="text-6xl mb-4">📦</div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">暂无商品数据</h3>
        <p class="text-gray-500">系统正在努力抓取数据，请稍后刷新</p>
      </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t mt-8">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <p class="text-center text-sm text-gray-500">
          数据来源于京东、淘宝官方接口，仅供参考 |
          <span class="text-amber-600">购买前请以实际页面价格为准</span>
        </p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getProducts, getStats } from './composables/useApi'
import ProductCard from './components/ProductCard.vue'

// State
const products = ref([])
const stats = ref(null)
const loading = ref(true)
const selectedPlatform = ref('')
const sortBy = ref('price_per_gram')

// Platform options
const platforms = [
  { label: '全部', value: '' },
  { label: '京东', value: 'JD' },
  { label: '淘宝', value: 'TAOBAO' },
]

// Fetch data
async function fetchData() {
  loading.value = true
  try {
    const params = {
      sort_by: sortBy.value,
      sort_order: sortBy.value === 'update_time' ? 'desc' : 'asc',
      limit: 50,
    }
    if (selectedPlatform.value) {
      params.platform = selectedPlatform.value
    }
    const data = await getProducts(params)
    products.value = data.products
  } catch (error) {
    console.error('Failed to fetch products:', error)
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    stats.value = await getStats()
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

// Format time
function formatTime(dateStr) {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString('zh-CN')
}

// Watch filters
watch([selectedPlatform, sortBy], () => {
  fetchData()
})

// Initialize
onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

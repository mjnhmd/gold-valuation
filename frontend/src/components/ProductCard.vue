<template>
  <div class="product-card bg-white rounded-xl shadow-sm overflow-hidden relative">
    <!-- 近期新低角标 -->
    <div v-if="product.is_price_lowest" class="absolute top-0 right-0 z-10">
      <div class="bg-green-500 text-white text-xs font-bold px-2 py-1 rounded-bl-lg">
        🔥 近期新低
      </div>
    </div>

    <!-- Cover Image -->
    <div class="relative aspect-square bg-gray-100">
      <img
        :src="product.cover_image || '/gold.svg'"
        :alt="product.title"
        class="w-full h-full object-cover"
        @error="handleImageError"
      />
      <!-- Platform Badge -->
      <span
        :class="[
          'absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-medium',
          product.platform === 'JD'
            ? 'bg-red-500 text-white'
            : 'bg-orange-500 text-white'
        ]"
      >
        {{ product.platform === 'JD' ? '京东' : '淘宝' }}
      </span>

      <!-- 折扣率角标 -->
      <div v-if="product.discount_rate > 0" class="absolute bottom-2 right-2">
        <span class="bg-red-600 text-white text-sm font-bold px-2 py-1 rounded-lg shadow">
          -{{ (product.discount_rate * 100).toFixed(0) }}%
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="p-4">
      <!-- Title -->
      <h3 class="text-sm font-medium text-gray-900 line-clamp-2 mb-2 h-10">
        {{ product.title }}
      </h3>

      <!-- 多维度指标区域 -->
      <div class="space-y-2 mb-3">
        <!-- 折扣率 - 高亮显示 -->
        <div v-if="product.discount_rate > 0" class="flex items-center justify-between">
          <span class="text-xs text-gray-500">折扣力度</span>
          <span :class="discountRateClass">
            {{ (product.discount_rate * 100).toFixed(1) }}% OFF
          </span>
        </div>

        <!-- 降价金额 -->
        <div v-if="product.discount_amount > 0" class="flex items-center justify-between">
          <span class="text-xs text-gray-500">立省</span>
          <span class="text-sm font-semibold text-orange-600">¥{{ product.discount_amount.toFixed(0) }}</span>
        </div>

        <!-- 优惠券 -->
        <div v-if="product.coupon_amount > 0" class="flex items-center justify-between">
          <span class="text-xs text-gray-500">优惠券</span>
          <span class="px-2 py-0.5 bg-red-100 text-red-600 text-xs font-bold rounded border border-red-200">
            券¥{{ product.coupon_amount.toFixed(0) }}
          </span>
        </div>

        <!-- 月销量 -->
        <div v-if="product.monthly_sales > 0" class="flex items-center justify-between">
          <span class="text-xs text-gray-500">月销</span>
          <span class="text-xs text-gray-600">{{ formatSales(product.monthly_sales) }}</span>
        </div>

        <!-- 克重 & 克价（如果有） -->
        <div v-if="product.weight_grams > 0" class="flex items-center justify-between">
          <span class="text-xs text-gray-500">{{ product.weight_grams.toFixed(2) }}克</span>
          <span class="text-xs text-gray-600">¥{{ product.price_per_gram.toFixed(2) }}/克</span>
        </div>
      </div>

      <!-- Price Info -->
      <div class="space-y-1">
        <!-- Original Price -->
        <div v-if="product.original_price && product.original_price !== product.final_price" class="text-xs text-gray-400 line-through">
          原价 ¥{{ product.original_price.toFixed(0) }}
        </div>

        <!-- Final Price - 核心高亮区 -->
        <div :class="highlightClass">
          <div class="flex items-baseline justify-center space-x-1">
            <span class="text-xs">¥</span>
            <span class="text-2xl font-bold">{{ product.final_price.toFixed(0) }}</span>
            <span class="text-xs">到手价</span>
          </div>
          <div v-if="highlightSubtext" class="text-xs mt-0.5 opacity-80">
            {{ highlightSubtext }}
          </div>
        </div>
      </div>

      <!-- Discount Tags -->
      <div v-if="discountTags.length > 0" class="flex flex-wrap gap-1 mt-3">
        <span
          v-for="(tag, index) in discountTags.slice(0, 2)"
          :key="index"
          class="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded"
        >
          {{ tag }}
        </span>
      </div>

      <!-- Buy Button -->
      <a
        :href="buyLink"
        target="_blank"
        rel="noopener noreferrer"
        class="mt-4 block w-full text-center bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-medium py-2.5 rounded-lg transition-all"
      >
        领券购买
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  product: {
    type: Object,
    required: true,
  },
  sortBy: {
    type: String,
    default: 'discount_rate',
  },
})

// Parse discount tags
const discountTags = computed(() => {
  if (!props.product.discount_tags) return []
  try {
    return JSON.parse(props.product.discount_tags)
  } catch {
    return []
  }
})

// 折扣率样式 - 折扣越大颜色越深
const discountRateClass = computed(() => {
  const rate = props.product.discount_rate
  if (rate >= 0.15) return 'text-sm font-bold text-red-600'
  if (rate >= 0.08) return 'text-sm font-semibold text-orange-600'
  return 'text-sm font-medium text-yellow-600'
})

// 核心高亮区样式 - 根据当前排序维度变化
const highlightClass = computed(() => {
  const base = 'rounded-lg px-3 py-2 text-center'
  if (props.product.is_price_lowest) {
    return `${base} bg-green-50 text-green-700`
  }
  if (props.sortBy === 'discount_rate' && props.product.discount_rate >= 0.1) {
    return `${base} bg-red-50 text-red-700`
  }
  return `${base} bg-amber-50 text-gray-900`
})

// 高亮区副文本
const highlightSubtext = computed(() => {
  if (props.product.is_price_lowest) return '📉 30天内最低价'
  if (props.product.discount_rate >= 0.1) return `相当于 ${((1 - props.product.discount_rate) * 10).toFixed(1)} 折`
  return ''
})

// 格式化销量
function formatSales(sales) {
  if (sales >= 10000) return `${(sales / 10000).toFixed(1)}万+`
  if (sales >= 1000) return `${(sales / 1000).toFixed(1)}千+`
  return `${sales}件`
}

// 生成购买链接：优先使用推广链接，fallback 到平台搜索
const buyLink = computed(() => {
  if (props.product.affiliate_url) {
    return props.product.affiliate_url
  }
  // fallback: 根据平台跳转对应搜索页
  const title = encodeURIComponent(props.product.title)
  if (props.product.platform === 'JD') {
    return `https://search.jd.com/Search?keyword=${title}`
  }
  return `https://s.taobao.com/search?q=${title}`
})

// Handle image load error
function handleImageError(e) {
  e.target.src = '/gold.svg'
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
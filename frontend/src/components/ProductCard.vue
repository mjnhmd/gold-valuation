<template>
  <div class="product-card bg-white rounded-xl shadow-sm overflow-hidden">
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
    </div>

    <!-- Content -->
    <div class="p-4">
      <!-- Title -->
      <h3 class="text-sm font-medium text-gray-900 line-clamp-2 mb-2 h-10">
        {{ product.title }}
      </h3>

      <!-- Weight -->
      <div class="flex items-center text-sm text-gray-500 mb-2">
        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
        </svg>
        <span>{{ product.weight_grams.toFixed(2) }}克</span>
      </div>

      <!-- Price Info -->
      <div class="space-y-1">
        <!-- Original Price -->
        <div v-if="product.original_price && product.original_price !== product.final_price" class="text-xs text-gray-400 line-through">
          原价 ¥{{ product.original_price.toFixed(0) }}
        </div>

        <!-- Final Price -->
        <div class="flex items-baseline justify-between">
          <div>
            <span class="text-lg font-bold text-gray-900">¥{{ product.final_price.toFixed(0) }}</span>
            <span class="text-xs text-gray-500 ml-1">到手价</span>
          </div>
        </div>

        <!-- Price Per Gram - Highlighted -->
        <div class="bg-red-50 rounded-lg px-3 py-2 text-center">
          <span class="text-2xl font-bold text-red-600">¥{{ product.price_per_gram.toFixed(2) }}</span>
          <span class="text-sm text-red-500">/克</span>
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
        :href="product.affiliate_url"
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

<script setup>
import { computed, ref, watch } from 'vue'

// Обложка: сразу размытая миниатюра Discogs 150 px (~3 КБ, приходит быстро), поверх неё — обложка 600 px,
// которая проявляется, когда догрузится. Если Discogs не отдал обложку (Cloudflare в РФ), — фото из магазина.
const props = defineProps({
  full: String, // обложка 600 px
  thumb: String, // миниатюра 150 px
  fallback: String, // фото из магазина
  alt: { type: String, default: '' },
  // первые карточки на экране грузим сразу и с высоким приоритетом, остальные — по мере прокрутки
  eager: Boolean,
})

const failed = ref(false)
const loaded = ref(false)
watch(
  () => [props.full, props.fallback],
  () => {
    failed.value = false
    loaded.value = false
  },
)

const src = computed(() => (failed.value || !props.full ? props.fallback : props.full))
const preview = computed(() => (!failed.value && props.thumb && props.thumb !== src.value ? props.thumb : null))

function onError() {
  if (!failed.value && props.fallback && props.fallback !== props.full) failed.value = true
}
</script>

<template>
  <div class="cover-stack">
    <img
      v-if="preview"
      class="cover-thumb"
      :src="preview"
      alt=""
      aria-hidden="true"
      :loading="eager ? 'eager' : 'lazy'"
      referrerpolicy="no-referrer"
    />
    <img
      v-if="src"
      class="cover-full"
      :class="{ loaded }"
      :src="src"
      :alt="alt"
      :loading="eager ? 'eager' : 'lazy'"
      :fetchpriority="eager ? 'high' : 'auto'"
      decoding="async"
      referrerpolicy="no-referrer"
      @load="loaded = true"
      @error="onError"
    />
    <div v-else class="cover-placeholder" aria-hidden="true"></div>
  </div>
</template>

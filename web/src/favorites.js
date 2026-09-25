import { computed, reactive, watch } from 'vue'

// Избранное без регистрации: список альбомов в localStorage этого браузера.
const KEY = 'groove:favorites'

function load() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

const state = reactive({ items: load() })

watch(
  () => state.items,
  (items) => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items))
    } catch {
      /* приватный режим или переполнение — избранное просто не сохранится */
    }
  },
  { deep: true },
)

// Синхронизация между вкладками
window.addEventListener('storage', (event) => {
  if (event.key === KEY) state.items = load()
})

export const favorites = computed(() => state.items)
export const favoritesCount = computed(() => state.items.length)

export function isFavorite(id) {
  return state.items.some((item) => item.id === Number(id))
}

export function toggleFavorite(album) {
  const id = Number(album.id)
  const index = state.items.findIndex((item) => item.id === id)
  if (index >= 0) {
    state.items.splice(index, 1)
  } else {
    // Снимок нужен, чтобы список рисовался сразу, даже если альбом пропал из продажи
    state.items.unshift({ id, a: album.a, t: album.t, c: album.c, s: album.s, p: album.p, added: Date.now() })
  }
}

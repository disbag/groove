const priceFormat = new Intl.NumberFormat('ru-RU')

export const formatPrice = (value) => (value == null ? '—' : `${priceFormat.format(value)} ₽`)

export function plural(n, one, few, many) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

export const shopsLabel = (n) => `${n} ${plural(n, 'магазин', 'магазина', 'магазинов')}`

export const COLOR_LABELS = {
  black: 'Чёрный',
  coloured: 'Цветной',
  splatter: 'Сплэттер',
  clear: 'Прозрачный',
  picture: 'Picture disc',
}

export const SORTS = [
  { value: 'new', label: 'Новые поступления' },
  { value: 'price', label: 'Сначала дешёвые' },
  { value: 'az', label: 'По алфавиту' },
]

export function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ru-RU', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  })
}

// Для поиска: без регистра, ё = е, без пунктуации
export const normalize = (text) =>
  (text || '').toLowerCase().replace(/ё/g, 'е').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim()

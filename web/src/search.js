import { getSearchIndex } from './api.js'
import { normalize } from './format.js'

// Индекс поиска (search.json) грузится один раз за сессию — при первом фокусе в поле или на странице поиска.
let index = null

export async function loadSearchIndex() {
  if (!index) {
    index = getSearchIndex()
      .then((rows) => rows.map(([id, label, year, price]) => ({ id, label, year, price, key: normalize(label) })))
      .catch((error) => {
        index = null
        throw error
      })
  }
  return index
}

// Все альбомы, в «исполнитель — альбом» которых есть каждое слово запроса (в любом порядке).
export function findAlbums(rows, query) {
  const words = normalize(query).split(' ').filter(Boolean)
  if (!rows || !words.length) return []
  return rows.filter((row) => words.every((w) => row.key.includes(w)))
}

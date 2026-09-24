// Данные — статические JSON, которые ночной конвейер кладёт в ./data/.
const base = `${import.meta.env.BASE_URL}data/`
const cache = new Map()

async function getJSON(path) {
  if (!cache.has(path)) {
    const request = fetch(base + path).then((response) => {
      if (!response.ok) throw new Error(`${response.status} ${path}`)
      return response.json()
    })
    cache.set(path, request)
    request.catch(() => cache.delete(path))
  }
  return cache.get(path)
}

export const getMeta = () => getJSON('meta.json')
export const getCatalogPage = (genre, sort, page) => getJSON(`catalog/${genre}/${sort}/${page}.json`)
export const getAlbum = (id) => getJSON(`card/${id}.json`)
export const getSearchIndex = () => getJSON('search.json')

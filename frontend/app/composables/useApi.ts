export function useApi() {
  return $fetch.create({ baseURL: '/api/v1', retry: 0 })
}

import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const client = axios.create({ baseURL: API_URL })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// If the token is invalid/expired, boot the user back to login rather than
// showing a confusing half-broken dashboard.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_id')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client

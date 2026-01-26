/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  distDir: 'out',
  images: {
    unoptimized: true,
  },
  // during development, proxy OAI calls to the backend at localhost:8000
  async rewrites() {
    return [
      // forward any /oai and /stats requests to backend
      { source: '/oai', destination: 'http://localhost:8000/oai' },
      { source: '/oai/:path*', destination: 'http://localhost:8000/oai/:path*' },
      { source: '/stats', destination: 'http://localhost:8000/stats' },
    ]
  },
}

module.exports = nextConfig

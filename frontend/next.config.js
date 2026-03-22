/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  // proxy OAI and stats requests to the backend
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    return [
      { source: '/oai', destination: `${backendUrl}/oai` },
      { source: '/oai/:path*', destination: `${backendUrl}/oai/:path*` },
      { source: '/stats', destination: `${backendUrl}/stats` },
    ]
  },
}

module.exports = nextConfig

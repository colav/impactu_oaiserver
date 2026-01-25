/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // export as a static site for simple serving from the backend
  output: 'export',
  // during development, proxy OAI calls to the backend at localhost:8000
  async rewrites() {
    return [
      // forward any /oai requests to backend
      { source: '/oai', destination: 'http://localhost:8000/oai' },
      { source: '/oai/:path*', destination: 'http://localhost:8000/oai/:path*' },
    ]
  },
}

module.exports = nextConfig

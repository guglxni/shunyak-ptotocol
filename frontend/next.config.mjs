/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typedRoutes: true,
  async rewrites() {
    const localApiOrigin = process.env.SHUNYAK_LOCAL_API_ORIGIN;
    if (!localApiOrigin) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${localApiOrigin}/api/:path*`
      }
    ];
  }
};

export default nextConfig;

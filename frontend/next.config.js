/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit .next/standalone: a self-contained server plus only the node_modules
  // it actually imports. It is what keeps the runtime image small and lets it
  // run without npm or a node_modules tree copied in.
  output: "standalone",
};

module.exports = nextConfig;

/**
 * Run `build` or `dev` with `SKIP_ENV_VALIDATION` to skip env validation. This is especially useful
 * for Docker builds.
 */
import "./src/env.js";

function getInternalServiceURL(envKey, fallbackURL) {
  const configured = process.env[envKey]?.trim();
  return configured && configured.length > 0
    ? configured.replace(/\/+$/, "")
    : fallbackURL;
}
import nextra from "nextra";

const withNextra = nextra({});

/** @type {import("next").NextConfig} */
const config = {
  output: "standalone",
  i18n: {
    locales: ["en", "zh"],
    defaultLocale: "en",
  },
  devIndicators: false,
  productionBrowserSourceMaps: false,
  async rewrites() {
    const gatewayURL = getInternalServiceURL(
      "DEER_FLOW_INTERNAL_GATEWAY_BASE_URL",
      "http://127.0.0.1:8001",
    );

    return {
      beforeFiles: [
        {
          source: "/",
          destination: "/ads-login",
        },
        {
          source: "/login",
          destination: "/ads-login",
        },
        {
          source: "/login/:path*",
          destination: "/ads-login/:path*",
        },
      ],
      afterFiles: [
        ...(!process.env.NEXT_PUBLIC_LANGGRAPH_BASE_URL
          ? [
              {
                source: "/api/langgraph",
                destination: `${gatewayURL}/api`,
              },
              {
                source: "/api/langgraph/:path*",
                destination: `${gatewayURL}/api/:path*`,
              },
            ]
          : []),
        ...(!process.env.NEXT_PUBLIC_BACKEND_BASE_URL
          ? [
              {
                source: "/api/agents",
                destination: `${gatewayURL}/api/agents`,
              },
              {
                source: "/api/agents/:path*",
                destination: `${gatewayURL}/api/agents/:path*`,
              },
              {
                source: "/api/skills",
                destination: `${gatewayURL}/api/skills`,
              },
              {
                source: "/api/skills/:path*",
                destination: `${gatewayURL}/api/skills/:path*`,
              },
              {
                source: "/api/:path*",
                destination: `${gatewayURL}/api/:path*`,
              },
            ]
          : []),
      ],
      fallback: [],
    };
  },
};

export default withNextra(config);

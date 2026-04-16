import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        fog: "var(--fog)",
        moss: "var(--moss)",
        ember: "var(--ember)",
        ocean: "var(--ocean)",
        paper: "var(--paper)"
      },
      boxShadow: {
        panel: "0 10px 40px rgba(0, 0, 0, 0.35)",
        glow: "0 0 0 1px rgba(120, 255, 187, 0.25), 0 0 24px rgba(120, 255, 187, 0.15)"
      }
    }
  },
  plugins: []
};

export default config;

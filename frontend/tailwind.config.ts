import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        page: "#F5F4F1",
        surface: "#FFFFFF",
        subtle: "#F0EEE9",
        border: "#D8D5CE",
        strong: "#B8B4AC",
        primary: "#1A1916",
        secondary: "#5C5A55",
        muted: "#8C8A84",
        accent: "#0B6E4F",
        accentLight: "#E8F5F0",
        red: "#C0392B",
        amber: "#B07D1A"
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"]
      },
      fontSize: {
        xs: "11px",
        sm: "12px",
        base: "13px",
        md: "14px",
        lg: "16px",
        xl: "20px"
      }
    }
  },
  plugins: []
};

export default config;

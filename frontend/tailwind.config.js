/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        encre: "#241c16",
        papier: "#f3efe6",
        carte: "#fffaf3",
        filet: "#e4d9c8",
        pin: "#0f6e56",
        brique: "#8f3d2b",
      },
      fontFamily: {
        serif: ["Georgia", "Iowan Old Style", "Palatino Linotype", "Palatino", "serif"],
        sans: ["Segoe UI", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

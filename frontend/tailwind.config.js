/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090d16",
        surface: "#101625",
        card: "#172033",
        border: "#263554",
        primary: "#3b82f6",
        accent: "#6366f1",
      }
    },
  },
  plugins: [],
}

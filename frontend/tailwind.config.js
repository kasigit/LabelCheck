/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Status colors defined once and used everywhere via tokens. Chosen to meet WCAG AA
      // (4.5:1) against white for the text shades; the amber is darkened for that reason.
      colors: {
        status: {
          match: "#15803d", // green-700
          review: "#b45309", // amber-700 (darkened so text passes AA)
          mismatch: "#b91c1c", // red-700
          missing: "#4b5563", // gray-600
        },
      },
      fontSize: {
        // Base 18px per the accessibility rules; results text larger.
        base: ["1.125rem", { lineHeight: "1.6rem" }],
      },
    },
  },
  plugins: [],
};

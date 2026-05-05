/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#faf5ff",
          100: "#f3e8ff",
          200: "#e9d5ff",
          300: "#d8b4fe",
          400: "#c084fc",
          500: "#a855f7",
          600: "#9333ea",
          700: "#7e22ce",
        },
        "glass-border": "rgba(255,255,255,0.6)",
        "glass-border-soft": "rgba(255,255,255,0.35)",
      },
      backgroundImage: {
        "app-gradient":
          "linear-gradient(135deg, #d4f5e0 0%, #d8ecfa 35%, #e7e3fb 65%, #fbe1ec 100%)",
        "btn-purple": "linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)",
        "btn-rainbow":
          "linear-gradient(135deg, #86efac 0%, #93c5fd 35%, #c4b5fd 65%, #fda4af 100%)",
        "glass-sheen":
          "linear-gradient(135deg, rgba(255,255,255,0.78) 0%, rgba(255,255,255,0.58) 50%, rgba(255,255,255,0.68) 100%)",
        "glass-sheen-strong":
          "linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.74) 50%, rgba(255,255,255,0.84) 100%)",
        "glass-highlight":
          "linear-gradient(180deg, rgba(255,255,255,0.7) 0%, rgba(255,255,255,0) 40%)",
      },
      boxShadow: {
        soft: "0 4px 20px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -1px rgba(15, 23, 42, 0.04)",
        card: "0 8px 30px -6px rgba(15, 23, 42, 0.08), 0 4px 10px -2px rgba(15, 23, 42, 0.04)",
        glass:
          "0 8px 32px -4px rgba(124, 58, 237, 0.10), 0 2px 8px -2px rgba(15,23,42,0.05), inset 0 1px 0 0 rgba(255,255,255,0.6)",
        "glass-lg":
          "0 20px 48px -8px rgba(124, 58, 237, 0.14), 0 4px 16px -4px rgba(15,23,42,0.06), inset 0 1px 0 0 rgba(255,255,255,0.7)",
        "glass-inset":
          "inset 0 1px 0 0 rgba(255,255,255,0.6), inset 0 -1px 0 0 rgba(15,23,42,0.04)",
      },
      backdropBlur: {
        glass: "14px",
        "glass-strong": "22px",
      },
      keyframes: {
        wave: {
          "0%, 100%": { transform: "scaleY(0.25)" },
          "50%": { transform: "scaleY(1)" },
        },
      },
      animation: {
        "wave-1": "wave 1s ease-in-out infinite 0s",
        "wave-2": "wave 1s ease-in-out infinite 0.15s",
        "wave-3": "wave 1s ease-in-out infinite 0.3s",
        "wave-4": "wave 1s ease-in-out infinite 0.45s",
        "wave-5": "wave 1s ease-in-out infinite 0.6s",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#0B0B0D",
        foreground: "#F8F9FA",
        accent: {
          DEFAULT: "#2DD4BF",
          foreground: "#0B0B0D",
        },
        muted: {
          DEFAULT: "#1A1B23",
          foreground: "#9CA3AF",
        },
        border: "#2A2B35",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        DEFAULT: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        "2xl": "2rem",
      },
      typography: () => ({
        invert: {
          css: {
            "--tw-prose-body": "#d1d5db",
            "--tw-prose-headings": "#F8F9FA",
            "--tw-prose-links": "#2DD4BF",
            "--tw-prose-bold": "#F8F9FA",
            "--tw-prose-code": "#2DD4BF",
            "--tw-prose-pre-bg": "#12141C",
            "--tw-prose-pre-code": "#e5e7eb",
            "--tw-prose-th-borders": "#2A2B35",
            "--tw-prose-td-borders": "#2A2B35",
            "--tw-prose-quote-borders": "#2DD4BF",
            "--tw-prose-quotes": "#9CA3AF",
            "--tw-prose-hr": "#2A2B35",
            maxWidth: "none",
            h1: { fontWeight: 700, letterSpacing: "-0.02em" },
            h2: { fontWeight: 600, letterSpacing: "-0.01em" },
            h3: { fontWeight: 600 },
            "h1, h2, h3, h4": { scrollMarginTop: "2rem" },
            pre: {
              backgroundColor: "#12141C",
              borderRadius: "0.75rem",
              border: "1px solid #2A2B35",
              overflowX: "auto",
            },
            "pre code": {
              backgroundColor: "transparent",
              border: "none",
              fontSize: "0.875rem",
              fontWeight: 400,
            },
            code: {
              backgroundColor: "#1A1B23",
              borderRadius: "0.375rem",
              padding: "0.125rem 0.375rem",
              fontWeight: 400,
              fontSize: "0.875rem",
            },
            "code::before": { content: '""' },
            "code::after": { content: '""' },
            table: {
              borderCollapse: "collapse",
              width: "100%",
              fontSize: "0.875rem",
            },
            "thead th": {
              backgroundColor: "#1A1B23",
              fontWeight: 600,
              textAlign: "left",
              padding: "0.5rem 0.75rem",
              borderBottom: "2px solid #2A2B35",
            },
            "tbody td": {
              padding: "0.5rem 0.75rem",
              borderBottom: "1px solid #2A2B35",
            },
            "tbody tr:last-child td": { borderBottom: "none" },
            "ul, ol": { paddingLeft: "1.5rem" },
            "li > p": { margin: 0 },
          },
        },
      }),
    },
  },
  plugins: [typography],
};

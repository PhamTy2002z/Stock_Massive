/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['var(--font-jetbrains-mono)', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // The reference's own steps, all derived from a 15px body. Named rather
        // than written as arbitrary values so a card eyebrow is the same size
        // in every card.
        'eyebrow': ['0.7rem', { lineHeight: '1rem', letterSpacing: '0.08em' }],
        'micro': ['0.74rem', { lineHeight: '1.05rem' }],
        'meta': ['0.8rem', { lineHeight: '1.15rem' }],
        'control': ['0.86rem', { lineHeight: '1.25rem' }],
        'row': ['0.9rem', { lineHeight: '1.3rem' }],
      },
      keyframes: {
        'auth-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'auth-tape': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        'auth-up': 'auth-up 400ms ease-out both',
        'auth-tape': 'auth-tape 24s linear infinite',
      },
      transitionTimingFunction: {
        // The reference animates every panel with the same curve: a fast start
        // that settles rather than eases evenly, which is what makes the
        // sidebar and the inspector feel like one mechanism.
        'sidebar': 'cubic-bezier(0.22, 1, 0.28, 1)',
        'panel': 'cubic-bezier(0.22, 1, 0.28, 1)',
      },
      transitionDuration: {
        'panel': '340ms',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        // Cards are 14px in the reference and controls are 8–11px; the composer
        // is the one 18px surface, and pills are fully round.
        card: '14px',
        composer: '18px',
        pill: '99px',
      },
      boxShadow: {
        // Menus float on a near-black ground, so they separate by shadow rather
        // than by border alone.
        menu: '0 26px 60px rgba(0, 0, 0, 0.65)',
        composer: '0 20px 50px rgba(0, 0, 0, 0.45)',
        panel: '-30px 0 70px rgba(0, 0, 0, 0.5)',
        modal: '0 40px 90px rgba(0, 0, 0, 0.7)',
      },
      colors: {
        auth: {
          background: '#141619',
          surface: '#1f2225',
          'surface-muted': '#181b1e',
          ink: '#0b0d0f',
          muted: '#596273',
          border: '#d8dde4',
          orange: '#ff6500',
          up: '#00bd7a',
          down: '#f02237',
        },
        // The surface ladder. Six steps, each one a few percent of luminance
        // off the one below it — the design separates planes by tone, not by
        // rules, so a component picks a step instead of drawing a border.
        surface: {
          DEFAULT: 'hsl(var(--surface-ground))',
          ground: 'hsl(var(--surface-ground))',
          panel: 'hsl(var(--surface-panel))',
          raised: 'hsl(var(--surface-raised))',
          sunken: 'hsl(var(--surface-sunken))',
          menu: 'hsl(var(--surface-menu))',
          bubble: 'hsl(var(--surface-bubble))',
        },
        // The ink ladder. `ink-1` is body copy and `ink-6` is the quietest
        // label the design allows; nothing sits below it.
        ink: {
          1: 'hsl(var(--ink-1))',
          2: 'hsl(var(--ink-2))',
          3: 'hsl(var(--ink-3))',
          4: 'hsl(var(--ink-4))',
          5: 'hsl(var(--ink-5))',
          6: 'hsl(var(--ink-6))',
        },
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        positive: 'hsl(var(--positive))',
        negative: 'hsl(var(--negative))',
        hairline: 'hsl(var(--hairline))',
        interactive: {
          DEFAULT: 'hsl(var(--interactive))',
          strong: 'hsl(var(--interactive-strong))',
        },
        nav: {
          DEFAULT: 'hsl(var(--nav))',
          foreground: 'hsl(var(--nav-foreground))',
        },
        ceiling: 'hsl(var(--ceiling))',
        reference: 'hsl(var(--reference))',
        floor: 'hsl(var(--floor))',
        caution: 'hsl(var(--caution))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          '1': 'hsl(var(--chart-1))',
          '2': 'hsl(var(--chart-2))',
          '3': 'hsl(var(--chart-3))',
          '4': 'hsl(var(--chart-4))',
          '5': 'hsl(var(--chart-5))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

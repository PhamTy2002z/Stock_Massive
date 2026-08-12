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
  			'sidebar': 'cubic-bezier(0.32, 0.72, 0, 1)',
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
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
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			positive: 'hsl(var(--positive))',
  			negative: 'hsl(var(--negative))',
  			hairline: 'hsl(var(--hairline))',
  			interactive: {
  				DEFAULT: 'hsl(var(--interactive))',
  				strong: 'hsl(var(--interactive-strong))'
  			},
  			nav: {
  				DEFAULT: 'hsl(var(--nav))',
  				foreground: 'hsl(var(--nav-foreground))'
  			},
  			ceiling: 'hsl(var(--ceiling))',
  			reference: 'hsl(var(--reference))',
  			floor: 'hsl(var(--floor))',
  			caution: 'hsl(var(--caution))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			}
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};

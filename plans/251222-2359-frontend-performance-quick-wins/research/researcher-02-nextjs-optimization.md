# Next.js Performance Optimization Research

## 1. Dynamic Imports with `next/dynamic`

### Basic Syntax
```tsx
import dynamic from 'next/dynamic'

// Simple dynamic import
const Component = dynamic(() => import('../components/Component'))

// With loading fallback
const ComponentWithLoading = dynamic(
  () => import('../components/Component'),
  { loading: () => <p>Loading...</p> }
)

// Client-only (no SSR)
const ClientOnlyComponent = dynamic(
  () => import('../components/Component'),
  { ssr: false }
)
```

### Named Exports
```tsx
const Hello = dynamic(() =>
  import('../components/hello').then((mod) => mod.Hello)
)
```

### Key Options
| Option | Type | Description |
|--------|------|-------------|
| `ssr` | boolean | Disable server-side rendering (default: true) |
| `loading` | function | Custom loading component |

## 2. Code Splitting Strategies for Heavy Components

### Charts/Editors Pattern
```tsx
// Dashboard with heavy chart - load client-only
const Chart = dynamic(() => import('@/components/chart'), {
  ssr: false,
  loading: () => <div className="h-[400px] animate-pulse bg-muted" />,
})
```

### On-Demand Loading
```tsx
const [showEditor, setShowEditor] = useState(false)
const Editor = dynamic(() => import('../components/Editor'))

// Only loads when condition met
{showEditor && <Editor />}
```

### Dynamic Library Import (Event-Based)
```tsx
const handleSearch = async (value: string) => {
  const Fuse = (await import('fuse.js')).default
  const fuse = new Fuse(data)
  setResults(fuse.search(value))
}
```

## 3. Bundle Analysis & Optimization

### Setup Bundle Analyzer
```bash
npm i @next/bundle-analyzer
```

```js
// next.config.js
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})
module.exports = withBundleAnalyzer(nextConfig)
```

### Run Analysis
```bash
ANALYZE=true npm run build
# or with Turbopack
npx next experimental-analyze
```

### Optimize Package Imports
```js
// next.config.js - tree-shake large packages
module.exports = {
  experimental: {
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
  },
}
```

## 4. `next/image` vs Regular `<img>`

| Feature | `next/image` | `<img>` |
|---------|--------------|---------|
| Auto optimization | Yes (WebP/AVIF) | No |
| Lazy loading | Built-in | Manual |
| Responsive sizes | Automatic | Manual |
| CLS prevention | Yes (placeholder) | No |
| CDN caching | Yes | Depends |

### Basic Usage
```tsx
import Image from 'next/image'

<Image
  src="/hero.jpg"
  alt="Hero"
  width={800}
  height={400}
  priority  // for LCP images
/>
```

### Skip Optimization (SVG/small images)
```tsx
<Image src="/icon.svg" alt="" unoptimized />
```

## Quick Wins Summary

1. **Dynamic import charts/editors** with `ssr: false`
2. **Add loading skeletons** to dynamic imports
3. **Run bundle analyzer** to identify large deps
4. **Use `optimizePackageImports`** for icon libraries
5. **Replace `<img>` with `next/image`** for automatic optimization
6. **Add `priority`** to above-fold images (LCP)
7. **Lazy load libraries** on user interaction (search, modals)

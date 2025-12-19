# Next.js 14 App Router SSR & Server Components Patterns

## 1. Server Components vs Client Components

### When to Use Server Components (Default)
- Data fetching from DB/API
- Access backend resources directly
- Keep sensitive info (API keys, tokens) on server
- Large dependencies that should stay server-side
- No interactivity needed

### When to Use Client Components
- Interactivity: `useState`, `useEffect`, event handlers
- Browser APIs: `localStorage`, `window`, `navigator`
- Custom hooks with state/effects
- Third-party libs requiring browser context

### Decision Matrix
| Need | Component Type |
|------|---------------|
| Fetch data | Server |
| onClick/onChange | Client |
| useState/useReducer | Client |
| Direct DB access | Server |
| SEO-critical content | Server |
| Real-time updates | Client |

---

## 2. Data Fetching in Server Components

### Basic async/await Pattern
```tsx
// Server Component - async by default
export default async function Page() {
  const data = await fetch('https://api.example.com/posts')
  const posts = await data.json()

  return (
    <ul>
      {posts.map((post) => (
        <li key={post.id}>{post.title}</li>
      ))}
    </ul>
  )
}
```

### Direct DB/ORM Access
```tsx
import { db, posts } from '@/lib/db'

export default async function Page() {
  const allPosts = await db.select().from(posts)
  return <PostList posts={allPosts} />
}
```

### Dynamic Data (No Cache)
```tsx
async function getData() {
  const res = await fetch('https://...', { cache: 'no-store' })
  return res.json()
}
```

---

## 3. Streaming with Suspense Boundaries

### Granular Streaming Pattern
```tsx
import { Suspense } from 'react'

export default function Page() {
  return (
    <div>
      {/* Sent immediately */}
      <header><h1>Dashboard</h1></header>

      {/* Streams when ready */}
      <Suspense fallback={<PostsSkeleton />}>
        <Posts />
      </Suspense>

      <Suspense fallback={<StatsSkeleton />}>
        <Stats />
      </Suspense>
    </div>
  )
}
```

### Sequential Data with Suspense
```tsx
export default async function Page({ params }) {
  const { id } = await params
  const artist = await getArtist(id)

  return (
    <>
      <h1>{artist.name}</h1>
      <Suspense fallback={<div>Loading playlists...</div>}>
        <Playlists artistID={artist.id} />
      </Suspense>
    </>
  )
}

async function Playlists({ artistID }) {
  const playlists = await getArtistPlaylists(artistID)
  return <ul>{playlists.map(p => <li key={p.id}>{p.name}</li>)}</ul>
}
```

---

## 4. "use client" Directive Best Practices

### Correct Usage
```tsx
'use client'  // Must be FIRST line, before imports

import { useState } from 'react'

export default function Counter() {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}
```

### Best Practices
1. Place `'use client'` at component boundary, not at top of tree
2. Keep client components small - push interactivity to leaves
3. Wrap third-party client-only libs in client component wrapper:

```tsx
// components/carousel.tsx
'use client'
import { Carousel } from 'acme-carousel'
export default Carousel
```

4. Server Components can import Client Components (not vice versa)

---

## 5. Passing Server Data to Client Components

### Props Serialization (Recommended)
```tsx
// Server Component
import LikeButton from '@/components/LikeButton'
import { getPost } from '@/lib/data'

export default async function Page({ params }) {
  const post = await getPost(params.id)
  return <LikeButton likes={post.likes} />  // Serializable prop
}

// Client Component
'use client'
export default function LikeButton({ likes }: { likes: number }) {
  const [count, setCount] = useState(likes)
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}
```

### Streaming Promise to Client (React `use` hook)
```tsx
// Server Component
export default function Page() {
  const postsPromise = getPosts()  // Don't await
  return (
    <Suspense fallback={<Loading />}>
      <Posts posts={postsPromise} />
    </Suspense>
  )
}

// Client Component
'use client'
import { use } from 'react'

export default function Posts({ posts }) {
  const allPosts = use(posts)  // Resolves promise
  return <ul>{allPosts.map(p => <li key={p.id}>{p.title}</li>)}</ul>
}
```

### Non-Serializable Props - AVOID
```tsx
// ❌ WRONG - Functions not serializable
<ClientComponent onClick={() => {}} />

// ✅ CORRECT - Define handler in client component
'use client'
export default function ClientComponent() {
  const handleClick = () => {}
  return <button onClick={handleClick}>Click</button>
}
```

---

## 6. loading.tsx and error.tsx Conventions

### loading.tsx - Route-level Loading UI
```tsx
// app/dashboard/loading.tsx
export default function Loading() {
  return <DashboardSkeleton />
}
```
- Auto-wrapped in Suspense boundary
- Shows while page.tsx loads
- Nested: `layout.tsx` > `loading.tsx` > `page.tsx`

### error.tsx - Error Boundary
```tsx
// app/dashboard/error.tsx
'use client'  // Must be client component

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

### not-found.tsx - 404 UI
```tsx
// app/not-found.tsx
import Link from 'next/link'

export default function NotFound() {
  return (
    <div>
      <h2>Not Found</h2>
      <Link href="/">Return Home</Link>
    </div>
  )
}
```

### File Hierarchy
```
app/
├── layout.tsx      # Root layout
├── loading.tsx     # Global loading
├── error.tsx       # Global error boundary
├── not-found.tsx   # 404 page
└── dashboard/
    ├── page.tsx
    ├── loading.tsx # Route-specific loading
    └── error.tsx   # Route-specific error
```

---

## Key Takeaways

1. **Default to Server Components** - only add `'use client'` when needed
2. **Push client boundaries down** - keep interactive parts small
3. **Use Suspense for streaming** - improves perceived performance
4. **Serialize data at boundaries** - only pass JSON-serializable props
5. **Leverage file conventions** - `loading.tsx`/`error.tsx` for automatic UX
6. **Fetch in Server Components** - avoid client-side waterfalls

# TanStack Query v5 + Next.js 14 App Router Integration

## 1. Installation

```bash
npm install @tanstack/react-query
# Optional: DevTools
npm install @tanstack/react-query-devtools
```

## 2. QueryClientProvider Setup (Client Component Wrapper)

Create `app/providers.tsx` - must be client component due to `useContext`:

```tsx
'use client'

import { isServer, QueryClient, QueryClientProvider } from '@tanstack/react-query'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // Prevent immediate refetch after hydration
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

function getQueryClient() {
  if (isServer) {
    return makeQueryClient() // Server: always new client
  } else {
    // Browser: reuse client (important for Suspense)
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}

export default function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient()
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}
```

Wrap in `app/layout.tsx`:

```tsx
import Providers from './providers'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

## 3. SSR Hydration Patterns

### Pattern A: Server Component Prefetch + Client Hydration

**Server Component (page.tsx):**

```tsx
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query'
import Posts from './posts'

export default async function PostsPage() {
  const queryClient = new QueryClient()

  await queryClient.prefetchQuery({
    queryKey: ['posts'],
    queryFn: getPosts,
  })

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Posts />
    </HydrationBoundary>
  )
}
```

**Client Component (posts.tsx):**

```tsx
'use client'

import { useQuery } from '@tanstack/react-query'

export default function Posts() {
  // Data available immediately from hydration
  const { data } = useQuery({
    queryKey: ['posts'],
    queryFn: getPosts,
  })

  // Non-prefetched query - fetches on client
  const { data: comments } = useQuery({
    queryKey: ['comments'],
    queryFn: getComments,
  })

  return <div>{/* render */}</div>
}
```

### Pattern B: Non-blocking Prefetch (no await)

```tsx
export default function PostsPage() {
  const queryClient = getQueryClient()

  // Fire-and-forget prefetch
  void queryClient.prefetchQuery({
    queryKey: ['posts'],
    queryFn: getPosts,
  })

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Posts />
    </HydrationBoundary>
  )
}
```

## 4. Query Keys Best Practices

```tsx
// Simple keys - generic resources
useQuery({ queryKey: ['todos'], queryFn: fetchTodos })

// Hierarchical keys - with variables
useQuery({ queryKey: ['todos', { status: 'done' }], queryFn: fetchTodos })
useQuery({ queryKey: ['todo', todoId], queryFn: () => fetchTodo(todoId) })

// Nested resources
useQuery({ queryKey: ['posts', postId, 'comments'], queryFn: fetchComments })
```

**Query Key Factory Pattern:**

```tsx
export const todoKeys = {
  all: ['todos'] as const,
  lists: () => [...todoKeys.all, 'list'] as const,
  list: (filters: Filters) => [...todoKeys.lists(), filters] as const,
  details: () => [...todoKeys.all, 'detail'] as const,
  detail: (id: number) => [...todoKeys.details(), id] as const,
}

// Usage
useQuery({ queryKey: todoKeys.detail(5), queryFn: () => fetchTodo(5) })
```

## 5. Stale Time Configuration

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,      // 1 min - data considered fresh
      gcTime: 5 * 60 * 1000,     // 5 min - cache garbage collection
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Per-query override
useQuery({
  queryKey: ['static-data'],
  queryFn: fetchStaticData,
  staleTime: Infinity, // Never stale
})
```

## 6. useQuery Patterns

```tsx
'use client'

import { useQuery } from '@tanstack/react-query'

function Component() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['posts'],
    queryFn: async () => {
      const res = await fetch('/api/posts')
      if (!res.ok) throw new Error('Failed')
      return res.json()
    },
    enabled: true,           // Conditional fetching
    staleTime: 5 * 60 * 1000,
    select: (data) => data.filter(p => p.active), // Transform data
  })

  if (isLoading) return <div>Loading...</div>
  if (isError) return <div>Error: {error.message}</div>

  return <div>{/* render data */}</div>
}
```

## 7. useMutation Patterns

```tsx
'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'

function CreatePost() {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (newPost: { title: string }) => {
      const res = await fetch('/api/posts', {
        method: 'POST',
        body: JSON.stringify(newPost),
      })
      return res.json()
    },
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['posts'] })
    },
    onError: (error) => {
      console.error('Mutation failed:', error)
    },
  })

  return (
    <button
      onClick={() => mutation.mutate({ title: 'New Post' })}
      disabled={mutation.isPending}
    >
      {mutation.isPending ? 'Creating...' : 'Create Post'}
    </button>
  )
}
```

**Optimistic Updates:**

```tsx
const mutation = useMutation({
  mutationFn: updateTodo,
  onMutate: async (newTodo) => {
    await queryClient.cancelQueries({ queryKey: ['todos'] })
    const previous = queryClient.getQueryData(['todos'])
    queryClient.setQueryData(['todos'], (old) => [...old, newTodo])
    return { previous }
  },
  onError: (err, newTodo, context) => {
    queryClient.setQueryData(['todos'], context.previous)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] })
  },
})
```

## Key Takeaways

1. **Provider**: Must be client component; use singleton pattern for browser client
2. **SSR**: Use `prefetchQuery` + `dehydrate` + `HydrationBoundary`
3. **staleTime**: Set >0 for SSR to prevent immediate client refetch
4. **Query Keys**: Use arrays, include all dependencies, consider factory pattern
5. **Mixing**: Can mix prefetched + client-only queries in same component
6. **Mutations**: Use `invalidateQueries` for cache sync after mutations

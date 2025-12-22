# React Performance Optimization Patterns

## 1. React.memo Best Practices

### When to Use
- Components receiving same props frequently but parent re-renders often
- Pure presentational components with expensive render logic
- List item components rendered in large lists

### When NOT to Use
- Components that almost always receive different props
- Components with cheap render logic (overhead > benefit)
- Components using context that changes frequently

```jsx
// Good: List item that receives stable props
const ListItem = memo(function ListItem({ item }) {
  return <div>{item.name}</div>;
});

// Bad: Component always gets new object props
<MyComponent data={{ value }} /> // Creates new object every render
```

## 2. useMemo and useCallback Patterns

### useMemo - Cache Expensive Computations
```jsx
const visibleTodos = useMemo(
  () => filterTodos(todos, tab),  // Expensive filter
  [todos, tab]                     // Only recompute when deps change
);
```

### useCallback - Stabilize Function References
```jsx
const handleSubmit = useCallback((orderDetails) => {
  post('/product/' + productId + '/buy', { referrer, orderDetails });
}, [productId, referrer]);
```

### Context Optimization Pattern
```jsx
const contextValue = useMemo(() => ({
  currentUser,
  login  // login should be wrapped in useCallback
}), [currentUser, login]);

return <AuthContext value={contextValue}>{children}</AuthContext>;
```

### Rules
- Always include ALL dependencies (lint will warn)
- Don't overuse - adds complexity and memory overhead
- Profile first, optimize second

## 3. Common Re-render Causes & Fixes

| Cause | Fix |
|-------|-----|
| New object/array literals in props | useMemo or lift to module scope |
| Inline function props | useCallback |
| Context value changes | useMemo context value |
| Parent state changes | memo child components |
| Missing keys in lists | Add stable unique keys |

### Anti-pattern: Inline Objects
```jsx
// BAD - creates new object every render
<List style={{ margin: 10 }} />

// GOOD - stable reference
const listStyle = useMemo(() => ({ margin: 10 }), []);
<List style={listStyle} />
```

## 4. TanStack Query: refetchIntervalInBackground

### What It Does
- `refetchInterval`: Polls data at specified interval (ms)
- `refetchIntervalInBackground: true`: Continues polling even when tab is inactive

### Performance Implications
- **Battery drain**: Background fetches consume resources
- **Network usage**: Unnecessary requests when user not viewing
- **Server load**: Multiplied by inactive tabs across users

### Recommendations
```tsx
// Dynamic interval based on state
const { data } = useQuery({
  queryKey: ['todos'],
  queryFn: fetchTodos,
  refetchInterval: (query) => {
    return query.state.status === 'error' ? 5000 : 30000;
  },
  refetchIntervalInBackground: false, // Default - prefer this
});
```

### When to Enable Background Refetch
- Critical real-time data (stock prices, alerts)
- Short-lived sessions where freshness is paramount
- Never for non-critical dashboard data

### Optimization Tips
- Use `notifyOnChangeProps: []` for prefetch queries to avoid rerenders
- Memoize `placeholderData` to avoid recomputation
- Consider `staleTime` to reduce unnecessary refetches

---

## Unresolved Questions
1. What is the current `refetchIntervalInBackground` usage in the codebase?
2. Are there components with expensive renders that lack memoization?
3. What is the acceptable staleTime for stock data in this application?

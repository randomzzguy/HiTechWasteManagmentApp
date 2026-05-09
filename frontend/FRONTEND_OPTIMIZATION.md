# Frontend Bundle Optimization Guide

This guide covers frontend performance optimizations for the Hi-Tech Waste Management application.

## Current Optimizations

The Next.js configuration includes:

- **SWC Minification**: Fast JavaScript minification
- **Compression**: Gzip compression enabled
- **Image Optimization**: AVIF and WebP formats
- **Modular Imports**: Tree-shaking for lucide icons
- **Standalone Output**: Optimized Docker builds

## Analyzing Bundle Size

### Using Bundle Analyzer

1. Install the analyzer:

```bash
npm install --save-dev @next/bundle-analyzer
```

2. Update `next.config.js` (uncomment the webpack section):

```javascript
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})

module.exports = withBundleAnalyzer(nextConfig)
```

3. Analyze bundle:

```bash
ANALYZE=true npm run build
```

This opens a visualization of your bundle size.

### Manual Bundle Size Check

```bash
npm run build
du -sh .next/static
```

## Optimization Strategies

### 1. Code Splitting

Next.js automatically code-splits by page. Additional strategies:

**Dynamic Imports**

```typescript
// Instead of static import
import { HeavyComponent } from './HeavyComponent'

// Use dynamic import
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <p>Loading...</p>,
  ssr: false, // Disable server-side rendering if not needed
})
```

**Route-Based Splitting**

Each page is automatically split. No additional action needed.

### 2. Image Optimization

**Use Next.js Image Component**

```typescript
import Image from 'next/image'

// Good
<Image 
  src="/logo.png" 
  alt="Logo" 
  width={200} 
  height={100}
  priority // For above-the-fold images
/>

// Avoid
<img src="/logo.png" alt="Logo" />
```

**Optimize Images**

- Use WebP/AVIF formats (automatic in Next.js)
- Compress images before deployment
- Use appropriate dimensions
- Lazy load below-the-fold images

### 3. Font Optimization

**Use next/font**

```typescript
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout() {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  )
}
```

### 4. Icon Optimization

**Use Modular Imports**

The configuration already includes modular imports for lucide icons:

```typescript
// Good - Only imports used icon
import { User, Settings } from 'lucide-react'

// Avoid - Imports entire library
import * as Icons from 'lucide-react'
```

### 5. Third-Party Libraries

**Use Lightweight Alternatives**

| Heavy Library | Lightweight Alternative |
|---------------|------------------------|
| moment.js | date-fns, luxon |
| lodash | lodash-es (tree-shakeable) |
| axios | fetch API |
| react-select | native select or lighter alternative |

**Load Third-Party Scripts Dynamically**

```typescript
useEffect(() => {
  const script = document.createElement('script')
  script.src = 'https://example.com/script.js'
  script.async = true
  document.body.appendChild(script)
  
  return () => {
    document.body.removeChild(script)
  }
}, [])
```

### 6. CSS Optimization

**Purge Unused CSS**

Tailwind CSS automatically purges unused styles in production.

**Avoid Large CSS Files**

```css
/* Avoid */
.button {
  /* 100 lines of styles */
}

/* Prefer - use utility classes with Tailwind */
<button className="px-4 py-2 bg-blue-500 rounded">
```

### 7. Data Fetching Optimization

**Use Server Components**

```typescript
// Good - Runs on server
async function Dashboard() {
  const data = await fetchData()
  return <div>{data}</div>
}

// Avoid - Runs on client
'use client'
function Dashboard() {
  const [data, setData] = useState(null)
  useEffect(() => {
    fetchData().then(setData)
  }, [])
  return <div>{data}</div>
}
```

**Implement Caching**

```typescript
// Cache API responses
const cachedData = await cache.get('key')
if (cachedData) return cachedData

const data = await fetchData()
await cache.set('key', data, 3600)
return data
```

## Performance Budgets

Set performance budgets to catch regressions:

**In package.json:**

```json
{
  "scripts": {
    "build": "next build",
    "analyze": "ANALYZE=true npm run build"
  }
}
```

**Target Bundle Sizes:**
- Initial JS: < 200KB gzipped
- Total JS: < 500KB gzipped
- CSS: < 50KB gzipped

## Monitoring Performance

### Lighthouse CI

```bash
npm install --save-dev @lhci/cli
```

```json
{
  "ci": {
    "collect": {
      "staticDistDir": ".next"
    },
    "assert": {
      "preset": "lighthouse:recommended"
    }
  }
}
```

### Web Vitals

Track Core Web Vitals:

```typescript
'use client'
import { useReportWebVitals } from 'next/web-vitals'

export function WebVitals() {
  useReportWebVitals((metric) => {
    console.log(metric)
    // Send to analytics
  })
  return null
}
```

## Preloading Resources

**Critical CSS**

```typescript
<link rel="preload" href="/styles.css" as="style" />
```

**Critical Fonts**

```typescript
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" />
```

**Critical Scripts**

```typescript
<script src="/critical.js" defer></script>
```

## Production Build Checklist

- [ ] Run bundle analyzer and review results
- [ ] Remove unused dependencies
- [ ] Optimize images (compress, use WebP)
- [ ] Implement code splitting for large components
- [ ] Enable compression (already enabled)
- [ ] Configure CDN for static assets
- [ ] Set up cache headers for static assets
- [ ] Test Lighthouse score (>90)
- [ ] Monitor Core Web Vitals in production

## Troubleshooting

### Bundle Too Large

1. Run bundle analyzer
2. Identify largest chunks
3. Use dynamic imports for large components
4. Replace heavy libraries with alternatives
5. Remove unused dependencies

### Slow First Contentful Paint (FCP)

1. Optimize above-the-fold content
2. Preload critical resources
3. Use server-side rendering
4. Reduce JavaScript blocking render

### High Time to Interactive (TTI)

1. Reduce main thread work
2. Code split JavaScript
3. Defer non-critical JavaScript
4. Optimize third-party scripts

## Additional Resources

- [Next.js Optimization Docs](https://nextjs.org/docs/app/building-your-application/optimizing)
- [Web.dev Performance](https://web.dev/performance/)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)

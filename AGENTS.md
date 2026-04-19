# Kimi Agent Guidelines

## Project Overview

Quartz static site generator with multi-domain support.

### Architecture
- **Frontend**: TypeScript/React, D3.js/Pixi.js for graph rendering
- **Backend**: Go server (quartz-service.exe) on :8766
- **Build**: Node.js/TypeScript with esbuild
- **Key Config**: quartz.config.json and quartz.layout.json in settings/{domain}/ control per-domain settings

## Code Standards

### 1. Encoding
- **ALL files must use UTF-8 encoding**
- Never write non-UTF-8 characters to source files
- Use WriteFile tool which handles encoding correctly

### 2. TypeScript Static Checking
- **Must run `npx tsc --noEmit` after every code change**
- Fix all TS errors before committing
- No warnings should be introduced

### 3. Testing
- **Write `.test.ts` files for testable logic**
- Run tests to verify functionality
- Don't skip tests for complex algorithms

### 4. Documentation
- **Update `.spec/*.md` files when implementing features**
- Document design decisions and trade-offs
- Keep .spec files in sync with code changes

## Development Workflow

1. **Understand** → Read existing code and .spec files
2. **Design** → Document approach in .spec if complex
3. **Implement** → Write code with TS checks
4. **Test** → Write and run tests
5. **Document** → Update .spec with final design

## File Organization

```
.spec/              # Design specs and architecture docs
client/quartz/      # Frontend TypeScript code
server/             # Go backend code
input/              # Source markdown files
output/             # Generated static sites
```

## Key Patterns

### Slug Types
- `FullSlug`: Full path with brand type
- `SimpleSlug`: Simplified path
- Use `simplifySlug()` to convert between them

### Graph Data Flow
- contentIndex.json → search, toc, graph (shared)
- graph/local/{slug}.json → separate precomputed graph data
- Don't modify contentIndex structure for graph optimization

### Build Commands
```bash
# Build with settings
npx quartz build --sqlite --settings <path> -d <input> -o <output>

# Reset flag via array (avoid shell parsing issues)
```

## Current Active Work

### Graph Optimization (Phase 1 Complete)
- ✅ Single-page neighborhood pre-calculation implemented
- ✅ Data structure aligned with contentIndex (Record<slug, ContentDetails>)
- ✅ Path structure: {md5(0,2)}/{md5(2,2)}/{slug}.json (slug may contain '/')
- ✅ graph2.inline.ts reads precomputed data with fallback to BFS
- ⏳ Performance testing pending

### Key Implementation Details
1. **GraphLocalEmitter** (`client/quartz/plugins/emitters/graphLocal.tsx`)
   - Generates local graph JSON for each page at build time
   - MD5 computed on full slug (including path separators)
   - Nodes stored as Record<slug, ContentDetails> for compatibility

2. **Data Format** (`graph/local/{hash}/{slug}.json`)
   ```json
   {
     "version": 1,
     "center": "page-slug",
     "depth": 1,
     "nodes": {
       "page-slug": { /* ContentDetails */ },
       "linked-page": { /* ContentDetails */ }
     },
     "edges": [
       {"source": "...", "target": "...", "sourceField": "project"}
     ]
   }
   ```

3. **Virtual Node Detection**
   - Virtual nodes have `filePath: ""`
   - Regular nodes have non-empty `filePath`

See `.spec/graph-local-precompute.md` for detailed design.

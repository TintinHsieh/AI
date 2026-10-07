# Campus Customs usability improvements

## Front-end improvement 1: Saved pieces / wishlist

### What I added

Product cards now have a heart control, product detail pages have a `Save piece` control, and the header shows the number of saved pieces. Saved product ids are stored in browser `localStorage`, so the list survives a refresh without adding an account requirement. The Products page also has a `Saved` filter.

### Why it helps

Shoppers can collect a short list of Yale pieces while browsing and return to it later, even as guests. The business gets a lower-friction way for shoppers to signal interest without requiring checkout or account creation.

## Front-end improvement 2: Clear catalogue sorting and filters

### What I added

The Products page now supports sorting by featured order, name, lowest price, or highest price. It also has a visible `Clear filters` action that resets search, garment type, sorting, and the saved-only filter, while the result count stays visible.

### Why it helps

Shoppers can move from discovery to a practical choice faster, especially when they have a budget or know the product name they want. Clear reset behavior prevents a hidden filter from making the catalogue appear empty and reduces support questions.

## Agent/backend improvement 1: Inventory-aware search

### What I added

The `catalogue_search` agent tool now accepts `in_stock_only`. It also detects explicit phrases such as `in stock`, `available`, and `on hand` both in the tool query and in the original request-level agent dependencies as a deterministic safety backstop. The SQL query then requires a positive inventory quantity. General discovery still includes catalogue rows without silently changing the shopper's request.

### Why it helps

The assistant is less likely to recommend a sold-out product when a shopper asks what they can actually buy. This protects trust and gives the business more accurate availability conversations.

## Agent/backend improvement 2: Short-lived catalogue search cache

### What I added

Repeated identical catalogue searches are cached in the backend for 30 seconds, keyed by database path, normalized query, result limit, and stock-only mode. The cache is capped at 128 keys, and cached `ProductMatch` objects are copied into each request's dependencies, so structured results remain bounded and isolated between shoppers.

### Why it helps

Repeated questions and refreshes avoid unnecessary SQLite work, making the chat feel faster and reducing backend load. The short TTL limits staleness while preserving the database as the source of truth for normal uncached reads.

## Verification

- Frontend build: `npm run build`.
- Saved-piece state is wired to `localStorage`, card/detail controls, header count, and the Products-page Saved filter.
- Sorting and clear-filter state are wired to the visible Products toolbar.
- Direct tool checks cover both general `hoodies` search and `hoodies in stock` search.
- Repeating the same tool query uses the bounded cache; the cache key separates general and stock-only results.

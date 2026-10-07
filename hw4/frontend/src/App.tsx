import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  clearSession,
  fetchChatHistory,
  fetchProduct,
  fetchProducts,
  imageUrl,
  loadSession,
  loginAccount,
  loadFavoriteIds,
  registerAccount,
  saveSession,
  saveFavoriteIds,
  sendChatMessage,
  type AuthResponse,
  type AuthUser,
} from "./api";
import type { ChatHistoryMessage, Product, ProductMatch } from "./types";

type NavItem = { label: string; href: string };

const navItems: NavItem[] = [
  { label: "Home", href: "/" },
  { label: "Products", href: "/products" },
  { label: "About Us", href: "/about" },
  { label: "Log in", href: "/login" },
  { label: "Create account", href: "/create-account" },
];

function formatPrice(price: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(price);
}

function truncate(text: string, length = 112): string {
  return text.length > length ? `${text.slice(0, length).trim()}…` : text;
}

function Header({ onNavigate, path, user, onLogout, savedCount }: { onNavigate: (href: string) => void; path: string; user: AuthUser | null; onLogout: () => void; savedCount: number }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <a
          className="brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("/");
          }}
        >
          <span className="brand-mark">CC</span>
          <span className="brand-name">
            Campus <em>Customs</em>
          </span>
        </a>
        <nav aria-label="Main navigation" className="main-nav">
          {navItems.map((item) => {
            const active = item.href === "/" ? path === "/" : path.startsWith(item.href);
            return (
              <a
                className={active ? "nav-link active" : "nav-link"}
                href={item.href}
                key={item.href}
                onClick={(event) => {
                  event.preventDefault();
                  onNavigate(item.href);
                }}
              >
                {item.label}
              </a>
            );
          })}
        </nav>
        <a className="header-badge" href="/products" onClick={(event) => { event.preventDefault(); onNavigate("/products"); }}>
          <span>New Haven</span>
          <strong>Est. 1701</strong>
        </a>
        <span className="saved-count" aria-label={`${savedCount} saved pieces`}>Saved {savedCount}</span>
        {user && <div className="header-account"><span>Hi, {user.first_name || user.name}</span><button className="logout-button" onClick={onLogout}>Log out</button></div>}
      </div>
    </header>
  );
}

function ProductCard({ product, onOpen, isFavorite, onToggleFavorite }: { product: ProductMatch; onOpen: (product: ProductMatch) => void; isFavorite: boolean; onToggleFavorite: (productId: string) => void }) {
  const openWithKeyboard = (event: KeyboardEvent<HTMLElement>) => {
    if (event.target instanceof HTMLButtonElement) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen(product);
    }
  };

  return (
    <article
      className="product-card"
      onClick={() => onOpen(product)}
      onKeyDown={openWithKeyboard}
      role="button"
      tabIndex={0}
    >
      <div className="product-image-wrap">
        <img src={imageUrl(product.image_url)} alt={product.name} loading="lazy" />
        <span className="product-type">{product.garment_type}</span>
        <button
          type="button"
          className={isFavorite ? "favorite-button saved" : "favorite-button"}
          aria-label={isFavorite ? `Remove ${product.name} from saved pieces` : `Save ${product.name}`}
          aria-pressed={isFavorite}
          onClick={(event) => { event.stopPropagation(); onToggleFavorite(product.product_id); }}
        >{isFavorite ? "♥" : "♡"}</button>
      </div>
      <div className="product-card-content">
        <div className="product-card-heading">
          <h3>{product.name}</h3>
          <span>{formatPrice(product.price)}</span>
        </div>
        <p>{truncate(product.description)}</p>
        <div className="product-card-foot"><span className={product.total_stock > 0 ? "product-stock" : "product-stock sold-out-label"}><i />{product.total_stock > 0 ? `${product.total_stock} in stock` : "Currently unavailable"}</span><span className="product-card-route">Open / piece</span></div>
        <span className="text-link">View piece <span aria-hidden="true">↗</span></span>
      </div>
    </article>
  );
}

function SectionLabel({ children }: { children: string }) {
  return <p className="section-label"><span className="label-dot" />{children}</p>;
}

function HomePage({ products, onNavigate, onOpen, favoriteIds, onToggleFavorite }: { products: Product[]; onNavigate: (href: string) => void; onOpen: (product: ProductMatch) => void; favoriteIds: Set<string>; onToggleFavorite: (productId: string) => void }) {
  const featured = products.slice(0, 3);
  return (
    <div className="page home-page">
      <section className="hero-section">
        <div className="hero-copy">
          <SectionLabel>Yale spiritwear / New Haven, CT</SectionLabel>
          <h1>Wear the<br /><span>blue</span> boldly.</h1>
          <p className="hero-subtitle">The campus is a feeling. Campus Customs makes it wearable — classic Yale character with a little more attitude.</p>
          <div className="hero-actions">
            <button className="button button-primary" onClick={() => onNavigate("/products")}>Shop the collection <span aria-hidden="true">↗</span></button>
            <button className="text-button" onClick={() => onNavigate("/about")}>Our story <span aria-hidden="true">→</span></button>
          </div>
        </div>
        <div className="hero-art" aria-label="Graphic collage featuring a Yale blue circle and pink star" role="img">
          <div className="hero-circle"><span>YALE</span><strong>CC</strong><small>NEW HAVEN / EST. 1701</small></div>
          <div className="hero-star">✦</div>
          <div className="hero-sticker">Built<br /><em>for</em><br />belonging.</div>
          <div className="hero-line line-one" />
          <div className="hero-line line-two" />
          <div className="hero-orbit orbit-one" />
          <div className="hero-orbit orbit-two" />
          <div className="hero-caption caption-top">Lookbook / 01</div>
          <div className="hero-caption caption-bottom">Yale / New Haven</div>
        </div>
      </section>

      <section className="ticker" aria-label="Campus Customs values">
        <span>YALE MADE</span><span>NEW HAVEN ROOTED</span><span>EVERYDAY ICONS</span><span>YALE MADE</span><span>NEW HAVEN ROOTED</span>
      </section>

      <section className="home-intro section-shell">
        <div>
          <SectionLabel>Not your average bookstore</SectionLabel>
          <h2>Classic looks.<br /><em>Current energy.</em></h2>
        </div>
        <div className="intro-copy">
          <p>From lecture hall mornings to late-night slices on York Street, these are the layers that keep up. Shop easy staples, college pride, and the pieces you’ll still reach for after graduation.</p>
          <button className="text-button" onClick={() => onNavigate("/about")}>Meet Campus Customs <span aria-hidden="true">→</span></button>
        </div>
      </section>

      <section className="featured-section section-shell">
        <div className="section-heading-row">
          <div><SectionLabel>From the catalogue</SectionLabel><h2>Good things<br /><em>in rotation.</em></h2></div>
          <button className="outline-button" onClick={() => onNavigate("/products")}>See all products <span aria-hidden="true">↗</span></button>
        </div>
        {products.length === 0 ? (
          <div className="empty-state">The catalogue is loading — check that the FastAPI service is running.</div>
        ) : (
          <div className="product-grid featured-grid">
            {featured.map((product) => <ProductCard key={product.product_id} product={product} onOpen={onOpen} isFavorite={favoriteIds.has(product.product_id)} onToggleFavorite={onToggleFavorite} />)}
          </div>
        )}
      </section>

      <section className="manifesto-section">
        <div className="manifesto-mark">CC<span>✦</span></div>
        <p>Wear where<br /><em>you’re from.</em></p>
        <span className="manifesto-note">A little blue goes a long way.</span>
      </section>
    </div>
  );
}

function ProductsPage({ products, loading, error, onOpen, favoriteIds, onToggleFavorite }: { products: Product[]; loading: boolean; error: string | null; onOpen: (product: ProductMatch) => void; favoriteIds: Set<string>; onToggleFavorite: (productId: string) => void }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All pieces");
  const [sortBy, setSortBy] = useState("featured");
  const [savedOnly, setSavedOnly] = useState(false);
  const categories = useMemo(() => ["All pieces", ...Array.from(new Set(products.map((product) => product.garment_type))).sort()], [products]);
  const filteredProducts = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const matching = products.filter((product) => {
      const matchesCategory = category === "All pieces" || product.garment_type === category;
      const searchable = [product.name, product.garment_type, product.description, ...product.colors, ...product.search_tags].join(" ").toLowerCase();
      return matchesCategory && (!needle || searchable.includes(needle)) && (!savedOnly || favoriteIds.has(product.product_id));
    });
    return [...matching].sort((left, right) => {
      if (sortBy === "name") return left.name.localeCompare(right.name);
      if (sortBy === "price-low") return left.price - right.price;
      if (sortBy === "price-high") return right.price - left.price;
      return 0;
    });
  }, [category, favoriteIds, products, savedOnly, search, sortBy]);
  const hasFilters = Boolean(search.trim()) || category !== "All pieces" || sortBy !== "featured" || savedOnly;
  const clearFilters = () => { setSearch(""); setCategory("All pieces"); setSortBy("featured"); setSavedOnly(false); };

  return (
    <div className="page products-page section-shell">
      <div className="page-intro-row">
        <div><SectionLabel>The full collection</SectionLabel><h1>Find your<br /><em>new favorite.</em></h1></div>
        <p className="page-intro-copy">Campus staples, reworked classics, and the occasional piece that starts a conversation. Filter the catalogue or search by what you’re feeling.</p>
      </div>
      <div className="collection-banner"><span className="collection-banner-mark">CC</span><div><span className="collection-banner-kicker">The New Haven edit / 2025</span><strong>Layers for the in-between.</strong></div><span className="collection-banner-index">01—04</span></div>
      <div className="catalogue-toolbar">
        <label className="search-field"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search products, colors, schools..." /></label>
        <label className="filter-field"><span>Filter</span><select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="filter-field"><span>Sort</span><select value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="featured">Featured</option><option value="name">Name A–Z</option><option value="price-low">Price low–high</option><option value="price-high">Price high–low</option></select></label>
        <button type="button" className={savedOnly ? "saved-filter active" : "saved-filter"} onClick={() => setSavedOnly((current) => !current)} aria-pressed={savedOnly}>♡ Saved ({favoriteIds.size})</button>
        {hasFilters && <button type="button" className="clear-filters" onClick={clearFilters}>Clear filters</button>}
        <span className="result-count">{filteredProducts.length} pieces</span>
      </div>
      {loading && <div className="loading-state"><span className="loading-orb" />Loading the collection...</div>}
      {error && <div className="error-state"><strong>Catalogue unavailable.</strong> {error}<br /><small>Start the API with <code>uvicorn backend.main:app --reload</code>.</small></div>}
      {!loading && !error && filteredProducts.length === 0 && <div className="empty-state">No pieces match that search. Try “hoodie”, “Yale”, or a color.</div>}
      <div className="product-grid catalogue-grid">
        {filteredProducts.map((product) => <ProductCard key={product.product_id} product={product} onOpen={onOpen} isFavorite={favoriteIds.has(product.product_id)} onToggleFavorite={onToggleFavorite} />)}
      </div>
    </div>
  );
}

function ChatResultsTray({ matches, onOpen, onClear, favoriteIds, onToggleFavorite }: { matches: ProductMatch[]; onOpen: (product: ProductMatch) => void; onClear: () => void; favoriteIds: Set<string>; onToggleFavorite: (productId: string) => void }) {
  if (!matches.length) return null;
  return (
    <section className="chat-results section-shell" aria-live="polite">
      <div className="section-heading-row chat-results-heading">
        <div><SectionLabel>From your chat</SectionLabel><h2>Good matches,<br /><em>right here.</em></h2></div>
        <button className="text-button" onClick={onClear}>Clear picks <span aria-hidden="true">→</span></button>
      </div>
      <div className="product-grid chat-results-grid">
        {matches.map((product) => <ProductCard key={product.product_id} product={product} onOpen={onOpen} isFavorite={favoriteIds.has(product.product_id)} onToggleFavorite={onToggleFavorite} />)}
      </div>
    </section>
  );
}

function ProductDetailPage({ product, loading, onNavigate, isFavorite, onToggleFavorite }: { product: Product | null; loading: boolean; onNavigate: (href: string) => void; isFavorite: boolean; onToggleFavorite: (productId: string) => void }) {
  if (loading) return <div className="page section-shell loading-page"><span className="loading-orb" />Loading this piece...</div>;
  if (!product) return <div className="page section-shell"><div className="error-state">That piece could not be found. <button className="text-button" onClick={() => onNavigate("/products")}>Back to products →</button></div></div>;
  const availableSizes = product.stock.filter((level) => level.quantity > 0);
  return (
    <div className="page detail-page section-shell">
      <button className="back-link" onClick={() => onNavigate("/products")}><span aria-hidden="true">←</span> Back to all pieces</button>
      <div className="detail-layout">
        <div className="detail-image-panel"><img src={imageUrl(product.image_url)} alt={product.name} /><span className="detail-stamp">CC / {product.garment_type}</span></div>
        <div className="detail-copy">
          <SectionLabel>{product.garment_type}</SectionLabel>
          <div className="detail-title-row"><h1>{product.name}</h1><button type="button" className={isFavorite ? "favorite-detail-button saved" : "favorite-detail-button"} onClick={() => onToggleFavorite(product.product_id)} aria-pressed={isFavorite}>{isFavorite ? "♥ Saved" : "♡ Save piece"}</button></div>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <div className="detail-rule" />
          <p className="detail-description">{product.description}</p>
          <div className="detail-meta"><span>Color notes</span><p>{product.colors.join(" · ")}</p></div>
          <div className="detail-meta"><span>Available sizes</span>
            {availableSizes.length ? <div className="size-list">{availableSizes.map((level) => <span className="size-chip" key={level.size}>{level.size}<small>{level.quantity} left</small></span>)}</div> : <p>Currently out of stock</p>}
          </div>
          <div className={product.total_stock > 0 ? "stock-callout" : "stock-callout sold-out"}><span className="status-dot" />{product.total_stock > 0 ? `${product.total_stock} total in stock` : "Currently unavailable"}<small>Live from the Campus Customs catalogue</small></div>
          <button className="button button-primary wide-button" onClick={() => onNavigate("/login")}>Sign in to save this piece <span aria-hidden="true">↗</span></button>
        </div>
      </div>
    </div>
  );
}

function AboutPage({ onNavigate }: { onNavigate: (href: string) => void }) {
  return (
    <div className="page about-page">
      <section className="about-hero section-shell"><SectionLabel>A different kind of campus store</SectionLabel><h1>Made for the<br /><span>long haul.</span></h1><p>Campus Customs is Yale spiritwear with a point of view: familiar enough to feel like home, considered enough to keep in your rotation.</p></section>
      <section className="about-grid section-shell"><div className="about-number">01</div><div><h2>Rooted in New Haven.<br /><em>Open to everywhere.</em></h2><p>We make pieces for the people who know the shortcut through Old Campus, the best seat in the library, and the exact weather that calls for a crewneck. The goal is simple: make belonging feel easy to wear.</p><p>Start with a classic. Make it yours.</p><button className="outline-button" onClick={() => onNavigate("/products")}>Browse the collection <span aria-hidden="true">↗</span></button></div></section>
      <section className="about-values"><div className="section-shell values-inner"><div><SectionLabel>Our north stars</SectionLabel><h2>Good design.<br /><em>Good company.</em></h2></div><div className="value-list"><div><strong>01 / Wearability</strong><p>Pieces that go from first coffee to last call.</p></div><div><strong>02 / Character</strong><p>Classic Yale cues, with room for your own point of view.</p></div><div><strong>03 / Belonging</strong><p>A storefront for students, alumni, neighbors, and friends.</p></div></div></div></section>
    </div>
  );
}

function AuthPage({ mode, onSuccess }: { mode: "login" | "create"; onSuccess: (session: AuthResponse) => void }) {
  const isLogin = mode === "login";
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    setSubmitting(true);
    try {
      const session = isLogin
        ? await loginAccount({ email, password })
        : await registerAccount({
            first_name: String(form.get("firstName") ?? "").trim(),
            last_name: String(form.get("lastName") ?? "").trim(),
            email,
            password,
            confirm_password: String(form.get("confirmPassword") ?? ""),
          });
      saveSession(session);
      onSuccess(session);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "We could not complete that request.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page auth-page section-shell"><div className="auth-card"><div className="auth-aside"><span className="auth-aside-mark">CC</span><p>Keep the good<br /><em>stuff close.</em></p><small>One account for your Campus Customs.</small></div><div className="auth-form-wrap"><SectionLabel>{isLogin ? "Welcome back" : "Join the club"}</SectionLabel><h1>{isLogin ? "Log in to your" : "Make it yours."}<br /><em>{isLogin ? "collection." : "Create an account."}</em></h1><form onSubmit={handleSubmit} className="auth-form">{!isLogin && <div className="field-row"><label>First name<input required name="firstName" autoComplete="given-name" /></label><label>Last name<input required name="lastName" autoComplete="family-name" /></label></div>}<label>Email address<input required type="email" name="email" autoComplete="email" /></label><label>Password<input required minLength={8} type="password" name="password" autoComplete={isLogin ? "current-password" : "new-password"} /></label>{!isLogin && <label>Confirm password<input required minLength={8} type="password" name="confirmPassword" autoComplete="new-password" /></label>}{error && <p className="form-error" role="alert">{error}</p>}<button className="button button-primary wide-button" disabled={submitting} type="submit">{submitting ? "Checking..." : isLogin ? "Log in" : "Create account"} <span aria-hidden="true">↗</span></button></form><p className="auth-note">Passwords are protected with a one-way scrypt hash. Your password is never stored in the browser or database as plain text.</p></div></div></div>
  );
}

type ChatMessage = { from: "shopper" | "assistant"; text: string; matches?: ProductMatch[] };

/* Legacy local chat preview retained in the assignment history; the live widget is below.
function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([{ from: "assistant", text: "Hey — welcome to Campus Customs. I’m a preview of the shop assistant. Ask me about a piece and I’ll be ready when the catalogue brain is connected." }]);
  const sendMessage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;
    setMessages((current) => [...current, { from: "shopper", text: value }, { from: "assistant", text: "This chat preview is ready for the backend. Soon I’ll search the catalogue and bring matching pieces right here." }]);
    setDraft("");
  };
  return (
    <div className={open ? "chat-widget open" : "chat-widget"}>
      {open && <div className="chat-panel"><div className="chat-panel-header"><div><span className="live-dot" />Customs assistant</div><button aria-label="Close chat" onClick={() => setOpen(false)}>×</button></div><div className="chat-messages">{messages.map((message, index) => <div className={message.from === "shopper" ? "chat-message shopper" : "chat-message"} key={`${message.from}-${index}`}>{message.text}</div>)}</div><div className="chat-suggestions"><button onClick={() => setDraft("Show me hoodies")}>Hoodies</button><button onClick={() => setDraft("What is new?")}>What’s new?</button></div><form onSubmit={sendMessage} className="chat-input"><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about the collection..." aria-label="Chat message" /><button aria-label="Send message">↑</button></form></div>}
      <button className="chat-launcher" onClick={() => setOpen((current) => !current)} aria-expanded={open}><span className="chat-icon">✦</span><span>{open ? "Close" : "Chat with us"}</span></button>
    </div>
  );
}

*/
function ConnectedChatWidget({
  session,
  pageContext,
  onMatches,
}: {
  session: AuthResponse | null;
  pageContext: Record<string, unknown>;
  onMatches: (matches: ProductMatch[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { from: "assistant", text: "Hey — welcome to Campus Customs. Ask me about hoodies, colors, sizes, or a specific piece." },
  ]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setMessages([{ from: "assistant", text: "Hey — welcome to Campus Customs. Ask me about hoodies, colors, sizes, or a specific piece." }]);
    setError(null);
    onMatches([]);
    if (!session?.token) return () => { active = false; };
    fetchChatHistory(session.token)
      .then((history) => {
        if (!active) return;
        const restored = history.messages.map((message: ChatHistoryMessage) => ({
          from: message.role === "user" ? "shopper" as const : "assistant" as const,
          text: message.content,
          matches: message.matches,
        }));
        setMessages(restored.length ? restored : [{ from: "assistant", text: "Welcome back. What are you looking for today?" }]);
        const latestMatches = [...history.messages].reverse().find((message) => message.matches.length)?.matches ?? [];
        onMatches(latestMatches);
      })
      .catch(() => {
        if (active) setError("I could not reload your saved chat yet.");
      });
    return () => { active = false; };
  }, [onMatches, session?.token]);

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value || sending) return;
    setDraft("");
    setError(null);
    setMessages((current) => [...current, { from: "shopper", text: value }]);
    setSending(true);
    try {
      const response = await sendChatMessage(value, pageContext, session?.token);
      setMessages((current) => [...current, { from: "assistant", text: response.reply, matches: response.matches }]);
      onMatches(response.matches);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "The assistant could not answer right now.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className={open ? "chat-widget open" : "chat-widget"}>
      {open && <div className="chat-panel"><div className="chat-panel-header"><div className="chat-brand"><span className="chat-avatar">CC</span><div><strong>Customs assistant</strong><small>{session ? "Saved to your account" : "Your catalogue sidekick"}</small></div></div><button aria-label="Close chat" onClick={() => setOpen(false)}>×</button></div><div className="chat-messages">{messages.map((message, index) => <div className={message.from === "shopper" ? "chat-message shopper" : "chat-message"} key={`${message.from}-${index}`}>{message.from === "assistant" && <span className="message-kicker">CC / NOTE</span>}{message.text}{message.matches?.length ? <small className="chat-match-note">{message.matches.length} product {message.matches.length === 1 ? "match" : "matches"} added below.</small> : null}</div>)}{sending && <div className="chat-message chat-thinking"><span className="thinking-dots"><i /><i /><i /></span>Searching the collection...</div>}{error && <div className="chat-error" role="alert">{error}</div>}</div><div className="chat-suggestions"><span className="suggestion-label">Try asking</span><button onClick={() => setDraft("Show me hoodies")}>Hoodies</button><button onClick={() => setDraft("What is new?")}>New arrivals</button></div><form onSubmit={sendMessage} className="chat-input"><span className="input-mark">/</span><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about the collection..." aria-label="Chat message" disabled={sending} /><button aria-label="Send message" disabled={sending}>→</button></form></div>}
      <button className="chat-launcher" onClick={() => setOpen((current) => !current)} aria-expanded={open}><span className="chat-icon">✦</span><span>{open ? "Close" : "Chat with us"}</span><span className="launcher-pulse" /></button>
    </div>
  );
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname || "/");
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [authSession, setAuthSession] = useState<AuthResponse | null>(() => loadSession());
  const [chatMatches, setChatMatches] = useState<ProductMatch[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => new Set(loadFavoriteIds()));

  const navigate = useCallback((nextPath: string) => {
    if (nextPath === path) return;
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [path]);

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname || "/");
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    fetchProducts()
      .then((result) => { setProducts(result); setCatalogueError(null); })
      .catch((reason: unknown) => setCatalogueError(reason instanceof Error ? reason.message : "The API could not be reached."))
      .finally(() => setLoadingProducts(false));
  }, []);

  const productId = path.match(/^\/products\/([^/]+)$/)?.[1];
  useEffect(() => {
    if (!productId) { setDetailProduct(null); setLoadingDetail(false); return; }
    const existing = products.find((item) => item.product_id === decodeURIComponent(productId));
    if (existing) { setDetailProduct(existing); setLoadingDetail(false); return; }
    setLoadingDetail(true);
    fetchProduct(decodeURIComponent(productId)).then(setDetailProduct).catch(() => setDetailProduct(null)).finally(() => setLoadingDetail(false));
  }, [productId, products]);

  const openProduct = (product: ProductMatch) => navigate(`/products/${encodeURIComponent(product.product_id)}`);
  const toggleFavorite = useCallback((productId: string) => {
    setFavoriteIds((current) => {
      const next = new Set(current);
      if (next.has(productId)) next.delete(productId);
      else next.add(productId);
      saveFavoriteIds([...next]);
      return next;
    });
  }, []);
  const pageContext = useMemo<Record<string, unknown>>(() => ({
    path,
    current_product: detailProduct ? {
      product_id: detailProduct.product_id,
      name: detailProduct.name,
      garment_type: detailProduct.garment_type,
      description: detailProduct.description,
      colors: detailProduct.colors,
      price: detailProduct.price,
    } : null,
  }), [detailProduct, path]);
  const handleChatMatches = useCallback((matches: ProductMatch[]) => setChatMatches(matches), []);
  const handleAuthSuccess = (session: AuthResponse) => {
    setAuthSession(session);
    navigate("/");
  };
  const handleLogout = () => {
    clearSession();
    setAuthSession(null);
    navigate("/");
  };
  let page;
  if (productId) page = <ProductDetailPage product={detailProduct} loading={loadingDetail} onNavigate={navigate} isFavorite={favoriteIds.has(decodeURIComponent(productId))} onToggleFavorite={toggleFavorite} />;
  else if (path === "/products") page = <ProductsPage products={products} loading={loadingProducts} error={catalogueError} onOpen={openProduct} favoriteIds={favoriteIds} onToggleFavorite={toggleFavorite} />;
  else if (path === "/about") page = <AboutPage onNavigate={navigate} />;
  else if (path === "/login") page = <AuthPage mode="login" onSuccess={handleAuthSuccess} />;
  else if (path === "/create-account") page = <AuthPage mode="create" onSuccess={handleAuthSuccess} />;
  else page = <HomePage products={products} onNavigate={navigate} onOpen={openProduct} favoriteIds={favoriteIds} onToggleFavorite={toggleFavorite} />;

  return <div className="app-shell"><Header onNavigate={navigate} path={path} user={authSession?.user ?? null} onLogout={handleLogout} savedCount={favoriteIds.size} /><main>{page}<ChatResultsTray matches={chatMatches} onOpen={openProduct} onClear={() => setChatMatches([])} favoriteIds={favoriteIds} onToggleFavorite={toggleFavorite} /></main><footer className="site-footer"><div className="footer-brand">Campus <em>Customs</em></div><p>New Haven layers for every kind of day.</p><span>2025 Campus Customs</span></footer><ConnectedChatWidget session={authSession} pageContext={pageContext} onMatches={handleChatMatches} /></div>;

}

CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    seed TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT NOT NULL DEFAULT 'seed',
    usage_count INTEGER NOT NULL DEFAULT 0,
    ranking_score REAL NOT NULL DEFAULT 50,
    last_posted_date_est TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (status IN ('active', 'needs_review', 'retired')),
    CHECK (ranking_score >= 0 AND ranking_score <= 100)
);

CREATE INDEX IF NOT EXISTS idx_concepts_status ON concepts(status);
CREATE INDEX IF NOT EXISTS idx_concepts_ranking_score ON concepts(ranking_score);
CREATE INDEX IF NOT EXISTS idx_concepts_last_posted_date_est ON concepts(last_posted_date_est);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    retailer TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    url TEXT NOT NULL,
    affiliate_url TEXT,
    image_url TEXT,
    local_image_path TEXT,
    price_cents INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (retailer, url)
);

CREATE INDEX IF NOT EXISTS idx_products_retailer ON products(retailer);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS outfits (
    id TEXT PRIMARY KEY,
    concept_id TEXT,
    concept_seed TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    product_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_outfits_concept_id ON outfits(concept_id);
CREATE INDEX IF NOT EXISTS idx_outfits_created_at ON outfits(created_at);

CREATE TABLE IF NOT EXISTS collages (
    id TEXT PRIMARY KEY,
    outfit_id TEXT NOT NULL,
    image_path TEXT NOT NULL,
    collage_url TEXT,
    layout_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (outfit_id) REFERENCES outfits(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collages_outfit_id ON collages(outfit_id);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    concept_id TEXT,
    outfit_id TEXT,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    image_path TEXT,
    caption TEXT,
    platform_post_id TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (platform IN ('tiktok', 'pinterest', 'local')),
    CHECK (status IN ('draft', 'scheduled', 'published', 'failed')),
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE SET NULL,
    FOREIGN KEY (outfit_id) REFERENCES outfits(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_concept_id ON posts(concept_id);
CREATE INDEX IF NOT EXISTS idx_posts_outfit_id ON posts(outfit_id);

CREATE TABLE IF NOT EXISTS metrics (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (platform IN ('tiktok', 'pinterest', 'local')),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_metrics_post_id ON metrics(post_id);
CREATE INDEX IF NOT EXISTS idx_metrics_collected_at ON metrics(collected_at);

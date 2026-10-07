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
    archived_at TEXT,
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
    scheduled_for TEXT,
    queue_order TEXT,
    is_manual_schedule BOOLEAN NOT NULL DEFAULT FALSE,
    approved BOOLEAN NOT NULL DEFAULT TRUE,
    link_check TEXT,
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
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_for ON posts(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_posts_queue_order ON posts(queue_order);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS admin_actions (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    target_id TEXT,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_created_at ON admin_actions(created_at);

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

-- ============================================================================
-- Security hardening (2026-10-07). An audit found the PUBLIC anon key (shipped
-- in the browser bundle) had full SELECT/INSERT/UPDATE/DELETE/TRUNCATE on every
-- table AND EXECUTE on the SECURITY DEFINER `_rpc_query` / `_rpc_exec` bridge —
-- i.e. anyone on the internet could run arbitrary SQL / wipe the database.
--
-- Access model after this block:
--   * service_role (worker + dashboard, server-only) — full access, bypasses RLS.
--   * anon (public site, web/lib/data.ts) — SELECT only on concepts/outfits/products.
--   * everything else — unreachable by the public.
--
-- Idempotent: safe to re-run (this whole file can be pasted into the Supabase
-- SQL editor, which runs as the table owner, to apply to an existing database).
-- ============================================================================

-- 1. Revoke the arbitrary-SQL RPC bridge from every non-privileged role.
--    (These are SECURITY DEFINER, so public EXECUTE = remote arbitrary SQL.)
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT oid::regprocedure AS sig FROM pg_proc
             WHERE proname IN ('_rpc_query', '_rpc_exec')
    LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated', r.sig);
    END LOOP;
END $$;

-- 2. Revoke all write privileges from the public roles. TRUNCATE is NOT gated by
--    RLS, so revoking the grant is required, not merely defense-in-depth.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

-- 3. Revoke read on everything the public site does not need.
REVOKE SELECT ON posts, collages, jobs, metrics, admin_actions
    FROM anon, authenticated;

-- 4. Enable row-level security on every table (service_role bypasses RLS).
ALTER TABLE concepts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE products      ENABLE ROW LEVEL SECURITY;
ALTER TABLE outfits       ENABLE ROW LEVEL SECURITY;
ALTER TABLE collages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE metrics       ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_actions ENABLE ROW LEVEL SECURITY;

-- 5. Read-only policies for the three tables the public gallery reads
--    (web/lib/data.ts). No write policy exists, so these are read-only even
--    before the grant revokes above.
DROP POLICY IF EXISTS anon_read_concepts ON concepts;
CREATE POLICY anon_read_concepts ON concepts FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS anon_read_outfits ON outfits;
CREATE POLICY anon_read_outfits  ON outfits  FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS anon_read_products ON products;
CREATE POLICY anon_read_products ON products FOR SELECT TO anon, authenticated USING (true);

-- 6. Stop FUTURE tables/functions from being auto-granted to the public roles.
--    Without this, Supabase's default privileges re-open the hole on the next
--    migration. (Applies to objects created by the role running this block —
--    the table owner — which is how the app creates schema objects.)
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated;

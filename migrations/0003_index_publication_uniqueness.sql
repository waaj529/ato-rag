-- Enforce one serving publication for each embedding profile.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS index_publications_one_active_idx
    ON index_publications (profile_id) WHERE status = 'active';

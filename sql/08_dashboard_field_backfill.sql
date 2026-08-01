-- 08_dashboard_field_backfill.sql
--
-- finsight.transactions.anomaly_score / is_flagged_iforest were added to sql/01_schema.sql
-- after this database was first built from it, so a from-scratch build already has them and
-- doesn't need this file. Run this once against an existing database that was built before
-- that change, to bring it in line - IF NOT EXISTS makes it safe to run more than once.
--
-- The columns themselves are only populated by src/fraud_detection.py::write_iforest_scores()
-- (Isolation Forest scoring requires the trained sklearn model, not something plain SQL can
-- produce) - this file only adds the columns, it doesn't fill them.
ALTER TABLE finsight.transactions ADD COLUMN IF NOT EXISTS anomaly_score NUMERIC(10,6);
ALTER TABLE finsight.transactions ADD COLUMN IF NOT EXISTS is_flagged_iforest SMALLINT;

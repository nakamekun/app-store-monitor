PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS apps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  app_store_id TEXT NOT NULL UNIQUE,
  bundle_id TEXT NOT NULL,
  sku TEXT,
  name TEXT NOT NULL,
  primary_locale TEXT,
  source TEXT NOT NULL DEFAULT 'mock',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  metric_date TEXT NOT NULL,
  app_id INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  impressions INTEGER NOT NULL DEFAULT 0,
  product_page_views INTEGER NOT NULL DEFAULT 0,
  downloads INTEGER NOT NULL DEFAULT 0,
  conversion_rate REAL NOT NULL DEFAULT 0.0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  UNIQUE (metric_date, app_id, source_type)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
  ON daily_metrics(metric_date);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_app_date
  ON daily_metrics(app_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_source_type
  ON daily_metrics(source_type);

CREATE TABLE IF NOT EXISTS app_usage_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  metric_date TEXT NOT NULL,
  app_id INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  active_devices INTEGER NOT NULL DEFAULT 0,
  sessions INTEGER NOT NULL DEFAULT 0,
  total_session_duration INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  UNIQUE (metric_date, app_id, source_type)
);

CREATE INDEX IF NOT EXISTS idx_app_usage_metrics_date
  ON app_usage_metrics(metric_date);

CREATE INDEX IF NOT EXISTS idx_app_usage_metrics_app_date
  ON app_usage_metrics(app_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_app_usage_metrics_source_type
  ON app_usage_metrics(source_type);

CREATE TABLE IF NOT EXISTS report_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_date TEXT NOT NULL,
  report_path TEXT,
  discord_sent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

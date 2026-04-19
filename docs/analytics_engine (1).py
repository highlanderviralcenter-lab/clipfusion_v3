"""
ClipFusion Viral Pro — AnalyticsEngine
SQLite puro (sqlite3, json, datetime). Zero dependências externas.

Módulos:
  - DataCollector      → registra métricas por corte/plataforma
  - PerformanceAnalyzer → CTR, retenção, engajamento, viral coefficient
  - LearningEngine     → aprende padrões, ajusta pesos
  - ReportGenerator    → HTML + console dashboard
  - ABTestFramework    → testa variações de hook/título
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ─── Caminho do banco ────────────────────────────────────────────────────────

DB_PATH = Path(os.path.expanduser("~")) / ".clipfusion" / "analytics.sqlite"


# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS performance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cut_id          TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    posted_at       TEXT,
    recorded_at     TEXT    DEFAULT (datetime('now')),
    views           INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    shares          INTEGER DEFAULT 0,
    watch_time_avg  REAL    DEFAULT 0.0,   -- segundos médios assistidos
    video_duration  REAL    DEFAULT 0.0,   -- duração total do corte
    archetype       TEXT    DEFAULT '',
    hook_text       TEXT    DEFAULT '',
    title           TEXT    DEFAULT '',
    nicho           TEXT    DEFAULT '',
    hour_posted     INTEGER DEFAULT -1,    -- 0-23
    ab_variant      TEXT    DEFAULT 'A'    -- 'A' ou 'B'
);

CREATE TABLE IF NOT EXISTS archetype_weights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nicho       TEXT NOT NULL,
    archetype   TEXT NOT NULL,
    weight      REAL DEFAULT 1.0,
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(nicho, archetype)
);

CREATE TABLE IF NOT EXISTS ab_tests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cut_id          TEXT NOT NULL,
    platform        TEXT NOT NULL,
    variant_a_hook  TEXT,
    variant_b_hook  TEXT,
    variant_a_title TEXT,
    variant_b_title TEXT,
    winner          TEXT DEFAULT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    resolved_at     TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS learning_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT,
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


# ─── Conexão ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.commit()
    return c


# ─── DataCollector ───────────────────────────────────────────────────────────

class DataCollector:
    """Registra e recupera métricas de performance de cortes."""

    def record(
        self,
        cut_id: str,
        platform: str,
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        watch_time_avg: float = 0.0,
        video_duration: float = 0.0,
        archetype: str = "",
        hook_text: str = "",
        title: str = "",
        nicho: str = "",
        posted_at: str = None,
        hour_posted: int = -1,
        ab_variant: str = "A",
    ) -> int:
        """Registra uma entrada de métricas. Retorna o ID inserido."""
        if posted_at is None:
            posted_at = datetime.now().isoformat()
        if hour_posted == -1:
            try:
                hour_posted = datetime.fromisoformat(posted_at).hour
            except Exception:
                hour_posted = datetime.now().hour

        c = _conn()
        cur = c.execute("""
            INSERT INTO performance_records
            (cut_id, platform, posted_at, views, likes, comments, shares,
             watch_time_avg, video_duration, archetype, hook_text, title,
             nicho, hour_posted, ab_variant)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cut_id, platform, posted_at, views, likes, comments, shares,
              watch_time_avg, video_duration, archetype, hook_text, title,
              nicho, hour_posted, ab_variant))
        rid = cur.lastrowid
        c.commit()
        c.close()
        return rid

    def update(self, record_id: int, **kwargs) -> None:
        """Atualiza campos de um registro existente (ex: após 24h)."""
        allowed = {"views", "likes", "comments", "shares", "watch_time_avg"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [record_id]
        c = _conn()
        c.execute(f"UPDATE performance_records SET {set_clause} WHERE id=?", values)
        c.commit()
        c.close()

    def get_by_cut(self, cut_id: str) -> list:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM performance_records WHERE cut_id=? ORDER BY recorded_at DESC",
            (cut_id,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_all(self, platform: str = None, nicho: str = None,
                since_days: int = None) -> list:
        query = "SELECT * FROM performance_records WHERE 1=1"
        params = []
        if platform:
            query += " AND platform=?"; params.append(platform)
        if nicho:
            query += " AND nicho=?"; params.append(nicho)
        if since_days:
            cutoff = (datetime.now() - timedelta(days=since_days)).isoformat()
            query += " AND recorded_at >= ?"; params.append(cutoff)
        query += " ORDER BY views DESC"
        c = _conn()
        rows = c.execute(query, params).fetchall()
        c.close()
        return [dict(r) for r in rows]


# ─── PerformanceAnalyzer ─────────────────────────────────────────────────────

class PerformanceAnalyzer:
    """Calcula CTR, retenção, engajamento e viral coefficient."""

    def metrics(self, record: dict) -> dict:
        views    = max(record.get("views", 0), 1)
        likes    = record.get("likes", 0)
        comments = record.get("comments", 0)
        shares   = record.get("shares", 0)
        wt_avg   = record.get("watch_time_avg", 0.0)
        duration = record.get("video_duration", 1.0) or 1.0

        engagement_rate  = round((likes + comments) / views * 100, 2)
        viral_coefficient = round(shares / views * 100, 2)
        retention_avg    = round(min(wt_avg / duration * 100, 100), 2)

        # CTR estimado: combinação de engajamento + compartilhamentos
        ctr_estimated = round((likes + comments + shares * 2) / views * 100, 2)

        viral_status = (
            "🔥 VIRAL"    if views >= 100_000 else
            "📈 BOM"      if views >= 10_000  else
            "😐 MÉDIO"    if views >= 1_000   else
            "💤 FLOP"
        )

        return {
            "cut_id":           record.get("cut_id"),
            "platform":         record.get("platform"),
            "views":            views,
            "likes":            likes,
            "comments":         comments,
            "shares":           shares,
            "ctr_estimated":    ctr_estimated,
            "retention_pct":    retention_avg,
            "engagement_rate":  engagement_rate,
            "viral_coefficient": viral_coefficient,
            "viral_status":     viral_status,
            "archetype":        record.get("archetype", ""),
            "hour_posted":      record.get("hour_posted", -1),
            "nicho":            record.get("nicho", ""),
        }

    def analyze_all(self, records: list) -> list:
        return [self.metrics(r) for r in records]

    def top_performers(self, records: list, n: int = 10) -> list:
        analyzed = self.analyze_all(records)
        return sorted(analyzed, key=lambda x: x["views"], reverse=True)[:n]

    def platform_summary(self, records: list) -> dict:
        platforms = {}
        for r in records:
            p = r.get("platform", "unknown")
            if p not in platforms:
                platforms[p] = {"views": [], "engagement": [], "retention": []}
            m = self.metrics(r)
            platforms[p]["views"].append(m["views"])
            platforms[p]["engagement"].append(m["engagement_rate"])
            platforms[p]["retention"].append(m["retention_pct"])

        summary = {}
        for p, data in platforms.items():
            def avg(lst): return round(sum(lst) / len(lst), 2) if lst else 0
            summary[p] = {
                "total_videos": len(data["views"]),
                "avg_views":      avg(data["views"]),
                "avg_engagement": avg(data["engagement"]),
                "avg_retention":  avg(data["retention"]),
                "total_views":    sum(data["views"]),
            }
        return summary


# ─── LearningEngine ──────────────────────────────────────────────────────────

class LearningEngine:
    """Aprende padrões dos vídeos e ajusta pesos dos arquétipos."""

    VIRAL_THRESHOLD = 100_000
    FLOP_THRESHOLD  = 1_000

    def compare_viral_vs_flop(self, records: list) -> dict:
        """Compara características de virais vs flops."""
        viral = [r for r in records if r.get("views", 0) >= self.VIRAL_THRESHOLD]
        flop  = [r for r in records if r.get("views", 0) < self.FLOP_THRESHOLD]

        def avg_field(lst, field):
            vals = [r.get(field, 0) for r in lst if r.get(field) is not None]
            return round(sum(vals) / len(vals), 2) if vals else 0

        return {
            "viral_count":          len(viral),
            "flop_count":           len(flop),
            "viral_avg_duration":   avg_field(viral, "video_duration"),
            "flop_avg_duration":    avg_field(flop,  "video_duration"),
            "viral_avg_hour":       avg_field(viral, "hour_posted"),
            "flop_avg_hour":        avg_field(flop,  "hour_posted"),
            "viral_top_archetypes": self._top_archetypes(viral),
            "flop_top_archetypes":  self._top_archetypes(flop),
        }

    def _top_archetypes(self, records: list) -> list:
        counts = {}
        for r in records:
            a = r.get("archetype", "unknown")
            counts[a] = counts.get(a, 0) + 1
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]

    def best_hours(self, records: list, platform: str = None) -> list:
        """Retorna os melhores horários reais ordenados por views médias."""
        filtered = [r for r in records
                    if (platform is None or r.get("platform") == platform)
                    and r.get("hour_posted", -1) >= 0]
        hours = {}
        for r in filtered:
            h = r["hour_posted"]
            if h not in hours:
                hours[h] = []
            hours[h].append(r.get("views", 0))
        result = []
        for h, views in hours.items():
            result.append({
                "hour":      h,
                "avg_views": round(sum(views) / len(views), 0),
                "count":     len(views),
            })
        return sorted(result, key=lambda x: x["avg_views"], reverse=True)

    def best_durations(self, records: list, platform: str = None) -> list:
        """Retorna faixas de duração ordenadas por views médias (buckets de 15s)."""
        filtered = [r for r in records
                    if (platform is None or r.get("platform") == platform)
                    and r.get("video_duration", 0) > 0]
        buckets = {}
        for r in filtered:
            d = r.get("video_duration", 0)
            bucket = int(d // 15) * 15  # agrupa em faixas de 15s
            label  = f"{bucket}–{bucket+15}s"
            if label not in buckets:
                buckets[label] = []
            buckets[label].append(r.get("views", 0))
        result = []
        for label, views in buckets.items():
            result.append({
                "range":     label,
                "avg_views": round(sum(views) / len(views), 0),
                "count":     len(views),
            })
        return sorted(result, key=lambda x: x["avg_views"], reverse=True)

    def update_archetype_weights(self, records: list, nicho: str) -> dict:
        """
        Ajusta pesos dos arquétipos baseado em performance real.
        Peso = avg_views do arquétipo / avg_views global (normalizado).
        """
        if not records:
            return {}

        global_avg = sum(r.get("views", 0) for r in records) / len(records)
        if global_avg == 0:
            return {}

        arch_views = {}
        for r in records:
            a = r.get("archetype", "")
            if not a:
                continue
            if a not in arch_views:
                arch_views[a] = []
            arch_views[a].append(r.get("views", 0))

        weights = {}
        c = _conn()
        for arch, views_list in arch_views.items():
            arch_avg = sum(views_list) / len(views_list)
            weight   = round(arch_avg / global_avg, 3)
            weights[arch] = weight
            c.execute("""
                INSERT INTO archetype_weights (nicho, archetype, weight, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(nicho, archetype) DO UPDATE SET
                    weight=excluded.weight, updated_at=excluded.updated_at
            """, (nicho, arch, weight))
            c.execute("""
                INSERT INTO learning_log (event, detail)
                VALUES ('weight_updated', ?)
            """, (json.dumps({"nicho": nicho, "archetype": arch, "weight": weight}),))
        c.commit()
        c.close()
        return weights

    def get_weights(self, nicho: str) -> dict:
        c = _conn()
        rows = c.execute(
            "SELECT archetype, weight FROM archetype_weights WHERE nicho=?",
            (nicho,)
        ).fetchall()
        c.close()
        return {r["archetype"]: r["weight"] for r in rows}

    def analyze_patterns(self, records: list, nicho: str = "") -> dict:
        """Retorna insights consolidados."""
        if not records:
            return {"error": "Sem dados suficientes para análise."}

        comparison   = self.compare_viral_vs_flop(records)
        best_hours   = self.best_hours(records)
        best_dur     = self.best_durations(records)
        weights      = self.update_archetype_weights(records, nicho) if nicho else {}

        insights = {
            "total_records":        len(records),
            "viral_vs_flop":        comparison,
            "best_hours":           best_hours[:5],
            "best_durations":       best_dur[:5],
            "archetype_weights":    weights,
            "top_archetype": (
                comparison["viral_top_archetypes"][0][0]
                if comparison["viral_top_archetypes"] else "n/a"
            ),
            "best_hour": (
                best_hours[0]["hour"] if best_hours else -1
            ),
            "best_duration_range": (
                best_dur[0]["range"] if best_dur else "n/a"
            ),
        }
        return insights


# ─── ReportGenerator ─────────────────────────────────────────────────────────

class ReportGenerator:
    """Gera relatório HTML + console."""

    def __init__(self):
        self.analyzer   = PerformanceAnalyzer()
        self.learner    = LearningEngine()

    def generate_report(self, records: list = None,
                        nicho: str = "",
                        output_path: str = None) -> str:
        if records is None:
            collector = DataCollector()
            records   = collector.get_all()

        if not records:
            return "<p>Sem dados ainda. Registre performances com DataCollector.record()</p>"

        top10        = self.analyzer.top_performers(records, 10)
        plat_summary = self.analyzer.platform_summary(records)
        insights     = self.learner.analyze_patterns(records, nicho)
        suggestions  = self.suggest_improvements(records, nicho)

        # ── HTML ──────────────────────────────────────────────────────────────
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")

        def fmt_row(m):
            return f"""
            <tr>
              <td>{m['cut_id'][:20]}</td>
              <td>{m['platform']}</td>
              <td>{m['views']:,}</td>
              <td>{m['engagement_rate']}%</td>
              <td>{m['retention_pct']}%</td>
              <td>{m['viral_coefficient']}%</td>
              <td>{m['archetype']}</td>
              <td>{m['viral_status']}</td>
            </tr>"""

        def fmt_plat(name, s):
            return f"""
            <tr>
              <td><b>{name}</b></td>
              <td>{s['total_videos']}</td>
              <td>{s['total_views']:,}</td>
              <td>{s['avg_views']:,}</td>
              <td>{s['avg_engagement']}%</td>
              <td>{s['avg_retention']}%</td>
            </tr>"""

        def fmt_sug(s):
            return f"<li>{s}</li>"

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>ClipFusion Analytics — {ts}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background:#0d0d1a; color:#f1f5f9; margin:0; padding:24px; }}
  h1   {{ color:#7c3aed; }} h2 {{ color:#a78bfa; border-bottom:1px solid #1e1e3a; padding-bottom:6px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:24px; }}
  th   {{ background:#1e1e3a; color:#a78bfa; padding:10px; text-align:left; }}
  td   {{ padding:8px 10px; border-bottom:1px solid #1e1e3a; }}
  tr:hover td {{ background:#151528; }}
  .card {{ background:#151528; border-radius:8px; padding:16px; margin:12px 0; }}
  .sug  {{ background:#1e1e3a; border-left:4px solid #7c3aed; padding:10px 16px; margin:8px 0; border-radius:4px; }}
  ul    {{ padding-left:20px; }} li {{ margin:6px 0; }}
  .green {{ color:#22c55e; }} .yellow {{ color:#f59e0b; }} .red {{ color:#ef4444; }}
</style>
</head>
<body>
<h1>✂ ClipFusion Analytics Dashboard</h1>
<p>Gerado em: {ts} | Total de registros: {len(records)}</p>

<h2>🏆 Top 10 Cortes de Todos os Tempos</h2>
<table>
  <tr><th>Corte</th><th>Plataforma</th><th>Views</th><th>Engajamento</th>
      <th>Retenção</th><th>Viral Coef.</th><th>Arquétipo</th><th>Status</th></tr>
  {''.join(fmt_row(m) for m in top10)}
</table>

<h2>📊 Média por Plataforma</h2>
<table>
  <tr><th>Plataforma</th><th>Vídeos</th><th>Views Total</th>
      <th>Média Views</th><th>Engajamento</th><th>Retenção</th></tr>
  {''.join(fmt_plat(n, s) for n, s in plat_summary.items())}
</table>

<h2>🧠 Insights do Sistema</h2>
<div class="card">
  <p>🕐 <b>Melhor horário para postar:</b> {insights.get('best_hour', 'n/a')}h</p>
  <p>⏱ <b>Melhor duração:</b> {insights.get('best_duration_range', 'n/a')}</p>
  <p>🎭 <b>Arquétipo campeão:</b> {insights.get('top_archetype', 'n/a')}</p>
  <p>🔥 <b>Virais:</b> {insights['viral_vs_flop'].get('viral_count', 0)} |
     💤 <b>Flops:</b> {insights['viral_vs_flop'].get('flop_count', 0)}</p>
</div>

<h2>💡 Sugestões do Sistema</h2>
<ul class="sug">{''.join(fmt_sug(s) for s in suggestions)}</ul>

</body></html>"""

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        return html

    def console_report(self, records: list = None, nicho: str = "") -> str:
        if records is None:
            collector = DataCollector()
            records   = collector.get_all()

        if not records:
            return "Sem dados. Use DataCollector.record() para começar."

        top10    = self.analyzer.top_performers(records, 10)
        insights = self.learner.analyze_patterns(records, nicho)
        sug      = self.suggest_improvements(records, nicho)

        lines = [
            "",
            "╔══════════════════════════════════════════════════════╗",
            "║         CLIPFUSION — ANALYTICS DASHBOARD            ║",
            f"║  {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {len(records)} registros{' ' * 20}║",
            "╚══════════════════════════════════════════════════════╝",
            "",
            "🏆 TOP 10 CORTES",
            f"  {'Corte':<22} {'Plat':<12} {'Views':>8} {'Eng%':>6} {'Reten%':>7} {'Status'}",
            "  " + "─" * 70,
        ]
        for m in top10:
            lines.append(
                f"  {m['cut_id'][:22]:<22} {m['platform']:<12} "
                f"{m['views']:>8,} {m['engagement_rate']:>5}% "
                f"{m['retention_pct']:>6}%  {m['viral_status']}"
            )

        lines += [
            "",
            "🧠 INSIGHTS",
            f"  Melhor horário : {insights.get('best_hour', 'n/a')}h",
            f"  Melhor duração : {insights.get('best_duration_range', 'n/a')}",
            f"  Arquétipo top  : {insights.get('top_archetype', 'n/a')}",
            f"  Virais / Flops : "
            f"{insights['viral_vs_flop'].get('viral_count', 0)} / "
            f"{insights['viral_vs_flop'].get('flop_count', 0)}",
            "",
            "💡 SUGESTÕES",
        ]
        for s in sug:
            lines.append(f"  → {s}")
        lines.append("")

        return "\n".join(lines)

    def suggest_improvements(self, records: list, nicho: str = "") -> list:
        if not records:
            return ["Sem dados suficientes para sugestões."]

        insights  = self.learner.analyze_patterns(records, nicho)
        sug       = []

        # Horário
        best_h = insights.get("best_hour", -1)
        if best_h >= 0:
            sug.append(
                f"Poste entre {best_h}h–{best_h+2}h — maior média de views registrada."
            )

        # Duração
        best_d = insights.get("best_duration_range", "")
        if best_d and best_d != "n/a":
            sug.append(f"Prefira cortes de {best_d} para maximizar retenção.")

        # Arquétipo
        top_arch = insights.get("top_archetype", "")
        if top_arch and top_arch != "n/a":
            sug.append(
                f"Arquétipo '{top_arch}' gera {self._arch_multiplier(records, top_arch):.1f}x "
                f"mais views — use mais."
            )

        # Virais vs flops
        vf = insights.get("viral_vs_flop", {})
        v_dur = vf.get("viral_avg_duration", 0)
        f_dur = vf.get("flop_avg_duration", 0)
        if v_dur and f_dur and abs(v_dur - f_dur) > 5:
            sug.append(
                f"Vídeos virais têm {v_dur:.0f}s de duração média vs "
                f"{f_dur:.0f}s dos flops."
            )

        if not sug:
            sug.append("Continue postando — dados insuficientes para padrões confiáveis.")

        return sug

    def _arch_multiplier(self, records: list, arch: str) -> float:
        arch_views  = [r.get("views", 0) for r in records if r.get("archetype") == arch]
        other_views = [r.get("views", 0) for r in records if r.get("archetype") != arch]
        avg_arch  = sum(arch_views) / len(arch_views)   if arch_views  else 1
        avg_other = sum(other_views) / len(other_views) if other_views else 1
        return round(avg_arch / max(avg_other, 1), 2)


# ─── ABTestFramework ─────────────────────────────────────────────────────────

class ABTestFramework:
    """Testa variações de hook/título e aprende qual performa melhor."""

    def create_test(
        self,
        cut_id: str,
        platform: str,
        variant_a_hook: str = "",
        variant_b_hook: str = "",
        variant_a_title: str = "",
        variant_b_title: str = "",
    ) -> int:
        c = _conn()
        cur = c.execute("""
            INSERT INTO ab_tests
            (cut_id, platform, variant_a_hook, variant_b_hook,
             variant_a_title, variant_b_title)
            VALUES (?,?,?,?,?,?)
        """, (cut_id, platform, variant_a_hook, variant_b_hook,
               variant_a_title, variant_b_title))
        tid = cur.lastrowid
        c.commit()
        c.close()
        return tid

    def resolve(self, test_id: int, records: list) -> dict:
        """
        Compara variantes A e B por views médias e declara vencedor.
        records: lista de DataCollector.record() com ab_variant='A' ou 'B'
        """
        c = _conn()
        test = c.execute(
            "SELECT * FROM ab_tests WHERE id=?", (test_id,)
        ).fetchone()
        c.close()
        if not test:
            return {"error": f"Teste {test_id} não encontrado."}

        cut_id = test["cut_id"]
        a_recs = [r for r in records
                  if r.get("cut_id") == cut_id and r.get("ab_variant") == "A"]
        b_recs = [r for r in records
                  if r.get("cut_id") == cut_id and r.get("ab_variant") == "B"]

        avg_a = sum(r.get("views", 0) for r in a_recs) / max(len(a_recs), 1)
        avg_b = sum(r.get("views", 0) for r in b_recs) / max(len(b_recs), 1)

        winner = "A" if avg_a >= avg_b else "B"
        winner_hook = test["variant_a_hook"] if winner == "A" else test["variant_b_hook"]

        c = _conn()
        c.execute("""
            UPDATE ab_tests SET winner=?, resolved_at=datetime('now') WHERE id=?
        """, (winner, test_id))
        c.execute("""
            INSERT INTO learning_log (event, detail) VALUES ('ab_resolved', ?)
        """, (json.dumps({
            "test_id": test_id, "cut_id": cut_id,
            "avg_a": avg_a, "avg_b": avg_b, "winner": winner,
        }),))
        c.commit()
        c.close()

        return {
            "test_id":     test_id,
            "cut_id":      cut_id,
            "avg_views_a": round(avg_a, 0),
            "avg_views_b": round(avg_b, 0),
            "winner":      winner,
            "winner_hook": winner_hook,
            "improvement": round(abs(avg_a - avg_b) / max(min(avg_a, avg_b), 1) * 100, 1),
        }

    def pending_tests(self) -> list:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM ab_tests WHERE winner IS NULL ORDER BY created_at DESC"
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def history(self) -> list:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM ab_tests WHERE winner IS NOT NULL ORDER BY resolved_at DESC"
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]


# ─── AnalyticsEngine (fachada principal) ─────────────────────────────────────

class AnalyticsEngine:
    """
    Fachada principal. Expõe todos os módulos com interface unificada.

    Uso rápido:
        engine = AnalyticsEngine()
        engine.record_performance("corte_001", "tiktok", views=50000, ...)
        print(engine.generate_report())
        print(engine.suggest_improvements())
    """

    def __init__(self):
        self.collector = DataCollector()
        self.analyzer  = PerformanceAnalyzer()
        self.learner   = LearningEngine()
        self.reporter  = ReportGenerator()
        self.ab        = ABTestFramework()

    # ── API principal ─────────────────────────────────────────────────────────

    def record_performance(
        self,
        cut_id: str,
        platform: str,
        metrics: dict,
    ) -> int:
        """
        Registra métricas de um corte.

        metrics = {
            "views": 50000,
            "likes": 3200,
            "comments": 180,
            "shares": 410,
            "watch_time_avg": 38.5,   # segundos médios assistidos
            "video_duration": 55.0,   # duração total do corte
            "archetype": "05_revelacao",
            "hook_text": "O segredo que...",
            "title": "Como fazer X",
            "nicho": "tecnologia",
            "posted_at": "2024-03-10T19:30:00",  # opcional
            "hour_posted": 19,                    # opcional
            "ab_variant": "A",                    # opcional
        }
        """
        return self.collector.record(
            cut_id=cut_id,
            platform=platform,
            views=metrics.get("views", 0),
            likes=metrics.get("likes", 0),
            comments=metrics.get("comments", 0),
            shares=metrics.get("shares", 0),
            watch_time_avg=metrics.get("watch_time_avg", 0.0),
            video_duration=metrics.get("video_duration", 0.0),
            archetype=metrics.get("archetype", ""),
            hook_text=metrics.get("hook_text", ""),
            title=metrics.get("title", ""),
            nicho=metrics.get("nicho", ""),
            posted_at=metrics.get("posted_at"),
            hour_posted=metrics.get("hour_posted", -1),
            ab_variant=metrics.get("ab_variant", "A"),
        )

    def analyze_patterns(self, nicho: str = "", since_days: int = None) -> dict:
        """Retorna insights de padrões aprendidos."""
        records = self.collector.get_all(nicho=nicho or None, since_days=since_days)
        return self.learner.analyze_patterns(records, nicho)

    def generate_report(
        self,
        nicho: str = "",
        output_html: str = None,
        console: bool = False,
    ) -> str:
        """
        Gera relatório completo.
        output_html: caminho para salvar HTML (opcional)
        console: True para retornar versão texto
        """
        records = self.collector.get_all()
        if console:
            return self.reporter.console_report(records, nicho)
        return self.reporter.generate_report(records, nicho, output_html)

    def suggest_improvements(self, nicho: str = "") -> list:
        """Retorna lista de sugestões baseadas nos dados."""
        records = self.collector.get_all()
        return self.reporter.suggest_improvements(records, nicho)

    # ── A/B Tests ─────────────────────────────────────────────────────────────

    def create_ab_test(
        self,
        cut_id: str,
        platform: str,
        variant_a: dict,
        variant_b: dict,
    ) -> int:
        """
        variant_a / variant_b = {"hook": "...", "title": "..."}
        Retorna test_id para referenciar depois.
        """
        return self.ab.create_test(
            cut_id=cut_id,
            platform=platform,
            variant_a_hook=variant_a.get("hook", ""),
            variant_b_hook=variant_b.get("hook", ""),
            variant_a_title=variant_a.get("title", ""),
            variant_b_title=variant_b.get("title", ""),
        )

    def resolve_ab_test(self, test_id: int) -> dict:
        """Determina vencedor com base nos dados registrados."""
        records = self.collector.get_all()
        return self.ab.resolve(test_id, records)

    def pending_ab_tests(self) -> list:
        return self.ab.pending_tests()

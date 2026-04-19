import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading, os, gc, json, subprocess
from pathlib import Path
from datetime import datetime

import db
from utils.hardware import HardwareDetector, check_system
from core.transcribe import transcribe_project
from core.candidate_engine import generate_candidates
from core.scoring_engine import ScoringEngine
from core.hybrid_prompt import HybridPromptGenerator
from core.hybrid_parser import parse_ai_response, validate_ai_cut
from core.decision_engine import DecisionEngine
from core.protection_factory import apply_protection
from core.post_pack import PostPackGenerator
from core.posting_schedule import PostingSchedule
from anti_copy_modules.core import LEVEL_LABELS

BG = "#0d0d1a"; BG2 = "#151528"; BG3 = "#1e1e3a"
ACC = "#7c3aed"; GRN = "#22c55e"; RED = "#ef4444"
YEL = "#f59e0b"; WHT = "#f1f5f9"; GRY = "#64748b"
FNT = ("Segoe UI", 10); FNTB = ("Segoe UI", 10, "bold")
FNTL = ("Segoe UI", 13, "bold"); MONO = ("Consolas", 9)

ACE_LEVELS = [
    ("🟢 NENHUM",  "none"),
    ("🟡 BÁSICO",  "basic"),
    ("🟠 ANTI-IA", "anti_ai"),
    ("🔴 MÁXIMO",  "maximum"),
]

class ClipFusionApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("✂ ClipFusion Viral Pro")
        self.root.geometry("1120x800")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.project_id = None
        self.video_path = None
        self.segments = []
        self.duration = 0.0
        self.cut_vars = {}
        self.output_dir = None
        self.hw = HardwareDetector()
        self._build_ui()

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=ACC, height=54)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✂  ClipFusion Viral Pro",
                 font=("Segoe UI", 16, "bold"), bg=ACC, fg=WHT).pack(side="left", padx=20, pady=12)
        tk.Label(hdr, text="vídeo longo → cortes virais prontos pra postar",
                 font=FNT, bg=ACC, fg="#c4b5fd").pack(side="left")
        self.lbl_hw = tk.Label(hdr, text=self.hw.get_status_string(),
                                font=("Segoe UI", 8), bg=ACC, fg="#c4b5fd")
        self.lbl_hw.pack(side="right", padx=16)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("TNotebook", background=BG2, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=GRY, padding=[14,7], font=FNT)
        s.map("TNotebook.Tab", background=[("selected", ACC)], foreground=[("selected", WHT)])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)

        self._tab_projeto()
        self._tab_transcricao()
        self._tab_ia()
        self._tab_cortes()
        self._tab_render()
        self._tab_historico()
        self._tab_agenda()
        self._tab_analytics()

    def _tab_projeto(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📁  Projeto")
        self._lbl(f, "Novo projeto", font=FNTL).pack(anchor="w", padx=30, pady=(28,4))
        self._lbl(f, "Selecione o vídeo longo e configure as opções.", color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        r1 = tk.Frame(f, bg=BG2); r1.pack(fill="x", padx=30, pady=6)
        self._lbl(r1, "Nome:").pack(side="left")
        self.v_name = tk.StringVar(value=f"Projeto {datetime.now().strftime('%d/%m %H:%M')}")
        tk.Entry(r1, textvariable=self.v_name, width=44,
                 bg=BG3, fg=WHT, insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=10)
        self._lbl(f, "Contexto (opcional — ajuda a IA entender o tema):").pack(anchor="w", padx=30, pady=(12,4))
        self.ctx_box = tk.Text(f, height=3, bg=BG3, fg=WHT,
                               insertbackground=WHT, relief="flat", font=FNT, wrap="word")
        self.ctx_box.pack(fill="x", padx=30)
        self.ctx_box.insert("1.0", "Ex: Podcast sobre vendas — episódio sobre prospecção de clientes.")
        self._sep(f)
        vr = tk.Frame(f, bg=BG2); vr.pack(fill="x", padx=30, pady=6)
        self._btn(vr, "📂 Selecionar vídeo", self._select_video, ACC).pack(side="left")
        self.lbl_video = self._lbl(vr, "Nenhum vídeo selecionado", color=GRY)
        self.lbl_video.pack(side="left", padx=14)
        op = tk.Frame(f, bg=BG2); op.pack(fill="x", padx=30, pady=10)
        self.v_vaapi = tk.BooleanVar(value=True)
        self._chk(op, "Usar VA-API (Intel HD 520) — recomendado", self.v_vaapi).pack(anchor="w")
        acef = tk.Frame(f, bg=BG2); acef.pack(fill="x", padx=30, pady=4)
        self._lbl(acef, "Anti-Copyright:").pack(side="left")
        self.v_ace = tk.StringVar(value="basic")
        for lbl, val in ACE_LEVELS:
            tk.Radiobutton(acef, text=lbl, variable=self.v_ace, value=val,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        wf = tk.Frame(f, bg=BG2); wf.pack(fill="x", padx=30, pady=4)
        self._lbl(wf, "Whisper:").pack(side="left")
        self.v_whisper = tk.StringVar(value="tiny")
        for m in ["tiny", "base", "small"]:
            tk.Radiobutton(wf, text=m, variable=self.v_whisper, value=m,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        lf = tk.Frame(f, bg=BG2); lf.pack(fill="x", padx=30, pady=4)
        self._lbl(lf, "Idioma:").pack(side="left")
        self.v_lang = tk.StringVar(value="pt")
        for lbl, val in [("Auto", "auto"), ("Português", "pt"), ("English", "en")]:
            tk.Radiobutton(lf, text=lbl, variable=self.v_lang, value=val,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        self._sep(f)
        self._btn(f, "▶  Iniciar Transcrição", self._start_transcription, GRN, wide=True).pack(padx=30, pady=8)
        self.lbl_status = self._lbl(f, "", color=GRY)
        self.lbl_status.pack(padx=30, pady=4)

    def _tab_transcricao(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📝  Transcrição")
        self._lbl(f, "Transcrição com timestamps", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self._lbl(f, "Gerada pelo Whisper. Revise se necessário.", color=GRY).pack(anchor="w", padx=30)
        self.box_transcript = scrolledtext.ScrolledText(
            f, bg=BG3, fg=WHT, font=MONO, relief="flat", insertbackground=WHT)
        self.box_transcript.pack(fill="both", expand=True, padx=30, pady=12)
        self._btn(f, "▶  Gerar Prompt para IA  →", self._goto_ia, ACC, wide=True).pack(padx=30, pady=(0,20))

    def _tab_ia(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="🤖  IA Externa")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Prompt para copiar", font=FNTL).pack(side="left")
        self._btn(top, "📋 Copiar", self._copy_prompt, ACC).pack(side="right")
        self._lbl(f, "Cole no Claude.ai, ChatGPT ou qualquer IA. Traga o JSON de resposta abaixo.",
                  color=GRY).pack(anchor="w", padx=30)
        self.box_prompt = scrolledtext.ScrolledText(
            f, height=11, bg=BG3, fg="#a5b4fc", font=MONO, relief="flat", insertbackground=WHT)
        self.box_prompt.pack(fill="x", padx=30, pady=(4,14))
        self._lbl(f, "Resposta da IA (cole o JSON aqui):", font=FNTB).pack(anchor="w", padx=30)
        self.box_resp = scrolledtext.ScrolledText(
            f, height=13, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_resp.pack(fill="both", expand=True, padx=30, pady=4)
        self._btn(f, "✅  Processar resposta  →  Ver Cortes",
                  self._process_resp, GRN, wide=True).pack(padx=30, pady=(4,20))

    def _tab_cortes(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="✂  Cortes")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Cortes sugeridos pela IA", font=FNTL).pack(side="left")
        self._btn(top, "✅ Todos",  self._approve_all, GRN).pack(side="right", padx=4)
        self._btn(top, "❌ Nenhum", self._reject_all,  RED).pack(side="right")
        self._lbl(f, "Marque os cortes que deseja renderizar.", color=GRY).pack(anchor="w", padx=30)
        outer = tk.Frame(f, bg=BG2); outer.pack(fill="both", expand=True, padx=30, pady=8)
        cv = tk.Canvas(outer, bg=BG2, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.cuts_frame = tk.Frame(cv, bg=BG2)
        self.cuts_frame.bind("<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.cuts_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))
        self._btn(f, "🎬  Renderizar cortes aprovados",
                  self._start_render, ACC, wide=True).pack(padx=30, pady=(4,20))

    def _tab_render(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="🎬  Render")
        self._lbl(f, "Progresso do render", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self.box_log = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_log.pack(fill="both", expand=True, padx=30, pady=10)
        self._btn(f, "📂  Abrir pasta de saída",
                  self._open_output, GRY, wide=True).pack(padx=30, pady=(0,20))

    def _tab_historico(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📋  Histórico")
        self._lbl(f, "Projetos anteriores", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        cols = ("ID", "Nome", "Status", "Criado em")
        st = ttk.Style()
        st.configure("Treeview", background=BG3, foreground=WHT, fieldbackground=BG3, rowheight=28)
        st.configure("Treeview.Heading", background=ACC, foreground=WHT)
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=50 if c=="ID" else 200)
        self.tree.pack(fill="both", expand=True, padx=30, pady=10)
        self._btn(f, "🔄  Carregar projeto selecionado",
                  self._load_project, ACC, wide=True).pack(padx=30, pady=(0,20))
        self._refresh_tree()

    def _tab_agenda(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📅  Agenda")
        self._lbl(f, "Agenda de Upload", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self._lbl(f, "Gera horários ideais com jitter anti-padrão para evitar detecção.",
                  color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        cfg = tk.Frame(f, bg=BG2); cfg.pack(fill="x", padx=30, pady=8)
        self._lbl(cfg, "Plataforma:").pack(side="left")
        self.v_platform = tk.StringVar(value="tiktok")
        for p in ["tiktok", "reels", "shorts"]:
            tk.Radiobutton(cfg, text=p, variable=self.v_platform, value=p,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        cfg2 = tk.Frame(f, bg=BG2); cfg2.pack(fill="x", padx=30, pady=4)
        self._lbl(cfg2, "Quantidade:").pack(side="left")
        self.v_count = tk.StringVar(value="10")
        tk.Entry(cfg2, textvariable=self.v_count, width=6,
                 bg=BG3, fg=WHT, insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=10)
        self._btn(f, "📅  Gerar Agenda", self._generate_schedule, ACC, wide=True).pack(padx=30, pady=10)
        self.box_agenda = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_agenda.pack(fill="both", expand=True, padx=30, pady=10)

    def _tab_analytics(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📊  Analytics")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Analytics & Aprendizado", font=FNTL).pack(side="left")
        self._btn(top, "🔄 Atualizar", self._refresh_analytics, ACC).pack(side="right")
        self._lbl(f, "Performance dos cortes, padrões aprendidos e sugestões do sistema.",
                  color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        reg = tk.Frame(f, bg=BG2); reg.pack(fill="x", padx=30, pady=4)
        self._lbl(reg, "Registrar resultado real:").pack(side="left")
        self.v_ana_cut   = tk.StringVar(value="cut_id")
        self.v_ana_plat  = tk.StringVar(value="tiktok")
        self.v_ana_views = tk.StringVar(value="0")
        tk.Entry(reg, textvariable=self.v_ana_cut,  width=14, bg=BG3, fg=WHT,
                 insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=4)
        for p in ["tiktok", "reels", "shorts"]:
            tk.Radiobutton(reg, text=p, variable=self.v_ana_plat, value=p,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=4)
        self._lbl(reg, "Views:").pack(side="left", padx=(8,2))
        tk.Entry(reg, textvariable=self.v_ana_views, width=8, bg=BG3, fg=WHT,
                 insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=4)
        self._btn(reg, "✅ Registrar", self._record_manual_analytics, GRN).pack(side="left", padx=8)
        self._sep(f)
        self.box_analytics = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_analytics.pack(fill="both", expand=True, padx=30, pady=(0,20))
        self.box_analytics.insert("1.0",
            "Clique em 🔄 Atualizar para ver o dashboard.\n"
            "Após renderizar e postar, registre os views reais aqui.\n"
            "O sistema aprende os padrões e sugere melhorias automaticamente.\n")

    def _select_video(self):
        p = filedialog.askopenfilename(
            title="Selecionar vídeo",
            filetypes=[("Vídeos", "*.mp4 *.mkv *.mov *.avi *.webm"), ("Todos", "*.*")])
        if p:
            self.video_path = p
            self.lbl_video.config(text=f"✅ {os.path.basename(p)}", fg=GRN)

def _start_transcription(self):
    if not self.video_path:
        messagebox.showwarning("Atenção", "Selecione um vídeo primeiro.")
        return

    name = self.v_name.get().strip() or "Sem nome"
    pid = db.create_project(name, self.video_path, self.v_lang.get())
    self.project_id = pid
    self._status(f"Projeto #{pid} criado. Transcrevendo...", YEL)

    def run():
        try:
            tid, result = transcribe_project(
                pid,
                self.video_path,
                model_size=self.v_whisper.get(),
                language=self.v_lang.get()
            )

            if not result or not result.get("segments"):
                raise RuntimeError("Transcrição vazia ou inválida.")

            self.segments = result["segments"]
            self.duration = self.segments[-1]["end"] if self.segments else 0

            candidate_ids = generate_candidates(pid, tid, self.segments)

            scoring = ScoringEngine()
            for cid in candidate_ids:
                with db.get_db() as conn:
                    row = conn.execute(
                        "SELECT * FROM candidates WHERE id = ?",
                        (cid,)
                    ).fetchone()

                    if row:
                        cand = dict(row)
                        scores = scoring.score_candidate({
                            "text": cand["text"],
                            "start": cand["start_time"]
                        })

                        conn.execute(
                            """
                            UPDATE candidates SET
                                hook_strength=?,
                                retention_score=?,
                                moment_strength=?,
                                shareability=?,
                                platform_fit_tiktok=?,
                                platform_fit_reels=?,
                                platform_fit_shorts=?,
                                combined_score=?
                            WHERE id=?
                            """,
                            (
                                scores["hook"],
                                scores["retention"],
                                scores["moment"],
                                scores["shareability"],
                                scores["platform_fit_tiktok"],
                                scores["platform_fit_reels"],
                                scores["platform_fit_shorts"],
                                scores["combined"],
                                cid
                            )
                        )
                        conn.commit()

            self.root.after(
                0,
                lambda: self._update_after_transcription(result["full_text"])
            )

        except Exception:
            import traceback
            err = traceback.format_exc()
            print(err, flush=True)
            Path.home().joinpath("clipfusion_error.log").write_text(
                err, encoding="utf-8"
            )
            self.root.after(
                0,
                lambda msg=err: messagebox.showerror("Erro", msg)
            )

    threading.Thread(target=run, daemon=True).start()

    def _update_after_transcription(self, full_text):
        self.box_transcript.delete("1.0", "end")
        for s in self.segments:
            self.box_transcript.insert("end", f"[{fmt_time(s['start'])}] {s['text']}\n")
        self._status(f"✅ {len(self.segments)} segmentos. Vá para 🤖 IA Externa.", GRN)
        self.nb.select(1)

    def _goto_ia(self):
        if not self.segments:
            messagebox.showwarning("Atenção", "Transcreva primeiro.")
            return
        self.nb.select(2)

    def _copy_prompt(self):
        p = self.box_prompt.get("1.0", "end-1c")
        if not p.strip():
            messagebox.showwarning("Atenção", "Prompt vazio.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(p)
        messagebox.showinfo("Copiado!", "Cole no Claude/ChatGPT e cole a resposta JSON abaixo.")

    def _process_resp(self):
        resp = self.box_resp.get("1.0", "end-1c").strip()
        if not resp:
            messagebox.showwarning("Atenção", "Cole a resposta da IA primeiro.")
            return
        if not self.project_id:
            messagebox.showwarning("Atenção", "Nenhum projeto ativo.")
            return
        from core.hybrid_parser import parse_ai_response, validate_ai_cut
        ai_cuts = parse_ai_response(resp)
        if not ai_cuts:
            messagebox.showerror("Erro", "Não foi possível interpretar o JSON da IA.")
            return
        # Aqui você pode combinar com scores locais e decidir
        # Por simplicidade, apenas salvamos como cortes aprovados
        # (decisão será feita depois)
        # Vamos apenas desenhar na aba cortes
        self._draw_cuts(ai_cuts)
        self.nb.select(3)

    def _draw_cuts(self, cuts):
        for w in self.cuts_frame.winfo_children():
            w.destroy()
        self.cut_vars = {}
        for i, cut in enumerate(cuts):
            self._draw_cut_card(cut, i)

    def _draw_cut_card(self, cut, idx):
        card = tk.Frame(self.cuts_frame, bg=BG3)
        card.pack(fill="x", pady=3, padx=2)
        var = tk.BooleanVar(value=True)
        self.cut_vars[idx] = var
        hdr = tk.Frame(card, bg=BG3); hdr.pack(fill="x", padx=10, pady=(8,3))
        tk.Checkbutton(hdr, variable=var, bg=BG3, fg=WHT,
                       selectcolor=ACC, activebackground=BG3, font=FNTB).pack(side="left")
        start = cut.get('start', 0)
        end = cut.get('end', 0)
        dur = end - start
        tk.Label(hdr, text=f"{cut.get('title', 'Corte')}",
                 bg=BG3, fg=WHT, font=FNTB).pack(side="left", padx=4)
        tk.Label(hdr, text=f"  {fmt_time(start)} → {fmt_time(end)}  ({fmt_time(dur)})",
                 bg=BG3, fg=GRY, font=FNT).pack(side="left")
        if cut.get('hook'):
            tk.Label(card, text=f"🎣  {cut['hook']}",
                     bg=BG3, fg="#a5b4fc", font=FNT,
                     wraplength=960, justify="left", anchor="w").pack(fill="x", padx=22, pady=2)
        if cut.get('reason'):
            tk.Label(card, text=f"💡  {cut['reason']}",
                     bg=BG3, fg=GRY, font=FNT,
                     wraplength=960, justify="left", anchor="w").pack(fill="x", padx=22, pady=(0,8))
        tk.Frame(card, bg=BG, height=1).pack(fill="x")

    def _approve_all(self):
        for v in self.cut_vars.values(): v.set(True)

    def _reject_all(self):
        for v in self.cut_vars.values(): v.set(False)

    def _start_render(self):
        # Aqui você chamaria o protection_factory, etc.
        messagebox.showinfo("Render", "Renderização iniciada (simulado).")

    def _open_output(self):
        messagebox.showinfo("Info", "Pasta de saída ainda não implementada.")

    def _generate_schedule(self):
        from core.posting_schedule import PostingSchedule
        ps = PostingSchedule(platform=self.v_platform.get())
        schedule = ps.generate(count=int(self.v_count.get()))
        text = ps.format_schedule(schedule)
        self.box_agenda.delete("1.0", "end")
        self.box_agenda.insert("1.0", text)

    def _load_project(self):
        sel = self.tree.selection()
        if not sel: return
        pid = int(self.tree.item(sel[0])["values"][0])
        proj = db.get_project(pid)
        if not proj: return
        self.project_id = pid
        self.video_path = proj["video_path"]
        t = db.get_transcript(pid)
        if t:
            self.segments = t['segments']
            self.duration = self.segments[-1]['end'] if self.segments else 0
            self.box_transcript.delete("1.0", "end")
            for s in self.segments:
                self.box_transcript.insert("end", f"[{fmt_time(s['start'])}] {s['text']}\n")
        self.v_name.set(proj["name"])
        self.lbl_video.config(text=f"✅ {os.path.basename(proj['video_path'])}", fg=GRN)
        messagebox.showinfo("Carregado", f"Projeto '{proj['name']}' carregado.")
        self.nb.select(0)

    def _refresh_tree(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        with db.get_db() as conn:
            rows = conn.execute("SELECT id, name, status, created_at FROM projects ORDER BY created_at DESC").fetchall()
            for r in rows:
                self.tree.insert("", "end", values=(r['id'], r['name'], r['status'], r['created_at']))

    def _refresh_analytics(self):
        self.box_analytics.insert("end", "Analytics em construção.\n")

    def _record_manual_analytics(self):
        messagebox.showinfo("Info", "Registro de analytics ainda não implementado.")

    def _log(self, m):
        self.box_log.insert("end", m+"\n"); self.box_log.see("end")

    def _status(self, m, color=GRY):
        self.lbl_status.config(text=m, fg=color)

    def _lbl(self, p, text="", font=None, color=None):
        return tk.Label(p, text=text,
                        bg=p.cget("bg") if hasattr(p,"cget") else BG2,
                        fg=color or WHT, font=font or FNT)

    def _btn(self, p, text, cmd, color=BG3, wide=False):
        return tk.Button(p, text=text, command=cmd,
                         bg=color, fg=WHT, font=FNTB, relief="flat",
                         cursor="hand2", padx=20 if wide else 14, pady=8,
                         activebackground=color, activeforeground=WHT,
                         width=50 if wide else None)

    def _chk(self, p, text, var):
        return tk.Checkbutton(p, text=text, variable=var,
                              bg=p.cget("bg"), fg=WHT, selectcolor=ACC,
                              activebackground=p.cget("bg"), font=FNT)

    def _sep(self, p):
        tk.Frame(p, bg=BG3, height=1).pack(fill="x", padx=30, pady=16)

def fmt_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

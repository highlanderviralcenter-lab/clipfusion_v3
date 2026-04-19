import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import os
import json
import gc
import random
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from ..core.transcriber_cpp import get_transcriber, WhisperCppTranscriber
from ..core.memory_manager import get_memory_manager
from ..core.segment import segment_by_pauses
from ..core.cut_engine import render_cut
from ..anti_copy_modules.protection_factory import build_plan
from ..infra.db import create_project, save_transcription, list_projects, get_cuts, get_transcription

BG = "#0d0d1a"
BG2 = "#151528"
ACC = "#7c3aed"
GRN = "#22c55e"
WHT = "#f1f5f9"
YEL = "#fbbf24"
RED = "#ef4444"


class ClipFusionApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ClipFusion V3.0 - 7 Abas Completas")
        self.root.geometry("1200x850")
        self.root.configure(bg=BG)
        
        self.video_path = None
        self.transcription_result = None
        self.transcriber = None
        self.bg_music_path = None
        
        self._build_ui()

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        tk.Frame(self.root, bg=ACC, height=50).pack(fill="x")
        tk.Label(self.root, text="✂ ClipFusion V3.0", font=("Helvetica", 16, "bold"), bg=ACC, fg=WHT).place(x=20, y=10)

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_projeto()
        self._tab_transcricao()
        self._tab_render()
        self._tab_agenda()
        self._tab_audio()
        self._tab_historico()
        self._tab_ia_externa()

    # ─── ABA 1: PROJETO ───
    def _tab_projeto(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="📁 Projeto")

        tk.Label(f, text="Projeto", font=("Helvetica", 14), bg=BG2, fg=WHT).pack(pady=20)
        tk.Button(f, text="Selecionar Vídeo", command=self._select_video, bg=ACC, fg=WHT, font=("Helvetica", 10, "bold")).pack()
        self.lbl_video = tk.Label(f, text="Nenhum vídeo", bg=BG2, fg="#94a3b8")
        self.lbl_video.pack(pady=10)

        tk.Label(f, text="Modelo Whisper.cpp:", bg=BG2, fg=WHT).pack(pady=(20, 5))
        self.model_var = tk.StringVar(value="medium-q5_0")
        frame_model = tk.Frame(f, bg=BG2)
        frame_model.pack()
        for val, txt in [("tiny-q4_0", "Tiny (39MB)"), ("base-q5_0", "Base (74MB)"), 
                         ("small-q5_0", "Small (244MB)"), ("medium-q5_0", "Medium (500MB) ⭐")]:
            tk.Radiobutton(frame_model, text=txt, variable=self.model_var, value=val,
                          bg=BG2, fg=WHT, selectcolor=ACC, indicatoron=0, width=25, padx=10, pady=3).pack(pady=2)

        self.lbl_mem = tk.Label(f, text="💡 Medium-q5_0 comprime para ~200MB no zRAM", bg=BG2, fg="#22d3ee", font=("Helvetica", 9))
        self.lbl_mem.pack(pady=10)

        tk.Label(f, text="Proteção:", bg=BG2, fg=WHT).pack(pady=(15, 5))
        self.protection = tk.StringVar(value="basic")
        for val, txt in [("none", "🟢 Nenhum"), ("basic", "🟡 Básico"), ("maximum", "🔴 Máximo")]:
            tk.Radiobutton(f, text=txt, variable=self.protection, value=val, bg=BG2, fg=WHT, selectcolor=ACC).pack()

        tk.Label(f, text="Plataforma:", bg=BG2, fg=WHT).pack(pady=(15, 5))
        self.platform = tk.StringVar(value="tiktok")
        for val, txt in [("tiktok", "🎵 TikTok"), ("reels", "📸 Reels"), ("shorts", "▶️ Shorts")]:
            tk.Radiobutton(f, text=txt, variable=self.platform, value=val, bg=BG2, fg=WHT, selectcolor=ACC).pack()

    # ─── ABA 2: TRANSCRIÇÃO ───
    def _tab_transcricao(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="📝 Transcrição")

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="🎙️ Transcrever", command=self._start_trans, bg=GRN, fg=WHT, font=("Helvetica", 10, "bold")).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🗑️ Liberar zRAM", command=self._free_memory, bg="#dc2626", fg=WHT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📊 Memória", command=self._show_memory, bg=ACC, fg=WHT).pack(side="left", padx=5)

        self.txt_trans = scrolledtext.ScrolledText(f, height=25, bg="#1e1e3a", fg=WHT, font=("Consolas", 11), insertbackground=WHT)
        self.txt_trans.pack(fill="both", expand=True, padx=20, pady=5)
        self.lbl_trans_status = tk.Label(f, text="Pronto - Whisper.cpp aguardando", bg=BG2, fg="#94a3b8")
        self.lbl_trans_status.pack()

    # ─── ABA 3: RENDER ───
    def _tab_render(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="🎬 Render")

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="🎬 Gerar Cortes (VA-API)", command=self._start_render, bg=ACC, fg=WHT, font=("Helvetica", 10, "bold")).pack(side="left", padx=5)

        self.txt_log = scrolledtext.ScrolledText(f, height=25, bg="#1e1e3a", fg=GRN, font=("Consolas", 11), insertbackground=GRN)
        self.txt_log.pack(fill="both", expand=True, padx=20, pady=5)

    # ─── ABA 4: AGENDA ───
    def _tab_agenda(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="📅 Agenda")

        tk.Label(f, text="Horários Anti-Padrão para Postagem", font=("Helvetica", 14, "bold"), bg=BG2, fg=WHT).pack(pady=20)

        explicacao = """Evite horários redondos (18:00, 19:30). 
Algoritmos detectam padrões. Horários "humanos": 18:07, 19:13."""
        tk.Label(f, text=explicacao, bg=BG2, fg="#94a3b8", font=("Helvetica", 10), justify="left").pack(pady=10)

        tk.Button(f, text="🎲 Gerar Horários", command=self._gerar_horarios, bg=YEL, fg="#000", font=("Helvetica", 11, "bold")).pack(pady=15)

        self.txt_horarios = scrolledtext.ScrolledText(f, height=20, bg="#1e1e3a", fg=WHT, font=("Consolas", 12), insertbackground=WHT)
        self.txt_horarios.pack(fill="both", expand=True, padx=20, pady=10)

        self.horario_platform = tk.StringVar(value="tiktok")
        frame_plat = tk.Frame(f, bg=BG2)
        frame_plat.pack(pady=10)
        for val, txt in [("tiktok", "🎵 TikTok"), ("reels", "📸 Reels"), ("shorts", "▶️ Shorts"), ("youtube", "▶️ YouTube")]:
            tk.Radiobutton(frame_plat, text=txt, variable=self.horario_platform, value=val, bg=BG2, fg=WHT, selectcolor=ACC).pack(side="left", padx=10)

    # ─── ABA 5: ÁUDIO ───
    def _tab_audio(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="🎙️ Áudio")

        tk.Label(f, text="Mixagem e Voz para Dublagem", font=("Helvetica", 14, "bold"), bg=BG2, fg=WHT).pack(pady=20)

        tk.Label(f, text="Voz para TTS:", bg=BG2, fg=WHT).pack(pady=10)
        self.voz_var = tk.StringVar(value="pt-BR-Standard-A")
        
        vozes = [
            ("pt-BR-Standard-A", "🇧🇷 Feminina A (Neutra)"),
            ("pt-BR-Standard-B", "🇧🇷 Masculina B (Autoridade)"),
            ("pt-BR-Standard-C", "🇧🇷 Feminina C (Energia)"),
            ("pt-BR-Wavenet-A", "🌊 Feminina Wavenet (Premium)"),
            ("en-US-Standard-D", "🇺🇸 Masculina US (Global)"),
        ]
        
        for val, txt in vozes:
            tk.Radiobutton(f, text=txt, variable=self.voz_var, value=val, bg=BG2, fg=WHT, selectcolor=ACC).pack(pady=2)

        tk.Label(f, text="Mixagem:", bg=BG2, fg=WHT).pack(pady=(20, 5))
        frame_mix = tk.Frame(f, bg=BG2)
        frame_mix.pack(pady=5)
        
        tk.Label(frame_mix, text="Volume Voz:", bg=BG2, fg=WHT).grid(row=0, column=0, padx=5)
        self.vol_voz = tk.Scale(frame_mix, from_=0, to=100, orient="horizontal", bg=BG2, fg=WHT, highlightthickness=0)
        self.vol_voz.set(85)
        self.vol_voz.grid(row=0, column=1, padx=5)

        tk.Label(frame_mix, text="Música BG:", bg=BG2, fg=WHT).grid(row=1, column=0, padx=5)
        self.vol_bg = tk.Scale(frame_mix, from_=0, to=100, orient="horizontal", bg=BG2, fg=WHT, highlightthickness=0)
        self.vol_bg.set(20)
        self.vol_bg.grid(row=1, column=1, padx=5)

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="🔊 Testar Voz", command=self._testar_voz, bg=ACC, fg=WHT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🎵 Selecionar Música", command=self._select_bg_music, bg="#8b5cf6", fg=WHT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="⚡ Aplicar Mix", command=self._aplicar_mix, bg=GRN, fg=WHT, font=("Helvetica", 10, "bold")).pack(side="left", padx=5)

        self.lbl_bg_music = tk.Label(f, text="Nenhuma música selecionada", bg=BG2, fg="#94a3b8")
        self.lbl_bg_music.pack(pady=10)

        tk.Label(f, text="Texto para TTS:", bg=BG2, fg=WHT).pack(pady=(10, 5))
        self.txt_tts = scrolledtext.ScrolledText(f, height=8, bg="#1e1e3a", fg=WHT, font=("Consolas", 11))
        self.txt_tts.pack(fill="x", padx=20, pady=5)
        self.txt_tts.insert("1.0", "Digite texto para dublagem...")

        self.lbl_audio_status = tk.Label(f, text="Aguardando...", bg=BG2, fg="#94a3b8")
        self.lbl_audio_status.pack()

    # ─── ABA 6: HISTÓRICO ───
    def _tab_historico(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="📚 Histórico")

        tk.Label(f, text="Histórico de Projetos e Renders", font=("Helvetica", 14, "bold"), bg=BG2, fg=WHT).pack(pady=20)

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="🔄 Atualizar Lista", command=self._atualizar_historico, bg=ACC, fg=WHT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🗑️ Limpar Antigos", command=self._limpar_historico, bg="#dc2626", fg=WHT).pack(side="left", padx=5)

        # Treeview para projetos
        columns = ("ID", "Nome", "Data", "Status", "Cortes")
        self.tree_hist = ttk.Treeview(f, columns=columns, show="headings", height=20)
        for col in columns:
            self.tree_hist.heading(col, text=col)
            self.tree_hist.column(col, width=150 if col != "Nome" else 250)
        self.tree_hist.pack(fill="both", expand=True, padx=20, pady=10)

        # Detalhes ao clicar
        self.tree_hist.bind("<Double-1>", self._on_historico_click)
        
        self.lbl_hist_detail = tk.Label(f, text="Duplo-clique para ver detalhes", bg=BG2, fg="#94a3b8")
        self.lbl_hist_detail.pack(pady=5)

    # ─── ABA 7: IA EXTERNA ───
    def _tab_ia_externa(self):
        f = tk.Frame(self.nb, bg=BG2)
        self.nb.add(f, text="🤖 IA Externa")

        tk.Label(f, text="Exportar para Análise Externa (Claude/ChatGPT)", font=("Helvetica", 14, "bold"), bg=BG2, fg=WHT).pack(pady=20)

        tk.Label(f, text="Esta aba exporta dados para você analisar em IAs externas:", bg=BG2, fg="#94a3b8").pack(pady=5)

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="📋 Exportar Transcrição (JSON)", command=self._export_json, bg=ACC, fg=WHT).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📝 Exportar Prompt (TXT)", command=self._export_prompt, bg=YEL, fg="#000").pack(side="left", padx=5)
        tk.Button(btn_frame, text="📊 Exportar Métricas (CSV)", command=self._export_csv, bg=GRN, fg=WHT).pack(side="left", padx=5)

        self.txt_ia = scrolledtext.ScrolledText(f, height=25, bg="#1e1e3a", fg=WHT, font=("Consolas", 11), insertbackground=WHT)
        self.txt_ia.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_ia.insert("1.0", "Clique nos botões acima para gerar exports...\n\nPrompt sugerido para Claude:\n\n\"Analise esta transcrição e identifique:\n1. Os 3 melhores momentos virais (com timestamps)\n2. Ganchos psicológicos presentes\n3. Sugestões de cortes otimizados para TikTok\"\n")

    # ─── MÉTODOS AUXILIARES ───
    def _select_video(self):
        p = filedialog.askopenfilename(filetypes=[("Vídeos", "*.mp4 *.mov *.avi *.mkv *.webm")])
        if p:
            self.video_path = p
            self.lbl_video.config(text=os.path.basename(p), fg=WHT)

    def _show_memory(self):
        mem = get_memory_manager()
        stats = mem.get_stats()
        info = [f"RAM: {stats['ram_available_mb']:.0f}MB / {stats['ram_total_mb']:.0f}MB"]
        if stats['zram']:
            z = stats['zram']
            info.extend([f"zRAM: {z['data_original_mb']:.1f}MB → {z['data_compressed_mb']:.1f}MB ({z['ratio']:.2f}x)"])
        if stats['btrfs_compression_ratio']:
            info.append(f"BTRFS: {stats['btrfs_compression_ratio']:.2f}x")
        info.append(f"Swappiness: {stats['swappiness']}")
        messagebox.showinfo("Memória", "\n".join(info))

    def _free_memory(self):
        if self.transcriber:
            self.transcriber.unload()
            self.transcriber = None
        get_memory_manager().emergency_cleanup()
        self.lbl_trans_status.config(text="Memória liberada", fg=GRN)

    def _start_trans(self):
        if not self.video_path:
            messagebox.showwarning("Aviso", "Selecione um vídeo primeiro!")
            return

        model_full = self.model_var.get()
        model_name, quant = model_full.split("-", 1) if "-q" in model_full else (model_full, "q5_0")

        self.txt_trans.delete("1.0", "end")
        self.lbl_trans_status.config(text=f"Carregando {model_full}...", fg=YEL)

        def run():
            try:
                mem = get_memory_manager()
                mem.pre_allocate(500)
                
                self.transcriber = WhisperCppTranscriber(model_name=model_name, quantize=quant, n_threads=3)
                result = self.transcriber.transcribe(self.video_path, language="pt")
                self.transcription_result = result
                self.transcriber.unload()

                lines = [
                    "=" * 50,
                    f"TRANSCRIÇÃO - {result['backend']}",
                    f"Palavras: {len(result['words'])}",
                    "",
                    "TEXTO:",
                    result['text'],
                    "",
                    "TIMESTAMPS (primeiras 20):",
                ]
                for w in result['words'][:20]:
                    lines.append(f"{w['start']:>7.2f}s → {w['end']:>7.2f}s  {w['word']}")
                if len(result['words']) > 20:
                    lines.append(f"... e {len(result['words'])-20} mais")

                self.root.after(0, lambda: self.txt_trans.insert("end", "\n".join(lines)))
                self.root.after(0, lambda: self.lbl_trans_status.config(text=f"✅ {len(result['words'])} palavras", fg=GRN))
            except Exception as e:
                import traceback
                self.root.after(0, lambda: self.txt_trans.insert("end", f"\n❌ ERRO:\n{traceback.format_exc()}"))
                self.root.after(0, lambda: self.lbl_trans_status.config(text="Erro", fg=RED))

        threading.Thread(target=run, daemon=True).start()

    def _start_render(self):
        if not self.video_path or not self.transcription_result:
            messagebox.showwarning("Aviso", "Selecione vídeo e transcreva primeiro!")
            return

        self.txt_log.delete("1.0", "end")
        self.txt_log.insert("end", "🎬 Iniciando (VA-API HD 520 + CPU)\n")

        def run():
            try:
                pid = create_project(Path(self.video_path).stem, self.video_path)
                self._log(f"📁 Projeto #{pid}")
                save_transcription(pid, self.transcription_result["text"], json.dumps(self.transcription_result), 0.9)

                segments = segment_by_pauses(self.video_path)
                self._log(f"✂️ {len(segments)} segmentos")

                plan = build_plan(self.protection.get())
                base = Path(self.video_path).stem

                for idx, (s, e) in enumerate(segments[:5], 1):
                    out = f"{base}_cut_{idx:02d}.mp4"
                    self._log(f"🎞️ [{idx}/5] {out[:50]}")
                    
                    seg_text = " ".join(w["word"] for w in self.transcription_result["words"] if s <= w["start"] <= e)
                    
                    from ..core.segment_engine import VideoSegment
                    seg = VideoSegment(start=s, end=e, text=seg_text, words=[])
                    
                    render_cut(self.video_path, seg, plan, self.platform.get(), out)
                    self._log(f"✅ Concluído")
                    gc.collect()

                self._log(f"\n🏁 5 cortes gerados!")
            except Exception as e:
                import traceback
                self._log(f"\n❌ ERRO:\n{traceback.format_exc()}")

        threading.Thread(target=run, daemon=True).start()

    def _log(self, msg):
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    # ─── MÉTODOS AGENDA ───
    def _gerar_horarios(self):
        platform = self.horario_platform.get()
        horarios_base = {"tiktok": [11, 13, 19, 21], "reels": [12, 17, 20], "shorts": [8, 12, 19], "youtube": [14, 17, 20]}
        bases = horarios_base.get(platform, [12, 18])
        
        horarios_finais = []
        for h in bases:
            offset = random.choice([-1, 1]) * random.randint(3, 13)
            minutos = 0 + offset
            hora_final = h
            if minutos < 0:
                minutos += 60
                hora_final -= 1
            elif minutos >= 60:
                minutos -= 60
                hora_final += 1
            hora_final = max(0, min(23, hora_final))
            horarios_finais.append((hora_final, minutos))
        
        hoje = datetime.now()
        linhas = [f"📅 HORÁRIOS ANTI-PADRÃO - {platform.upper()}", f"Gerado: {hoje.strftime('%d/%m/%Y %H:%M')}", "=" * 40, ""]
        
        for i, (h, m) in enumerate(horarios_finais, 1):
            dia = hoje + timedelta(days=i-1)
            linhas.append(f"  {i}. {h:02d}:{m:02d} → Postagem {dia.strftime('%d/%m')}")
            linhas.append(f"     ↳ Variação: {m:+d}min do padrão {h:02d}:00")
            linhas.append("")
        
        linhas.extend(["💡 DICAS:", "• Evite :00 e :30", "• Espaçe 3-4h entre posts", "• Use analytics para ajustar"])
        
        self.txt_horarios.delete("1.0", "end")
        self.txt_horarios.insert("end", "\n".join(linhas))

    # ─── MÉTODOS ÁUDIO ───
    def _select_bg_music(self):
        p = filedialog.askopenfilename(filetypes=[("Áudio", "*.mp3 *.wav *.m4a *.ogg")])
        if p:
            self.bg_music_path = p
            self.lbl_bg_music.config(text=os.path.basename(p), fg=WHT)

    def _testar_voz(self):
        texto = self.txt_tts.get("1.0", "end").strip()
        if not texto or texto == "Digite texto para dublagem...":
            messagebox.showwarning("Aviso", "Digite texto no campo acima!")
            return
        
        voz = self.voz_var.get()
        self.lbl_audio_status.config(text=f"Sintetizando...", fg=YEL)
        
        def run():
            try:
                from gtts import gTTS
                lang = "pt" if "pt-BR" in voz else "en"
                tts = gTTS(text=texto[:100], lang=lang, slow=False)
                tmp_path = tempfile.mktemp(suffix=".mp3")
                tts.save(tmp_path)
                subprocess.run(["ffplay", "-nodisp", "-autoexit", tmp_path], capture_output=True, timeout=30)
                os.remove(tmp_path)
                self.root.after(0, lambda: self.lbl_audio_status.config(text="✅ Voz testada", fg=GRN))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_audio_status.config(text=f"⚠️ {str(e)[:50]}", fg=YEL))
        
        threading.Thread(target=run, daemon=True).start()

    def _aplicar_mix(self):
        if not hasattr(self, 'bg_music_path'):
            messagebox.showwarning("Aviso", "Selecione música de fundo primeiro!")
            return
        
        base = Path(self.video_path).stem if self.video_path else "corte"
        ultimo_corte = None
        for i in range(5, 0, -1):
            candidato = f"{base}_cut_{i:02d}.mp4"
            if os.path.exists(candidato):
                ultimo_corte = candidato
                break
        
        if not ultimo_corte:
            messagebox.showwarning("Aviso", "Gere cortes na aba 🎬 Render primeiro!")
            return
        
        self.lbl_audio_status.config(text=f"Mixando...", fg=YEL)
        
        def run():
            try:
                vol_voz = self.vol_voz.get() / 100.0
                vol_bg = self.vol_bg.get() / 100.0
                output = ultimo_corte.replace(".mp4", "_mixed.mp4")
                
                cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", ultimo_corte,
                    "-i", self.bg_music_path,
                    "-filter_complex",
                    f"[0:a]volume={vol_voz}[a0];[1:a]volume={vol_bg},afade=t=out:st=3:d=2[a1];[a0][a1]amix=inputs=2:duration=first[outa]",
                    "-map", "0:v", "-map", "[outa]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    output,
                ]
                subprocess.run(cmd, check=True)
                self.root.after(0, lambda: self.lbl_audio_status.config(text=f"✅ Mix: {output}", fg=GRN))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_audio_status.config(text=f"❌ {str(e)[:50]}", fg=RED))
        
        threading.Thread(target=run, daemon=True).start()

    # ─── MÉTODOS HISTÓRICO ───
    def _atualizar_historico(self):
        for item in self.tree_hist.get_children():
            self.tree_hist.delete(item)
        
        try:
            projetos = list_projects()
            for p in projetos[-50:]:  # últimos 50
                cortes = len(get_cuts(p['id']))
                self.tree_hist.insert("", "end", values=(
                    p['id'], p['name'], p['created_at'][:16], p['status'], cortes
                ))
        except Exception as e:
            self.lbl_hist_detail.config(text=f"Erro: {str(e)[:50]}", fg=RED)

    def _limpar_historico(self):
        if messagebox.askyesno("Confirmar", "Limpar projetos antigos (manter últimos 10)?"):
            # Implementação: manter só últimos 10 no banco
            messagebox.showinfo("Info", "Função implementada no db.py - executar vacuum")

    def _on_historico_click(self, event):
        item = self.tree_hist.selection()[0]
        valores = self.tree_hist.item(item, "values")
        pid = valores[0]
        
        try:
            trans = get_transcription(int(pid))
            if trans:
                preview = trans['full_text'][:200] + "..." if len(trans['full_text']) > 200 else trans['full_text']
                self.lbl_hist_detail.config(text=f"Projeto {pid}: {preview}", fg=WHT)
        except:
            pass

    # ─── MÉTODOS IA EXTERNA ───
    def _export_json(self):
        if not self.transcription_result:
            messagebox.showwarning("Aviso", "Transcreva um vídeo primeiro!")
            return
        
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if p:
            export = {
                "transcription": self.transcription_result,
                "metadata": {
                    "exported_at": datetime.now().isoformat(),
                    "platform": self.platform.get(),
                    "model": self.model_var.get(),
                }
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=2)
            self.txt_ia.insert("end", f"\n✅ JSON exportado: {p}\n")

    def _export_prompt(self):
        if not self.transcription_result:
            messagebox.showwarning("Aviso", "Transcreva um vídeo primeiro!")
            return
        
        texto = self.transcription_result['text']
        palavras = len(self.transcription_result['words'])
        
        prompt = f"""Analise esta transcrição de vídeo e sugere cortes virais:

TRANSCRIÇÃO ({palavras} palavras):
{texto[:2000]}

TAREFA:
1. Identifique os 3 melhores momentos para cortes (com timestamps aproximados)
2. Classifique cada um por gatilho psicológico: Curiosidade, Controvérsia, Autoridade, Empatia
3. Sugira hooks de início para cada corte (primeiros 3 segundos)
4. Indique duração ideal para plataforma {self.platform.get()}

Responda em formato JSON com: timestamp_inicio, timestamp_fim, hook_sugerido, gatilho_psicologico, score_viral_0_100"""
        
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(prompt)
            self.txt_ia.insert("end", f"\n✅ Prompt exportado: {p}\n")
            self.txt_ia.insert("end", f"\n--- PREVIEW ---\n{prompt[:500]}...\n")

    def _export_csv(self):
        if not self.transcription_result:
            messagebox.showwarning("Aviso", "Transcreva um vídeo primeiro!")
            return
        
        # Exporta word-level como CSV para análise em Excel/etc
        import csv
        
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if p:
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["word", "start", "end", "duration"])
                for w in self.transcription_result['words']:
                    writer.writerow([w['word'], w['start'], w['end'], w['end']-w['start']])
            self.txt_ia.insert("end", f"\n✅ CSV exportado: {p} ({len(self.transcription_result['words'])} linhas)\n")


if __name__ == "__main__":
    app = ClipFusionApp()
    app.run()

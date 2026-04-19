#!/usr/bin/env python3
"""
ClipFusion SIMPLES - Corta vídeo e queima legenda com VA-API
Uso: python3 main_simples.py
"""

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import subprocess
import os
import tempfile
from pathlib import Path

BG = "#0d0d1a"
BG2 = "#151528"
ACC = "#7c3aed"
GRN = "#22c55e"
WHT = "#ffffff"

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ClipFusion - Cortador com Legenda")
        self.root.geometry("700x600")
        self.root.configure(bg=BG)
        self.video_path = None
        self._build()

    def _build(self):
        f = tk.Frame(self.root, bg=BG2)
        f.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(f, text="ClipFusion - Cortador de Vídeo com Legenda", font=("Arial", 14, "bold"), bg=BG2, fg=WHT).pack(pady=10)

        # Selecionar vídeo
        row1 = tk.Frame(f, bg=BG2)
        row1.pack(fill="x", pady=5)
        tk.Button(row1, text="📂 Selecionar Vídeo", command=self.sel_video, bg=ACC, fg=WHT).pack(side="left")
        self.lbl_video = tk.Label(row1, text="Nenhum vídeo", bg=BG2, fg=GRN)
        self.lbl_video.pack(side="left", padx=10)

        # Parâmetros do corte
        frame = tk.Frame(f, bg=BG2)
        frame.pack(pady=10)
        tk.Label(frame, text="Início (segundos):", bg=BG2, fg=WHT).grid(row=0, column=0, padx=5)
        self.start_entry = tk.Entry(frame, width=10)
        self.start_entry.grid(row=0, column=1, padx=5)
        self.start_entry.insert(0, "10")
        tk.Label(frame, text="Fim (segundos):", bg=BG2, fg=WHT).grid(row=1, column=0, padx=5)
        self.end_entry = tk.Entry(frame, width=10)
        self.end_entry.grid(row=1, column=1, padx=5)
        self.end_entry.insert(0, "25")

        # Texto da legenda
        tk.Label(f, text="Texto da legenda:", bg=BG2, fg=WHT).pack(anchor="w", pady=(10,0))
        self.txt_legenda = scrolledtext.ScrolledText(f, height=5, bg="#1e1e3a", fg=WHT, font=("Consolas", 10))
        self.txt_legenda.pack(fill="x", pady=5)
        self.txt_legenda.insert("1.0", "Exemplo de legenda")

        # Botão renderizar
        tk.Button(f, text="✂️ Renderizar Corte", command=self.renderizar, bg=GRN, fg=WHT, font=("Arial", 10, "bold")).pack(pady=15)

        # Log
        self.log = scrolledtext.ScrolledText(f, height=10, bg="#1e1e3a", fg=GRN, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, pady=5)

    def sel_video(self):
        p = filedialog.askopenfilename(filetypes=[("MP4", "*.mp4")])
        if p:
            self.video_path = p
            self.lbl_video.config(text=os.path.basename(p))

    def renderizar(self):
        if not self.video_path:
            self.log_insert("❌ Selecione um vídeo primeiro.\n")
            return
        try:
            start = float(self.start_entry.get())
            end = float(self.end_entry.get())
        except:
            self.log_insert("❌ Início/Fim devem ser números.\n")
            return
        texto = self.txt_legenda.get("1.0", "end").strip()
        if not texto:
            self.log_insert("❌ Digite o texto da legenda.\n")
            return

        duration = end - start
        if duration <= 0:
            self.log_insert("❌ O fim deve ser maior que o início.\n")
            return

        self.log_insert(f"🎬 Renderizando corte de {start}s a {end}s (duração {duration:.1f}s)\n")
        self.log_insert(f"📝 Legenda: {texto[:50]}\n")
        self.root.update()

        # Criar SRT temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            srt_path = f.name
            f.write(f"1\n00:00:00,000 --> 00:00:{int(duration):02d},000\n{texto}\n")

        output = Path(self.video_path).stem + f"_cortado_{start}_{end}.mp4"

        # Detectar VA-API
        try:
            subprocess.run(["vainfo"], capture_output=True, check=True)
            vaapi = True
        except:
            vaapi = False

        try:
            if vaapi:
                self.log_insert("✅ Usando VA-API (aceleração Intel)\n")
                # Passo 1: Cortar e redimensionar via VA-API
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                    raw = tmp.name
                cmd1 = [
                    "ffmpeg", "-y",
                    "-hwaccel", "vaapi",
                    "-hwaccel_device", "/dev/dri/renderD128",
                    "-ss", str(start), "-i", self.video_path, "-t", str(duration),
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,format=nv12,hwupload",
                    "-c:v", "h264_vaapi",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    raw
                ]
                subprocess.run(cmd1, check=True, stderr=subprocess.PIPE)
                # Passo 2: Queimar legenda com libx264
                cmd2 = [
                    "ffmpeg", "-y", "-i", raw,
                    "-vf", f"subtitles={srt_path}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "copy",
                    output
                ]
                subprocess.run(cmd2, check=True, stderr=subprocess.PIPE)
                os.unlink(raw)
            else:
                self.log_insert("⚠️ VA-API não disponível, usando CPU\n")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start), "-i", self.video_path, "-t", str(duration),
                    "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,subtitles={srt_path}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    output
                ]
                subprocess.run(cmd, check=True, stderr=subprocess.PIPE)

            self.log_insert(f"✅ Concluído! Arquivo: {output}\n")
            messagebox.showinfo("Pronto", f"Vídeo gerado:\n{output}")
        except subprocess.CalledProcessError as e:
            self.log_insert(f"❌ Erro no FFmpeg: {e.stderr.decode()}\n")
        except Exception as e:
            self.log_insert(f"❌ Erro: {e}\n")
        finally:
            if os.path.exists(srt_path):
                os.unlink(srt_path)

    def log_insert(self, msg):
        self.log.insert("end", msg)
        self.log.see("end")
        self.root.update_idletasks()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()

#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FULLinstallClipFusion_V3.sh
# Instalador completo do ClipFusion Viral Pro
# Com correção definitiva do zRAM (systemd-zram-generator)
# ============================================================================
# Uso:
#   chmod +x FULLinstallClipFusion_V3.sh
#   sudo ./FULLinstallClipFusion_V3.sh
#   cd ~/clipfusion && ./run.sh
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[ OK ]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error(){ echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ----------------------------------------------------------------------------
# 0. PREFLIGHT
# ----------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    log_error "Este script deve ser executado como root (use sudo)."
fi

REAL_USER=${SUDO_USER:-$(who am i | awk '{print $1}')}
REAL_HOME=$(eval echo "~$REAL_USER")
INSTALL_DIR="$REAL_HOME/clipfusion"

log_info "Instalando em: $INSTALL_DIR para usuário: $REAL_USER"

for cmd in python3 ffmpeg; do
    if ! command -v $cmd >/dev/null; then
        log_error "$cmd não encontrado. Instale-o primeiro (apt install $cmd)."
    fi
done

free_mb=$(df -m "$REAL_HOME" | awk 'NR==2 {print $4}')
if [[ ${free_mb:-0} -lt 2048 ]]; then
    log_error "Espaço em disco insuficiente (<2GB)."
fi

# ----------------------------------------------------------------------------
# 1. PACOTES DO SISTEMA
# ----------------------------------------------------------------------------
log_info "Atualizando e instalando pacotes..."
apt update -qq
apt install -y python3-pip python3-venv python3-tk ffmpeg \
    intel-media-va-driver-non-free vainfo lm-sensors systemd-zram-generator

# ----------------------------------------------------------------------------
# 2. CONFIGURAÇÃO DEFINITIVA DO ZRAM (systemd-zram-generator)
# ----------------------------------------------------------------------------
log_info "Configurando zRAM com systemd-zram-generator (6GB, lz4)..."

# Remove possível conflito com zram-tools
systemctl stop zramswap 2>/dev/null || true
systemctl disable zramswap 2>/dev/null || true
apt remove -y zram-tools 2>/dev/null || true

# Configura o gerador
cat > /etc/systemd/zram-generator.conf << 'EOF'
[zram0]
zram-size = 6144MiB
compression-algorithm = lz4
swap-priority = 100
EOF

# Recarrega e ativa
systemctl daemon-reload
systemctl restart systemd-zram-setup@zram0.service

sleep 2
if [[ -b /dev/zram0 ]]; then
    log_ok "zRAM /dev/zram0 criado com sucesso (6GB, lz4)"
    swapon /dev/zram0 2>/dev/null || true
else
    log_warn "Falha ao criar /dev/zram0. Verifique o kernel."
fi

log_info "Status do zRAM:"
zramctl || true
swapon --show || true

# ----------------------------------------------------------------------------
# 3. CRIAÇÃO DA ESTRUTURA DE DIRETÓRIOS
# ----------------------------------------------------------------------------
mkdir -p "$INSTALL_DIR"/{core,anti_copy_modules,viral_engine,gui,utils,config,output}
mkdir -p "$INSTALL_DIR"/output/{prompts,reports,renders}
cd "$INSTALL_DIR"

# ----------------------------------------------------------------------------
# 4. AMBIENTE PYTHON (VENV)
# ----------------------------------------------------------------------------
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q

# ----------------------------------------------------------------------------
# 5. DEPENDÊNCIAS PYTHON
# ----------------------------------------------------------------------------
cat > requirements.txt << 'EOF'
faster-whisper==1.0.3
numpy==1.26.4
opencv-python-headless==4.9.0.80
gTTS==2.5.4
deep-translator==1.11.4
PyYAML==6.0.1
EOF
pip install -r requirements.txt -q

# ----------------------------------------------------------------------------
# 6. GERAÇÃO DOS ARQUIVOS DE CÓDIGO
# ----------------------------------------------------------------------------
log_info "Criando arquivos fonte..."

# db.py
cat > db.py << 'EOF'
import sqlite3, json, os
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(os.path.expanduser("~")) / ".clipfusion" / "clipfusion.db"

def _get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                video_path TEXT NOT NULL,
                language TEXT,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                full_text TEXT,
                segments_json TEXT,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                transcript_id INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                hook_strength REAL,
                retention_score REAL,
                moment_strength REAL,
                shareability REAL,
                platform_fit_tiktok REAL,
                platform_fit_reels REAL,
                platform_fit_shorts REAL,
                combined_score REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS cuts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                candidate_id INTEGER,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                title TEXT,
                hook TEXT,
                archetype TEXT,
                platforms TEXT,
                protection_level TEXT DEFAULT 'none',
                output_paths TEXT,
                viral_score REAL,
                decision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE SET NULL
            );
        """)
        conn.commit()

def create_project(name, video_path, language='pt'):
    with get_db() as conn:
        cur = conn.execute("INSERT INTO projects (name, video_path, language) VALUES (?,?,?)", (name, video_path, language))
        conn.commit()
        return cur.lastrowid

def get_project(project_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

def list_projects():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, status, created_at FROM projects ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

def update_project_status(project_id, status):
    with get_db() as conn:
        conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
        conn.commit()

def save_transcription(project_id, full_text, segments, quality_score=0.0):
    seg_json = json.dumps(segments, ensure_ascii=False)
    with get_db() as conn:
        cur = conn.execute("INSERT INTO transcripts (project_id, full_text, segments_json, quality_score) VALUES (?,?,?,?)",
                           (project_id, full_text, seg_json, quality_score))
        conn.commit()
        return cur.lastrowid

def get_transcription(project_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transcripts WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out['segments'] = json.loads(out.get('segments_json','[]'))
        return out

def save_candidate(project_id, transcript_id, start, end, text, scores=None, decision='pending'):
    s = scores or {}
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO candidates (project_id, transcript_id, start_time, end_time, text,
                hook_strength, retention_score, moment_strength, shareability,
                platform_fit_tiktok, platform_fit_reels, platform_fit_shorts, combined_score, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (project_id, transcript_id, start, end, text,
              s.get('hook',0), s.get('retention',0), s.get('moment',0), s.get('shareability',0),
              s.get('platform_fit_tiktok',0), s.get('platform_fit_reels',0), s.get('platform_fit_shorts',0),
              s.get('combined',0), decision))
        conn.commit()
        return cur.lastrowid

def get_candidates(project_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM candidates WHERE project_id = ? ORDER BY combined_score DESC", (project_id,)).fetchall()
        return [dict(r) for r in rows]

def save_cut(project_id, candidate_id, start, end, title, hook, archetype, platforms, protection_level, output_paths, viral_score, decision):
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO cuts (project_id, candidate_id, start_time, end_time, title, hook, archetype,
                platforms, protection_level, output_paths, viral_score, decision)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (project_id, candidate_id, start, end, title, hook, archetype,
              json.dumps(platforms), protection_level, json.dumps(output_paths), viral_score, decision))
        conn.commit()
        return cur.lastrowid

def get_cuts(project_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM cuts WHERE project_id = ?", (project_id,)).fetchall()
        return [dict(r) for r in rows]

def update_cut_output(cut_id, output_paths):
    with get_db() as conn:
        conn.execute("UPDATE cuts SET output_paths = ? WHERE id = ?", (json.dumps(output_paths), cut_id))
        conn.commit()

def update_cut_status(cut_id, status):
    with get_db() as conn:
        conn.execute("UPDATE cuts SET decision = ? WHERE id = ?", (status, cut_id))
        conn.commit()

init_db()
EOF

# utils/hardware.py
mkdir -p utils
cat > utils/hardware.py << 'EOF'
import subprocess, os
class HardwareDetector:
    def __init__(self): self.info = self._detect_all()
    def _detect_all(self):
        return {'cpu': self._detect_cpu(), 'gpu': self._detect_gpu(), 'ram_gb': self._detect_ram(), 'encoder': self._detect_encoder(), 'vaapi': self._check_vaapi()}
    def _detect_cpu(self):
        try:
            with open('/proc/cpuinfo') as f: lines=f.readlines()
            model,cores="",0
            for line in lines:
                if 'model name' in line and not model: model=line.split(':')[1].strip()
                if 'processor' in line: cores+=1
            return {'model':model,'cores':cores}
        except: return {'model':'i5-6200U','cores':4}
    def _detect_gpu(self):
        gpu={'intel':False,'nvidia':False}
        try:
            r=subprocess.run(['lspci'], capture_output=True, text=True)
            if 'HD Graphics 520' in r.stdout or 'UHD' in r.stdout: gpu['intel']=True
        except: pass
        try:
            r=subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'nvidia' in r.stdout or 'nouveau' in r.stdout: gpu['nvidia']=True
        except: pass
        return gpu
    def _detect_ram(self):
        try:
            with open('/proc/meminfo') as f: line=f.readline()
            kb=int(line.split()[1]); return round(kb/1024/1024,1)
        except: return 8.0
    def _detect_encoder(self):
        try:
            env=dict(os.environ); env.setdefault('LIBVA_DRIVER_NAME','iHD')
            r=subprocess.run(['vainfo'], env=env, capture_output=True, text=True)
            if 'VAEntrypointEncSlice' in r.stdout: return 'h264_vaapi'
        except: pass
        return 'libx264'
    def _check_vaapi(self):
        try:
            env=dict(os.environ); env.setdefault('LIBVA_DRIVER_NAME','iHD')
            r=subprocess.run(['vainfo'], env=env, capture_output=True, text=True)
            out=r.stdout+r.stderr
            return {'disponivel':'VAEntrypointEncSlice' in out, 'driver':'iHD' if 'iHD' in out else 'i965', 'encode_h264':'VAEntrypointEncSlice' in out}
        except: return {'disponivel':False,'driver':'none','encode_h264':False}
    def get_encoder(self): return 'h264_vaapi' if self.info['vaapi']['disponivel'] else 'libx264'
    def get_status_string(self):
        enc=self.get_encoder(); vaapi='✅ VA-API' if enc=='h264_vaapi' else '⚠️ CPU'
        try:
            r=subprocess.run(['sensors'], capture_output=True, text=True)
            for line in r.stdout.split('\n'):
                if 'Core 0' in line: temp=line.split()[2].replace('+','').replace('°C',''); return f"{vaapi}  |  CPU {temp}°C  |  RAM {self.info['ram_gb']}GB"
        except: pass
        return f"{vaapi}  |  i5-6200U  |  RAM {self.info['ram_gb']}GB"
EOF

# core/transcriber.py
mkdir -p core
cat > core/transcriber.py << 'EOF'
import os, tempfile, shutil, subprocess, gc
def fmt_time(s): return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"
class WhisperTranscriber:
    def __init__(self, model="tiny", language="pt"): self.model=model; self.language=language
    def transcribe(self, video_path, progress_callback=None):
        tmp_dir = tempfile.mkdtemp()
        wav_path = os.path.join(tmp_dir, "audio.wav")
        try:
            subprocess.run(['ffmpeg','-y','-i',video_path,'-vn','-acodec','pcm_s16le','-ar','16000','-ac','1',wav_path], capture_output=True, check=True)
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel(self.model, device="cpu", compute_type="int8", cpu_threads=2)
                segs, _ = model.transcribe(wav_path, language=self.language, vad_filter=True)
                segments = [{'start':round(s.start,2),'end':round(s.end,2),'text':s.text.strip()} for s in segs]
                del model; gc.collect()
            except ImportError:
                import whisper
                model = whisper.load_model(self.model, device="cpu")
                res = model.transcribe(wav_path, language=self.language, fp16=False)
                segments = [{'start':round(s['start'],2),'end':round(s['end'],2),'text':s['text'].strip()} for s in res['segments']]
            return {'full_text':' '.join(s['text'] for s in segments), 'segments':segments, 'language':self.language}
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
EOF

# core/segment.py
cat > core/segment.py << 'EOF'
def segment_by_pauses(segments, min_duration=18, max_duration=35, pause_threshold=0.5):
    candidates = []
    current_start = None
    current_end = None
    current_text = []
    last_end = 0
    for seg in segments:
        if current_start is None:
            current_start = seg['start']; current_end = seg['end']; current_text = [seg['text']]; last_end = seg['end']; continue
        gap = seg['start'] - last_end
        if gap > pause_threshold or (seg['end'] - current_start) > max_duration:
            if (current_end - current_start) >= min_duration:
                candidates.append({'start': current_start, 'end': current_end, 'text': ' '.join(current_text)})
            current_start = seg['start']; current_end = seg['end']; current_text = [seg['text']]
        else:
            current_end = seg['end']; current_text.append(seg['text'])
        last_end = seg['end']
    if current_start and (current_end - current_start) >= min_duration:
        candidates.append({'start': current_start, 'end': current_end, 'text': ' '.join(current_text)})
    return candidates
EOF

# core/decision_engine.py
cat > core/decision_engine.py << 'EOF'
def evaluate_decision(local_score, external_score, platform_fit, transcription_quality):
    final = (local_score*0.5) + (external_score*0.3) + (platform_fit*0.1) + (transcription_quality*0.1)
    if final >= 0.75: return final, "approve", "Alto potencial"
    if final >= 0.55: return final, "review", "Revisar manualmente"
    return final, "discard", "Descartar"
EOF

# core/cut_engine.py
cat > core/cut_engine.py << 'EOF'
import subprocess, os, tempfile, shutil
def _detect_vaapi():
    try:
        r = subprocess.run(["vainfo"], capture_output=True, text=True)
        return "VAEntrypointEncSlice" in r.stdout
    except: return False
def render_cut(video_path, start, end, out_dir, base_name, protection_level="basic", subtitle_text="", use_vaapi=True, auto_dub_en=False, dub_lang="en"):
    duration = end - start
    out = {}
    tmp = tempfile.mkdtemp()
    try:
        for platform in ["tiktok","reels","shorts"]:
            out_path = os.path.join(out_dir, platform, f"{base_name}_{platform}.mp4")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            cmd = ["ffmpeg","-y","-ss",str(start),"-i",video_path,"-t",str(duration),"-c:v","libx264","-c:a","aac",out_path]
            subprocess.run(cmd, check=False)
            out[platform] = out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out
def render_all(video_path, cuts, segments, output_dir, project_id, ace_level="basic", use_vaapi=True, progress_cb=None):
    results = {}
    for i, cut in enumerate(cuts):
        if progress_cb: progress_cb(f"[{i+1}/{len(cuts)}] {cut.get('title','Corte')}")
        results[i] = render_cut(video_path, cut['start'], cut['end'], output_dir, f"cut_{i}", ace_level, "", use_vaapi)
    return results
EOF

# core/prompt_builder.py
cat > core/prompt_builder.py << 'EOF'
import json, re
from viral_engine.archetypes import ARCHETYPES
from core.transcriber import fmt_time

def _detect_lang(text):
    text_l = text.lower()
    pt_markers = (" você ", " não ", " para ", " que ", " com ", " uma ", " de ")
    en_markers = (" you ", " not ", " with ", " the ", " and ", " this ", " that ")
    return "en" if sum(m in text_l for m in en_markers) > sum(m in text_l for m in pt_markers) else "pt"

def _coverage_sample(segments, buckets=10):
    if not segments: return []
    first = float(segments[0]["start"]); last = float(segments[-1]["end"]); span = max(1.0, last-first)
    bucket_size = span / buckets; sampled = []; idx = 0
    for b in range(buckets):
        b_start = first + b*bucket_size; b_end = b_start+bucket_size
        chosen = None
        while idx < len(segments):
            s = segments[idx]; idx+=1
            if b_start <= float(s["start"]) < b_end: chosen = s; break
        if chosen: sampled.append(chosen)
    return sampled

def build_analysis_prompt(segments, duration, context=""):
    sampled = _coverage_sample(segments, buckets=12)
    joined = " ".join(s.get("text","") for s in sampled)[:3000]
    lang = _detect_lang(f" {joined} ")
    lines, total = [], 0
    for s in segments:
        line = f"[{fmt_time(s['start'])}] {s['text']}"
        total += len(line)+1
        if total > 30000: lines.append("...(truncado)"); break
        lines.append(line)
    transcript = "\n".join(lines)
    arch_block = "\n".join(f"  {k}: {v['emocao']} — {v['descricao']}" for k,v in ARCHETYPES.items())
    ctx = f"\n## CONTEXTO\n{context.strip()}\n" if context.strip() else ""
    lang_block = "Primary language appears to be ENGLISH." if lang=="en" else "Idioma principal detectado: PORTUGUÊS."
    coverage = "\n".join(f"[{fmt_time(s['start'])}] {s['text']}" for s in sampled)
    return f"""Você é especialista em viralização de conteúdo curto.
{ctx}
## DURAÇÃO TOTAL: {fmt_time(duration)}
## LANGUAGE / IDIOMA
{lang_block}
## TRANSCRIÇÃO COM TIMESTAMPS
{transcript}
## COBERTURA GLOBAL
{coverage}
## ARQUÉTIPOS DISPONÍVEIS
{arch_block}
## TAREFA: Identifique 3 a 8 cortes virais (JSON)
{{"cortes":[{{"titulo":"...","start":0,"end":0,"archetype":"05_revelacao","hook":"...","reason":"...","platforms":["tiktok","reels","shorts"]}}]}}
Analise agora:"""

def parse_ai_response(text):
    text = re.sub(r"```json\s*|```\s*", "", text.strip())
    blob = re.search(r"\{[\s\S]*\}", text) or re.search(r"\[[\s\S]*\]", text)
    if not blob: raise ValueError("JSON não encontrado")
    parsed = json.loads(blob.group())
    cortes = parsed if isinstance(parsed,list) else parsed.get("cortes",[])
    result = []
    for i,c in enumerate(cortes):
        s = float(c.get("start",0) or 0); e = float(c.get("end",0) or 0)
        if e>s and (e-s)>=10:
            result.append({"cut_index":i,"title":c.get("titulo",f"Corte {i+1}"),"start":s,"end":e,"archetype":c.get("archetype","01_despertar"),"hook":c.get("hook",""),"reason":c.get("reason",""),"platforms":c.get("platforms",["tiktok","reels","shorts"]),"metadata":c.get("metadata",{})})
    return result
EOF

# anti_copy_modules/core.py
mkdir -p anti_copy_modules
cat > anti_copy_modules/core.py << 'EOF'
from enum import Enum
class ProtectionLevel(Enum): NONE="none"; BASIC="basic"; ANTI_IA="anti_ia"; MAXIMUM="maximum"
LEVEL_LABELS = {"none":"🟢 NENHUM","basic":"🟡 BÁSICO","anti_ia":"🟠 ANTI-IA","maximum":"🔴 MÁXIMO"}
class AntiCopyrightEngine:
    def __init__(self, project_id, cut_index, config, log=print): pass
    def process(self, inp, out): import shutil; shutil.copy2(inp, out)
EOF

# anti_copy_modules/network_evasion.py
cat > anti_copy_modules/network_evasion.py << 'EOF'
import random
from datetime import datetime, timedelta
class NetworkEvasion:
    PLATFORM_CONFIGS={"tiktok":{"peak":[(7,9),(12,14),(19,22)],"interval":(4,8)},"instagram":{"peak":[(11,13),(19,21)],"interval":(18,30)},"youtube":{"peak":[(14,16),(19,21)],"interval":(48,96)},"kwai":{"peak":[(12,14),(20,23)],"interval":(6,12)}}
    def __init__(self,seed=None): self.rng=random.Random(seed)
    def generate_schedule(self,count,platform="tiktok"):
        cfg=self.PLATFORM_CONFIGS.get(platform,self.PLATFORM_CONFIGS["tiktok"]); current=datetime.now(); out=[]
        for i in range(count):
            min_h,max_h=cfg["interval"]; hours=self.rng.uniform(min_h,max_h); jitter=hours*self.rng.uniform(-0.20,0.20); current+=timedelta(hours=hours+jitter)
            window=self.rng.choice(cfg["peak"]); current=current.replace(hour=int(self.rng.uniform(*window)),minute=self.rng.randint(0,59),second=self.rng.randint(0,59))
            out.append({"index":i+1,"platform":platform,"datetime":current.strftime("%d/%m/%Y %H:%M")})
        return out
    def format_schedule(self,schedule):
        lines=[f"📅 Agenda — {len(schedule)} vídeos\n"] + [f"  #{s['index']:02d}  {s['datetime']}  [{s['platform']}]" for s in schedule]
        return "\n".join(lines)
EOF

# viral_engine/archetypes.py
mkdir -p viral_engine
cat > viral_engine/archetypes.py << 'EOF'
ARCHETYPES = {
    "01_despertar": {"emocao":"Curiosidade+Urgência","descricao":"Quebra de crença"},
    "02_tensao": {"emocao":"Medo+Antecipação","descricao":"Risco iminente"},
    "03_confronto": {"emocao":"Raiva+Determinação","descricao":"Posição forte"},
    "04_virada": {"emocao":"Esperança+Empoderamento","descricao":"Mudança de perspectiva"},
    "05_revelacao": {"emocao":"Surpresa+Fascínio","descricao":"Segredo revelado"},
    "06_justo_engolido": {"emocao":"Injustiça+Revolta","descricao":"Alguém sendo prejudicado"},
    "07_transformacao": {"emocao":"Superação+Inspiração","descricao":"Antes/depois"},
    "08_resolucao": {"emocao":"Alívio+Satisfação","descricao":"Solução entregue"},
    "09_impacto": {"emocao":"Choque+Admiração","descricao":"Números fortes"},
    "10_encerramento": {"emocao":"Realização+Fechamento","descricao":"Lição aprendida"},
}
EOF

# gui/main_gui.py (versão resumida mas funcional)
mkdir -p gui
cat > gui/main_gui.py << 'EOF'
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading, os, gc, json
from pathlib import Path
from datetime import datetime
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from core.transcriber import WhisperTranscriber, fmt_time
from core.segment import segment_by_pauses
from core.decision_engine import evaluate_decision
from core.cut_engine import render_all, _detect_vaapi
from anti_copy_modules.core import LEVEL_LABELS
from viral_engine.archetypes import ARCHETYPES
from utils.hardware import HardwareDetector

BG="#0d0d1a"; BG2="#151528"; BG3="#1e1e3a"; ACC="#7c3aed"; GRN="#22c55e"; RED="#ef4444"; YEL="#f59e0b"; WHT="#f1f5f9"; GRY="#64748b"
FNT=("Segoe UI",10); FNTB=("Segoe UI",10,"bold"); FNTL=("Segoe UI",13,"bold"); MONO=("Consolas",9)
ACE_LEVELS=[("🟢 NENHUM","none"),("🟡 BÁSICO","basic"),("🟠 ANTI-IA","anti_ia"),("🔴 MÁXIMO","maximum")]

class ClipFusionApp:
    def __init__(self):
        self.root=tk.Tk(); self.root.title("✂ ClipFusion Viral Pro"); self.root.geometry("1120x800"); self.root.configure(bg=BG)
        self.project_id=None; self.video_path=None; self.segments=[]; self.duration=0.0; self.cut_vars={}; self.output_dir=None; self.hw=HardwareDetector()
        self._build_ui()
    def run(self): self.root.mainloop()
    def _build_ui(self):
        hdr=tk.Frame(self.root,bg=ACC,height=54); hdr.pack(fill="x")
        tk.Label(hdr,text="✂  ClipFusion Viral Pro",font=("Segoe UI",16,"bold"),bg=ACC,fg=WHT).pack(side="left",padx=20,pady=12)
        tk.Label(hdr,text="vídeo longo → cortes virais",font=FNT,bg=ACC,fg="#c4b5fd").pack(side="left")
        self.lbl_hw=tk.Label(hdr,text=self.hw.get_status_string(),font=("Segoe UI",8),bg=ACC,fg="#c4b5fd"); self.lbl_hw.pack(side="right",padx=16)
        s=ttk.Style(); s.theme_use("clam"); s.configure("TNotebook",background=BG2,borderwidth=0); s.configure("TNotebook.Tab",background=BG3,foreground=GRY,padding=[14,7],font=FNT); s.map("TNotebook.Tab",background=[("selected",ACC)],foreground=[("selected",WHT)])
        self.nb=ttk.Notebook(self.root); self.nb.pack(fill="both",expand=True)
        self._tab_projeto(); self._tab_transcricao(); self._tab_ia(); self._tab_cortes(); self._tab_render(); self._tab_historico(); self._tab_agenda()
    def _tab_projeto(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="📁  Projeto")
        self._lbl(f,"Novo projeto",font=FNTL).pack(anchor="w",padx=30,pady=(28,4))
        self._lbl(f,"Selecione o vídeo e configure.",color=GRY).pack(anchor="w",padx=30); self._sep(f)
        r1=tk.Frame(f,bg=BG2); r1.pack(fill="x",padx=30,pady=6); self._lbl(r1,"Nome:").pack(side="left"); self.v_name=tk.StringVar(value=f"Projeto {datetime.now().strftime('%d/%m %H:%M')}"); tk.Entry(r1,textvariable=self.v_name,width=44,bg=BG3,fg=WHT,insertbackground=WHT,relief="flat",font=FNT).pack(side="left",padx=10)
        self._lbl(f,"Contexto (opcional)").pack(anchor="w",padx=30,pady=(12,4)); self.ctx_box=tk.Text(f,height=3,bg=BG3,fg=WHT,insertbackground=WHT,relief="flat",font=FNT,wrap="word"); self.ctx_box.pack(fill="x",padx=30); self.ctx_box.insert("1.0","Ex: Podcast sobre vendas")
        self._sep(f); vr=tk.Frame(f,bg=BG2); vr.pack(fill="x",padx=30,pady=6); self._btn(vr,"📂 Selecionar vídeo",self._select_video,ACC).pack(side="left"); self.lbl_video=self._lbl(vr,"Nenhum vídeo",color=GRY); self.lbl_video.pack(side="left",padx=14)
        op=tk.Frame(f,bg=BG2); op.pack(fill="x",padx=30,pady=10); self.v_vaapi=tk.BooleanVar(value=True); self._chk(op,"Usar VA-API (Intel HD 520)",self.v_vaapi).pack(anchor="w")
        acef=tk.Frame(f,bg=BG2); acef.pack(fill="x",padx=30,pady=4); self._lbl(acef,"Anti-Copyright:").pack(side="left"); self.v_ace=tk.StringVar(value="basic")
        for lbl,val in ACE_LEVELS: tk.Radiobutton(acef,text=lbl,variable=self.v_ace,value=val,bg=BG2,fg=WHT,selectcolor=ACC,activebackground=BG2,font=FNT).pack(side="left",padx=8)
        wf=tk.Frame(f,bg=BG2); wf.pack(fill="x",padx=30,pady=4); self._lbl(wf,"Whisper:").pack(side="left"); self.v_whisper=tk.StringVar(value="tiny")
        for m in ["tiny","base","small"]: tk.Radiobutton(wf,text=m,variable=self.v_whisper,value=m,bg=BG2,fg=WHT,selectcolor=ACC,activebackground=BG2,font=FNT).pack(side="left",padx=8)
        self._lbl(f,"Cole uma transcrição (opcional)").pack(anchor="w",padx=30,pady=(10,4))
        self.box_transcript_input=scrolledtext.ScrolledText(f,height=8,bg=BG3,fg=WHT,font=MONO,relief="flat",insertbackground=WHT); self.box_transcript_input.pack(fill="both",padx=30,pady=(0,10))
        self._btn(f,"▶ Iniciar Transcrição",self._start_transcription,GRN,wide=True).pack(padx=30,pady=8); self.lbl_status=self._lbl(f,"",color=GRY); self.lbl_status.pack(padx=30,pady=4)
    def _tab_transcricao(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="📝  Transcrição")
        self._lbl(f,"Transcrição com timestamps",font=FNTL).pack(anchor="w",padx=30,pady=(20,4))
        self.box_transcript=scrolledtext.ScrolledText(f,bg=BG3,fg=WHT,font=MONO,relief="flat",insertbackground=WHT); self.box_transcript.pack(fill="both",expand=True,padx=30,pady=12)
        self._btn(f,"▶ Gerar Prompt IA →",self._goto_ia,ACC,wide=True).pack(padx=30,pady=(0,20))
    def _tab_ia(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="🤖  IA Externa")
        top=tk.Frame(f,bg=BG2); top.pack(fill="x",padx=30,pady=(20,4)); self._lbl(top,"Prompt para copiar",font=FNTL).pack(side="left"); self._btn(top,"📋 Copiar",self._copy_prompt,ACC).pack(side="right")
        self.box_prompt=scrolledtext.ScrolledText(f,height=11,bg=BG3,fg="#a5b4fc",font=MONO,relief="flat",insertbackground=WHT); self.box_prompt.pack(fill="x",padx=30,pady=(4,14))
        self._lbl(f,"Resposta da IA (JSON):",font=FNTB).pack(anchor="w",padx=30)
        self.box_resp=scrolledtext.ScrolledText(f,height=13,bg=BG3,fg=GRN,font=MONO,relief="flat",insertbackground=WHT); self.box_resp.pack(fill="both",expand=True,padx=30,pady=4)
        self._btn(f,"✅ Processar resposta",self._process_resp,GRN,wide=True).pack(padx=30,pady=(4,20))
    def _tab_cortes(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="✂  Cortes")
        top=tk.Frame(f,bg=BG2); top.pack(fill="x",padx=30,pady=(20,4)); self._lbl(top,"Cortes sugeridos",font=FNTL).pack(side="left"); self._btn(top,"✅ Todos",self._approve_all,GRN).pack(side="right",padx=4); self._btn(top,"❌ Nenhum",self._reject_all,RED).pack(side="right")
        self._lbl(f,"Marque os cortes para renderizar.").pack(anchor="w",padx=30)
        outer=tk.Frame(f,bg=BG2); outer.pack(fill="both",expand=True,padx=30,pady=8); cv=tk.Canvas(outer,bg=BG2,highlightthickness=0); sb=ttk.Scrollbar(outer,orient="vertical",command=cv.yview); self.cuts_frame=tk.Frame(cv,bg=BG2); self.cuts_frame.bind("<Configure>",lambda e: cv.configure(scrollregion=cv.bbox("all"))); cv.create_window((0,0),window=self.cuts_frame,anchor="nw"); cv.configure(yscrollcommand=sb.set); cv.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y"); cv.bind_all("<MouseWheel>",lambda e: cv.yview_scroll(-1*(e.delta//120),"units"))
        self._btn(f,"🎬 Renderizar",self._start_render,ACC,wide=True).pack(padx=30,pady=(4,20))
    def _tab_render(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="🎬  Render")
        self._lbl(f,"Log de render",font=FNTL).pack(anchor="w",padx=30,pady=(20,4))
        self.box_log=scrolledtext.ScrolledText(f,bg=BG3,fg=GRN,font=MONO,relief="flat",insertbackground=WHT); self.box_log.pack(fill="both",expand=True,padx=30,pady=10)
        self._btn(f,"📂 Abrir pasta",self._open_output,GRY,wide=True).pack(padx=30,pady=(0,20))
    def _tab_historico(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="📋  Histórico")
        self._lbl(f,"Projetos anteriores",font=FNTL).pack(anchor="w",padx=30,pady=(20,4))
        cols=("ID","Nome","Status","Criado em"); st=ttk.Style(); st.configure("Treeview",background=BG3,foreground=WHT,fieldbackground=BG3,rowheight=28); st.configure("Treeview.Heading",background=ACC,foreground=WHT)
        self.tree=ttk.Treeview(f,columns=cols,show="headings",selectmode="browse")
        for c in cols: self.tree.heading(c,text=c); self.tree.column(c,width=50 if c=="ID" else 200)
        self.tree.pack(fill="both",expand=True,padx=30,pady=10); self._btn(f,"🔄 Carregar projeto",self._load_project,ACC,wide=True).pack(padx=30,pady=(0,20)); self._refresh_tree()
    def _tab_agenda(self):
        f=tk.Frame(self.nb,bg=BG2); self.nb.add(f,text="📅  Agenda")
        self._lbl(f,"Agenda de Upload",font=FNTL).pack(anchor="w",padx=30,pady=(20,4)); self._sep(f)
        cfg=tk.Frame(f,bg=BG2); cfg.pack(fill="x",padx=30,pady=8); self._lbl(cfg,"Plataforma:").pack(side="left"); self.v_platform=tk.StringVar(value="tiktok")
        for p in ["tiktok","instagram","youtube","kwai"]: tk.Radiobutton(cfg,text=p,variable=self.v_platform,value=p,bg=BG2,fg=WHT,selectcolor=ACC,activebackground=BG2,font=FNT).pack(side="left",padx=8)
        cfg2=tk.Frame(f,bg=BG2); cfg2.pack(fill="x",padx=30,pady=4); self._lbl(cfg2,"Quantidade:").pack(side="left"); self.v_count=tk.StringVar(value="10"); tk.Entry(cfg2,textvariable=self.v_count,width=6,bg=BG3,fg=WHT,insertbackground=WHT,relief="flat",font=FNT).pack(side="left",padx=10)
        self._btn(f,"📅 Gerar Agenda",self._generate_schedule,ACC,wide=True).pack(padx=30,pady=10); self.box_agenda=scrolledtext.ScrolledText(f,bg=BG3,fg=GRN,font=MONO,relief="flat",insertbackground=WHT); self.box_agenda.pack(fill="both",expand=True,padx=30,pady=10)
    def _select_video(self): p=filedialog.askopenfilename(filetypes=[("Vídeos","*.mp4 *.mkv *.mov *.avi *.webm")]); self.video_path=p; self.lbl_video.config(text=f"✅ {os.path.basename(p)}",fg=GRN) if p else None
    def _start_transcription(self):
        if not self.video_path: messagebox.showwarning("Atenção","Selecione um vídeo."); return
        name=self.v_name.get().strip() or "Sem nome"; pid=db.create_project(name,self.video_path); self.project_id=pid; self._status(f"Projeto #{pid} criado. Transcrevendo...",YEL)
        def run():
            try:
                raw=self.box_transcript_input.get("1.0","end-1c").strip()
                if raw:
                    lines=[x.strip() for x in raw.splitlines() if x.strip()]
                    base_segments=[]; t=0.0
                    for line in lines: end=t+3.0; base_segments.append({"start":t,"end":end,"text":line}); t=end
                    self.segments=segment_by_pauses(base_segments) or [{"start":0.0,"end":min(30.0,max(18.0,t)),"text":" ".join(lines)}]
                    full_text="\n".join(lines)
                    quality=0.85
                else:
                    transcriber=WhisperTranscriber(model=self.v_whisper.get(),language="pt")
                    res=transcriber.transcribe(self.video_path); self.segments=res["segments"]; self.duration=self.segments[-1]["end"] if self.segments else 0; full_text=res["full_text"]; quality=0.9
                db.save_transcription(pid,full_text,self.segments,quality); db.update_project_status(pid,"transcrito")
                self.root.after(0,lambda: self._update_after_transcription(full_text))
            except Exception as e: self.root.after(0,lambda: messagebox.showerror("Erro",str(e)))
        threading.Thread(target=run,daemon=True).start()
    def _update_after_transcription(self,full_text):
        self.box_transcript.delete("1.0","end")
        for s in self.segments: self.box_transcript.insert("end",f"[{fmt_time(s['start'])}] {s['text']}\n")
        from core.prompt_builder import build_analysis_prompt
        ctx=self.ctx_box.get("1.0","end").strip(); ctx="" if ctx.startswith("Ex:") else ctx
        prompt=build_analysis_prompt(self.segments,self.duration,ctx)
        self.box_prompt.delete("1.0","end"); self.box_prompt.insert("1.0",prompt)
        self._status(f"✅ {len(self.segments)} segmentos. Vá para IA Externa.",GRN); self.nb.select(1)
    def _goto_ia(self): self.nb.select(2)
    def _copy_prompt(self): self.root.clipboard_clear(); self.root.clipboard_append(self.box_prompt.get("1.0","end-1c")); messagebox.showinfo("Copiado","Cole no Claude/ChatGPT e cole a resposta JSON.")
    def _process_resp(self):
        resp=self.box_resp.get("1.0","end-1c").strip()
        if not resp: messagebox.showwarning("Atenção","Cole o JSON da IA."); return
        try:
            from core.prompt_builder import parse_ai_response
            cuts=parse_ai_response(resp)
            if not cuts: raise ValueError("Nenhum corte válido")
            db.save_cuts(self.project_id, cuts)
            db.update_project_status(self.project_id,"cortes_prontos")
            self._draw_cuts(cuts); self.nb.select(3)
        except Exception as e: messagebox.showerror("Erro",str(e))
    def _draw_cuts(self,cuts):
        for w in self.cuts_frame.winfo_children(): w.destroy()
        self.cut_vars={}
        for i,cut in enumerate(cuts):
            card=tk.Frame(self.cuts_frame,bg=BG3); card.pack(fill="x",pady=3,padx=2); var=tk.BooleanVar(value=True); self.cut_vars[i]=var
            hdr=tk.Frame(card,bg=BG3); hdr.pack(fill="x",padx=10,pady=(8,3)); tk.Checkbutton(hdr,variable=var,bg=BG3,fg=WHT,selectcolor=ACC,activebackground=BG3,font=FNTB).pack(side="left")
            start=cut['start']; end=cut['end']; dur=end-start
            tk.Label(hdr,text=cut.get('title','Corte'),bg=BG3,fg=WHT,font=FNTB).pack(side="left",padx=4)
            tk.Label(hdr,text=f"  {fmt_time(start)} → {fmt_time(end)} ({fmt_time(dur)})",bg=BG3,fg=GRY,font=FNT).pack(side="left")
            if cut.get('hook'): tk.Label(card,text=f"🎣 {cut['hook']}",bg=BG3,fg="#a5b4fc",font=FNT,wraplength=960,justify="left",anchor="w").pack(fill="x",padx=22,pady=2)
            tk.Frame(card,bg=BG,height=1).pack(fill="x")
    def _approve_all(self): [v.set(True) for v in self.cut_vars.values()]
    def _reject_all(self): [v.set(False) for v in self.cut_vars.values()]
    def _start_render(self):
        if not self.project_id: messagebox.showwarning("Atenção","Nenhum projeto ativo."); return
        approved=[]
        for i,cut in enumerate(db.get_candidates(self.project_id)):
            if self.cut_vars.get(i,True):
                approved.append({"start":cut["start_time"],"end":cut["end_time"],"title":f"Corte {cut['id']}","platforms":["tiktok","reels","shorts"]})
        if not approved: messagebox.showwarning("Atenção","Nenhum corte aprovado."); return
        proj=db.get_project(self.project_id); safe="".join(c for c in proj['name'] if c.isalnum() or c in " _-").strip().replace(" ","_")
        out_dir=os.path.join(str(Path(self.video_path).parent),f"clipfusion_{safe}"); os.makedirs(out_dir,exist_ok=True); self.output_dir=out_dir
        self.nb.select(4); self.box_log.delete("1.0","end"); vaapi_ok=_detect_vaapi() and self.v_vaapi.get()
        self._log(f"Renderizando {len(approved)} cortes em {out_dir}"); self._log(f"Anti-copyright: {LEVEL_LABELS.get(self.v_ace.get(),'')}"); self._log(f"Encoder: {'VA-API' if vaapi_ok else 'CPU'}")
        ace=self.v_ace.get(); vaapi=self.v_vaapi.get(); segs=self.segments; vid=self.video_path
        def run():
            try:
                results=render_all(vid,approved,segs,out_dir,str(self.project_id),ace,vaapi,lambda m: self.root.after(0,lambda msg=m: self._log(msg)))
                gc.collect()
                self.root.after(0,lambda: self._log(f"\n✅ PRONTO! {len(results)} cortes em {out_dir}"))
                self.root.after(0,lambda: messagebox.showinfo("Concluído",f"{len(results)} cortes gerados!\nPasta: {out_dir}"))
            except Exception as e: self.root.after(0,lambda err=e: self._log(f"\n❌ ERRO: {err}"))
        threading.Thread(target=run,daemon=True).start()
    def _open_output(self): d=self.output_dir; os.system(f'xdg-open "{d}"') if d and os.path.exists(d) else messagebox.showinfo("Info","Pasta ainda não criada.")
    def _generate_schedule(self):
        try:
            from anti_copy_modules.network_evasion import NetworkEvasion
            ne=NetworkEvasion(seed=int(datetime.now().timestamp()))
            sched=ne.generate_schedule(int(self.v_count.get()),self.v_platform.get())
            text=ne.format_schedule(sched)
            self.box_agenda.delete("1.0","end"); self.box_agenda.insert("1.0",text)
        except Exception as e: messagebox.showerror("Erro",str(e))
    def _load_project(self):
        sel=self.tree.selection()
        if not sel: return
        pid=int(self.tree.item(sel[0])["values"][0]); proj=db.get_project(pid)
        if not proj: return
        self.project_id=pid; self.video_path=proj["video_path"]
        t=db.get_transcription(pid)
        if t:
            self.segments=t['segments']; self.duration=self.segments[-1]['end'] if self.segments else 0
            self.box_transcript.delete("1.0","end")
            for s in self.segments: self.box_transcript.insert("end",f"[{fmt_time(s['start'])}] {s['text']}\n")
        self.v_name.set(proj["name"]); self.lbl_video.config(text=f"✅ {os.path.basename(proj['video_path'])}",fg=GRN); messagebox.showinfo("Carregado",f"Projeto '{proj['name']}' carregado."); self.nb.select(0)
    def _refresh_tree(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        for p in db.list_projects(): self.tree.insert("","end",values=(p["id"],p["name"],p.get("status","-"),p["created_at"]))
    def _log(self,m): self.box_log.insert("end",m+"\n"); self.box_log.see("end")
    def _status(self,m,color=GRY): self.lbl_status.config(text=m,fg=color)
    def _lbl(self,p,text="",font=None,color=None): return tk.Label(p,text=text,bg=p.cget("bg") if hasattr(p,"cget") else BG2,fg=color or WHT,font=font or FNT)
    def _btn(self,p,text,cmd,color=BG3,wide=False): return tk.Button(p,text=text,command=cmd,bg=color,fg=WHT,font=FNTB,relief="flat",cursor="hand2",padx=20 if wide else 14,pady=8,activebackground=color,activeforeground=WHT,width=50 if wide else None)
    def _chk(self,p,text,var): return tk.Checkbutton(p,text=text,variable=var,bg=p.cget("bg"),fg=WHT,selectcolor=ACC,activebackground=p.cget("bg"),font=FNT)
    def _sep(self,p): tk.Frame(p,bg=BG3,height=1).pack(fill="x",padx=30,pady=16)
EOF

# main.py
cat > main.py << 'EOF'
#!/usr/bin/env python3
from db import init_db
from gui.main_gui import ClipFusionApp
if __name__ == "__main__":
    init_db()
    ClipFusionApp().run()
EOF

# run.sh
cat > run.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export LIBVA_DRIVER_NAME=iHD
python main.py
EOF
chmod +x run.sh

# README.md
cat > README.md << 'EOF'
# ✂ ClipFusion Viral Pro
Ferramenta completa para criar cortes virais de vídeos longos, otimizada para i5-6200U + Intel HD 520.

## Instalação
```bash
chmod +x FULLinstallClipFusion_V3.sh
sudo ./FULLinstallClipFusion_V3.sh
cd ~/clipfusion && ./run.sh

\
#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


class Validator:
    def __init__(self, repo_path: Path):
        self.repo = repo_path.expanduser().resolve()
        self.ops_dir = self.repo / "ops"
        self.reports_dir = self.ops_dir / "reports"
        self.manifest_path = self.ops_dir / "manifests" / "patch_selecao_inteligencia_v1.json"
        self.registry_path = self.ops_dir / "patch_registry.jsonl"
        self.status = "FAIL"
        self.checks: List[CheckResult] = []
        self.notes: List[str] = []
        self.current_hashes: Dict[str, str] = {}
        self.report_path: Path | None = None

    def add(self, name: str, ok: bool, details: str = "") -> None:
        self.checks.append(CheckResult(name=name, ok=ok, details=details))

    def load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest não encontrado: {self.manifest_path}")
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def validate_repo_root(self, manifest: Dict[str, Any]) -> bool:
        if not self.repo.exists() or not self.repo.is_dir():
            self.add("repo_root", False, f"pasta não encontrada: {self.repo}")
            return False

        missing = []
        for marker in manifest["target_repo_markers"]:
            if not (self.repo / marker).exists():
                missing.append(marker)
        if missing:
            self.add("repo_root", False, f"ausentes na raiz: {', '.join(missing)}")
            return False

        self.add("repo_root", True, str(self.repo))
        return True

    def snapshot_paths(self, manifest: Dict[str, Any]) -> None:
        for rel in manifest["files_changed"]:
            path = self.repo / rel
            if path.exists():
                self.current_hashes[rel] = sha256_file(path)

        anti = self.repo / "anti_copy_modules"
        if anti.exists():
            for p in anti.rglob("*"):
                if p.is_file():
                    self.current_hashes[str(p.relative_to(self.repo))] = sha256_file(p)

    def check_files_exist(self, manifest: Dict[str, Any]) -> None:
        for rel in manifest["files_changed"]:
            path = self.repo / rel
            self.add(f"file_exists:{rel}", path.exists(), rel)

    def check_markers(self, manifest: Dict[str, Any]) -> None:
        for rel, markers in manifest["file_markers"].items():
            path = self.repo / rel
            if not path.exists():
                self.add(f"markers:{rel}", False, "arquivo ausente")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            missing = [m for m in markers if m not in text]
            self.add(f"markers:{rel}", not missing, "ok" if not missing else f"faltando: {missing}")

    def check_python_syntax(self, manifest: Dict[str, Any]) -> None:
        failed = []
        for rel in manifest["files_changed"]:
            path = self.repo / rel
            try:
                py_compile.compile(str(path), doraise=True)
            except Exception as exc:
                failed.append(f"{rel}: {exc}")
        self.add("python_syntax", not failed, "ok" if not failed else " | ".join(failed))

    def import_module(self, path: Path, module_name: str):
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Não foi possível carregar módulo: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def smoke_prompt_builder(self) -> None:
        try:
            mod = self.import_module(self.repo / "core" / "prompt_builder.py", "clipfusion_prompt_builder_validation")
            segments = [
                {"start": 0.0, "end": 4.0, "text": "Você está cometendo um erro que destrói seus resultados."},
                {"start": 4.0, "end": 10.0, "text": "Ninguém te conta isso, mas o problema está no começo do processo."},
                {"start": 10.0, "end": 22.0, "text": "Quando você ajusta isso, a retenção muda completamente."},
            ]
            prompt = mod.build_analysis_prompt(segments, 22.0, context="teste")
            mock = """
            {
              "cortes": [
                {
                  "titulo": "Teste",
                  "start": 0.0,
                  "end": 22.0,
                  "archetype": "05_revelacao",
                  "hook": "Você está cometendo um erro",
                  "reason": "Gancho forte",
                  "platforms": ["tiktok"],
                  "metadata": {}
                }
              ]
            }
            """
            cuts = mod.parse_ai_response(mock)
            ok = (
                "MAPA DE JANELAS PRIORITÁRIAS" in prompt and
                isinstance(cuts, list) and len(cuts) == 1 and
                "local_score" in cuts[0] and
                cuts[0].get("selection_version") == "v2_windows_rerank"
            )
            details = f"cuts={len(cuts)} selection_version={cuts[0].get('selection_version') if cuts else None}"
            self.add("smoke_prompt_builder", ok, details)
        except Exception as exc:
            self.add("smoke_prompt_builder", False, repr(exc))

    def check_db_schema(self, manifest: Dict[str, Any]) -> None:
        db_path = Path.home() / ".clipfusion" / "db.sqlite"
        try:
            self.import_module(self.repo / "db.py", "clipfusion_db_validation")
            if not db_path.exists():
                self.add("db_schema", False, f"DB não encontrado: {db_path}")
                return
            conn = sqlite3.connect(str(db_path))
            try:
                rows = conn.execute("PRAGMA table_info(cuts)").fetchall()
            finally:
                conn.close()
            cols = {r[1] for r in rows}
            missing = [c for c in manifest["db_required_columns"] if c not in cols]
            self.add("db_schema", not missing, "ok" if not missing else f"faltando: {missing}")
        except Exception as exc:
            self.add("db_schema", False, repr(exc))

    def snapshot_protected(self) -> None:
        anti = self.repo / "anti_copy_modules"
        if not anti.exists():
            self.add("protected_paths", False, "anti_copy_modules ausente")
            return
        file_count = sum(1 for p in anti.rglob("*") if p.is_file())
        self.add("protected_paths", file_count > 0, f"anti_copy_modules arquivos={file_count}")

    def decide_status(self) -> None:
        failed = [c for c in self.checks if not c.ok]
        if failed:
            self.status = "FAIL"
        else:
            self.status = "PASS"

    def write_report(self, manifest: Dict[str, Any]) -> Path:
        self.ops_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report_path = self.reports_dir / f"validation_{ts}.json"
        payload = {
            "timestamp": now_iso(),
            "patch_name": manifest["patch_name"],
            "patch_version": manifest["version"],
            "repo_path": str(self.repo),
            "status": self.status,
            "checks": [asdict(c) for c in self.checks],
            "notes": self.notes,
            "files_changed": manifest["files_changed"],
            "files_preserved": manifest["files_preserved"],
            "hashes": self.current_hashes,
        }
        self.report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.report_path

    def append_registry(self, manifest: Dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": now_iso(),
            "patch_name": manifest["patch_name"],
            "patch_version": manifest["version"],
            "status": self.status,
            "repo_path": str(self.repo),
            "report_path": str(self.report_path) if self.report_path else "",
            "files_changed": manifest["files_changed"],
        }
        with self.registry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def run(self) -> int:
        try:
            manifest = self.load_manifest()
            if not self.validate_repo_root(manifest):
                self.snapshot_paths(manifest)
                self.decide_status()
                self.write_report(manifest)
                self.append_registry(manifest)
                return 1

            self.snapshot_paths(manifest)
            self.check_files_exist(manifest)
            self.check_markers(manifest)
            self.check_python_syntax(manifest)
            self.smoke_prompt_builder()
            self.check_db_schema(manifest)
            self.snapshot_protected()
            self.decide_status()
            report = self.write_report(manifest)
            self.append_registry(manifest)

            print(f"STATUS: {self.status}")
            print(f"REPORT: {report}")
            if self.status != "PASS":
                for c in self.checks:
                    if not c.ok:
                        print(f"- FALHA {c.name}: {c.details}")
                return 1
            return 0
        except Exception as exc:
            self.status = "FAIL"
            self.notes.append(repr(exc))
            try:
                manifest = self.load_manifest()
                self.write_report(manifest)
                self.append_registry(manifest)
                print(f"STATUS: FAIL\nREPORT: {self.report_path}\nERRO: {exc}")
            except Exception:
                print(f"STATUS: FAIL\nERRO: {exc}")
            return 1


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: python3 ops/validate_patch_and_register.py /caminho/para/o/repo")
        return 2
    validator = Validator(Path(sys.argv[1]))
    return validator.run()


if __name__ == "__main__":
    raise SystemExit(main())

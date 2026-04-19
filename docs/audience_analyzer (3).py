"""ClipFusion — Audience Analyzer. Perfis demográficos por nicho."""
import json, os

PERFIS_BUILTIN = {
    "investimentos": {
        "faixa_etaria": "25–40", "genero": "neutro",
        "interesses": ["dinheiro", "liberdade financeira", "renda extra"],
        "dores": ["medo de perder", "falta de tempo", "informação complexa"],
        "palavras_chave": ["renda passiva", "primeiro milhão", "juros compostos"],
        "tom": "motivacional, educativo, direto",
        "exemplos_cta": ["Quer começar? Comenta 'EU QUERO'", "Salva pra ver depois"],
    },
    "fitness": {
        "faixa_etaria": "18–35", "genero": "feminino predominante",
        "interesses": ["emagrecimento", "saúde", "bem-estar"],
        "dores": ["falta de tempo", "dieta restritiva", "resultados lentos"],
        "palavras_chave": ["treino rápido", "queima de gordura", "antes e depois"],
        "tom": "energético, encorajador",
        "exemplos_cta": ["Marca uma amiga!", "Compartilha com quem está começando"],
    },
    "tecnologia": {
        "faixa_etaria": "20–45", "genero": "masculino predominante",
        "interesses": ["programação", "IA", "carreira tech"],
        "dores": ["ficar desatualizado", "dificuldade de aprendizado"],
        "palavras_chave": ["inteligência artificial", "carreira", "inovação"],
        "tom": "analítico, inspirador, descontraído",
        "exemplos_cta": ["Compartilha com um amigo dev!"],
    },
    "empreendedorismo": {
        "faixa_etaria": "22–45", "genero": "neutro",
        "interesses": ["negócios", "vendas", "crescimento"],
        "dores": ["falta de clientes", "gestão de tempo", "competição"],
        "palavras_chave": ["escalar", "faturamento", "estratégia"],
        "tom": "direto, provocativo, inspirador",
        "exemplos_cta": ["Comenta 'QUERO' pra receber mais", "Salva pra aplicar"],
    },
    "relacionamentos": {
        "faixa_etaria": "18–40", "genero": "neutro",
        "interesses": ["comunicação", "autoconhecimento", "amor"],
        "dores": ["conflitos", "solidão", "comunicação difícil"],
        "palavras_chave": ["casal", "autoestima", "relacionamento saudável"],
        "tom": "empático, direto, acolhedor",
        "exemplos_cta": ["Marca alguém que precisa ouvir isso", "Salva pra refletir"],
    },
}

DEFAULT_PERFIL = {
    "faixa_etaria": "18–45", "genero": "neutro",
    "interesses": ["aprender", "entretenimento"],
    "dores": ["falta de tempo", "informação complexa"],
    "palavras_chave": ["viral", "dica", "rápido"],
    "tom": "motivacional, direto",
    "exemplos_cta": ["Compartilha com quem precisa!", "Salva pra ver depois"],
}


class AudienceAnalyzer:
    def __init__(self):
        self.perfis = dict(PERFIS_BUILTIN)
        custom = os.path.join(os.path.dirname(__file__), "..", "config", "perfis_nicho.json")
        if os.path.exists(custom):
            with open(custom, encoding="utf-8") as f:
                self.perfis.update(json.load(f))

    def analyze(self, nicho: str, platform: str) -> dict:
        nicho_low = nicho.lower()
        perfil = next(
            (v for k, v in self.perfis.items() if k in nicho_low or nicho_low in k),
            DEFAULT_PERFIL)
        grupo_sec = {"nome": "Interessados em produtividade",
                     "angulo_gancho": "Como isso afeta sua rotina?",
                     "expansao_potencial": "25%"}
        timing = {"tiktok": ["18h–22h","12h–14h"], "instagram": ["19h–21h","11h–13h"],
                  "youtube": ["14h–16h","19h–21h"]}.get(platform, ["18h–22h"])
        return {
            "perfil_primario": perfil, "grupo_secundario": grupo_sec,
            "timing_otimo": timing,
            "hashtags_sugeridas": [f"#{nicho.replace(' ','')}", "#viral", "#dica", "#conteudo", "#shorts"],
        }

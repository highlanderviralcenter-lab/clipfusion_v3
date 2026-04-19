"""ClipFusion — Motor de Análise Viral Completo (Auto-contido).

Motor completo de análise viral para conteúdo de vídeo.
Auto-contido, sem dependências externas além de re, json, random.
"""
import re
import json
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Nicho(Enum):
    INVESTIMENTOS = "investimentos"
    FITNESS = "fitness"
    TECNOLOGIA = "tecnologia"
    RELACIONAMENTOS = "relacionamentos"
    EMPREENDEDORISMO = "empreendedorismo"
    GERAL = "geral"


class Archetype(Enum):
    DESPERTAR = "despertar"
    TENSAO = "tensao"
    CONFRONTO = "confronto"
    VIRADA = "virada"
    REVELACAO = "revelacao"
    JUSTO_ENGOLIDO = "justo_engolido"
    TRANSFORMACAO = "transformacao"
    RESOLUCAO = "resolucao"
    IMPACTO = "impacto"
    ENCERRAMENTO = "encerramento"


class Platform(Enum):
    TIKTOK = "tiktok"
    REELS = "reels"
    SHORTS = "shorts"


@dataclass
class Cut:
    id: str
    text: str
    duration: float
    start_time: float = 0.0
    viral_score: float = 0.0
    platform: Optional[Platform] = None
    hooks: List[str] = field(default_factory=list)
    archetype: Optional[Archetype] = None


class ViralEngine:
    """
    Motor completo de análise viral para conteúdo de vídeo.
    Auto-contido, sem dependências externas além de re, json, random.
    """

    # Keywords por nicho para detecção automática
    NICHO_KEYWORDS = {
        Nicho.INVESTIMENTOS: [
            "dinheiro", "investir", "ação", "bolsa", "dividendo", "riqueza",
            "milionário", "patrimônio", "juros", "compostos", "crypto", "bitcoin",
            "renda", "passiva", "fiis", "fundos", "poupança", "banco", "lucro",
            "trading", "swing trade", "day trade", "finanças", "economia"
        ],
        Nicho.FITNESS: [
            "muscle", "academia", "treino", "dieta", "proteína", "emagrecer",
            "gordura", "definição", "hipertrofia", "suplemento", "whey", "creatina",
            "cardio", "musculação", "corpo", "físico", "saúde", "nutrição",
            "caloria", "metabolismo", "exercício", "força", "resistência"
        ],
        Nicho.TECNOLOGIA: [
            "ai", "inteligência artificial", "código", "programar", "software",
            "app", "aplicativo", "startup", "tech", "gadget", "smartphone",
            "computador", "internet", "digital", "automação", "robô", "algoritmo",
            "dados", "cloud", "nuvem", "blockchain", "metaverso", "tecnologia"
        ],
        Nicho.RELACIONAMENTOS: [
            "namoro", "casamento", "relacionamento", "paixão", "amor", "traição",
            "ciúmes", "conquista", "sedução", "match", "tinder", "ex", "crush",
            "beijo", "sexo", "intimidade", "compromisso", "noivo", "noiva",
            "divórcio", "separação", "ficante", "friendzone"
        ],
        Nicho.EMPREENDEDORISMO: [
            "negócio", "empresa", "startup", "vendas", "cliente", "produto",
            "serviço", "lucro", "faturamento", "escalar", "marketing", "empreender",
            "sócio", "investidor", "pitch", "mvp", "bootstrapping", "burn rate",
            "saas", "ecommerce", "dropshipping", "afiliado", "infoproduto"
        ]
    }

    # Templates de hooks por arquétipo
    HOOK_TEMPLATES = {
        Archetype.DESPERTAR: [
            "Você não vai acreditar no que descobri sobre {tema}...",
            "Acabei de ter uma revelação sobre {tema} que mudou tudo.",
            "Pare tudo o que está fazendo. Isso sobre {tema} é importante."
        ],
        Archetype.TENSAO: [
            "O que vou te contar sobre {tema} pode te deixar irritado...",
            "Tem algo sobre {tema} que ninguém quer que você saiba.",
            "Estou nervoso em falar isso, mas sobre {tema}..."
        ],
        Archetype.CONFRONTO: [
            "Discordo 100% de quem fala assim sobre {tema}.",
            "Vou ser cancelado por falar a verdade sobre {tema}.",
            "Todo mundo está errado sobre {tema} e vou provar."
        ],
        Archetype.VIRADA: [
            "Pensei que entendia {tema} até descobrir isso...",
            "Minha vida mudou quando parei de acreditar nisso sobre {tema}.",
            "O plot twist sobre {tema} que ninguém esperava."
        ],
        Archetype.REVELACAO: [
            "O segredo que os experts em {tema} escondem de você.",
            "Finalmente vou revelar a verdade sobre {tema}.",
            "O segredo mais bem guardado do mundo de {tema}."
        ],
        Archetype.JUSTO_ENGOLIDO: [
            "Fui enganado sobre {tema} por anos... até hoje.",
            "Como me prejudiquei acreditando em mentiras sobre {tema}.",
            "A mentira sobre {tema} que me custou caro."
        ],
        Archetype.TRANSFORMACAO: [
            "De {estado_ruim} para {estado_bom} em {tempo} com {tema}.",
            "Como {tema} transformou minha vida completamente.",
            "O antes e depois que {tema} fez na minha realidade."
        ],
        Archetype.RESOLUCAO: [
            "Resolvi meu maior problema com {tema} assim...",
            "A solução definitiva para {tema} finalmente chegou.",
            "Chega de sofrer com {tema}. Faça isso agora."
        ],
        Archetype.IMPACTO: [
            "Isso sobre {tema} vai chocar você.",
            "Números brutais sobre {tema} que ninguém mostra.",
            "A realidade dura sobre {tema} que precisa ser dita."
        ],
        Archetype.ENCERRAMENTO: [
            "E foi assim que {tema} mudou minha vida para sempre.",
            "A lição final sobre {tema} que você precisa aprender.",
            "Terminei minha jornada com {tema} e esse foi o resultado."
        ]
    }

    # Gatilhos emocionais por nicho
    GATILHOS_POR_NICHO = {
        Nicho.INVESTIMENTOS: ["ganância", "medo de perder", "status", "liberdade financeira", "prova social"],
        Nicho.FITNESS: ["insegurança corporal", "desejo de aprovação", "competição", "saúde", "disciplina"],
        Nicho.TECNOLOGIA: ["FOMO tecnológico", "produtividade", "futurismo", "automação de tarefas", "vantagem competitiva"],
        Nicho.RELACIONAMENTOS: ["medo de solidão", "desejo de conexão", "ciúmes", "validação afetiva", "competitividade social"],
        Nicho.EMPREENDEDORISMO: ["medo de fracasso", "desejo de liberdade", "status", "legado", "independência"],
        Nicho.GERAL: ["curiosidade", "medo de ficar de fora", "desejo de pertencimento", "surpresa", "empatia"]
    }

    # Dores por nicho
    DORES_POR_NICHO = {
        Nicho.INVESTIMENTOS: ["perder dinheiro", "não saber onde investir", "inflação corroendo poupança", "trabalhar até morrer"],
        Nicho.FITNESS: ["não ver resultados", "falta de tempo", "alimentação restritiva", "comparação com outros"],
        Nicho.TECNOLOGIA: ["ficar para trás", "complexidade técnica", "custo de ferramentas", "sobrecarga de informação"],
        Nicho.RELACIONAMENTOS: ["rejeição", "trauma passado", "falta de autoconfiança", "padrões tóxicos"],
        Nicho.EMPREENDEDORISMO: ["falta de dinheiro", "medo de falhar", "concorrência forte", "falta de clientes"],
        Nicho.GERAL: ["estagnação", "procrastinação", "falta de propósito", "comparação social"]
    }

    # Horários ótimos por plataforma e nicho
    HORARIOS_OTIMOS = {
        Platform.TIKTOK: {
            "geral": ["08:00", "12:00", "19:00", "21:00"],
            Nicho.INVESTIMENTOS: ["07:00", "12:30", "18:00"],
            Nicho.FITNESS: ["06:00", "12:00", "17:00"],
            Nicho.TECNOLOGIA: ["08:00", "13:00", "20:00"],
            Nicho.RELACIONAMENTOS: ["20:00", "22:00", "23:00"],
            Nicho.EMPREENDEDORISMO: ["07:00", "12:00", "19:00"]
        },
        Platform.REELS: {
            "geral": ["09:00", "13:00", "18:00", "20:00"],
            Nicho.INVESTIMENTOS: ["08:00", "13:00", "19:00"],
            Nicho.FITNESS: ["07:00", "12:00", "18:00"],
            Nicho.TECNOLOGIA: ["09:00", "14:00", "21:00"],
            Nicho.RELACIONAMENTOS: ["12:00", "19:00", "21:00"],
            Nicho.EMPREENDEDORISMO: ["08:00", "13:00", "20:00"]
        },
        Platform.SHORTS: {
            "geral": ["10:00", "14:00", "16:00", "20:00"],
            Nicho.INVESTIMENTOS: ["09:00", "15:00", "19:00"],
            Nicho.FITNESS: ["08:00", "14:00", "17:00"],
            Nicho.TECNOLOGIA: ["10:00", "15:00", "21:00"],
            Nicho.RELACIONAMENTOS: ["14:00", "20:00", "22:00"],
            Nicho.EMPREENDEDORISMO: ["09:00", "14:00", "19:00"]
        }
    }

    # Palavras de alta retenção (curiosidade imediata)
    PALAVRAS_GANCHO = [
        "segredo", "revelação", "chocante", "inesperado", "proibido",
        "bombástico", "exclusivo", "urgente", "alerta", "descoberta",
        "mentira", "verdade", "manipulação", "golpe", "truque"
    ]

    # Palavras de alta shareabilidade (emoção viral)
    PALAVRAS_SHARE = [
        "indignante", "inacreditável", "emocionante", "revoltante",
        "inspirador", "destruidor", "transformador", "essencial",
        "obrigatório", "vital", "crucial", "definidor"
    ]

    # Palavras de comentabilidade (polêmica/dúvida)
    PALAVRAS_COMENTARIO = [
        "discordo", "concorda?", "errado", "certo", "deveria",
        "injusto", "justo", "exagero", "mentira", "verdade",
        "opinião", "discordam", "comentem", "o que acham"
    ]

    def __init__(self):
        self._cache_nicho = {}

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrai palavras-chave significativas do texto."""
        text_lower = text.lower()
        words = re.findall(r'\b[a-záéíóúãõâêîôûàèìòùç]{3,}\b', text_lower)
        stopwords = {'que', 'como', 'para', 'mas', 'por', 'são', 'sua', 'esse',
                     'essa', 'este', 'esta', 'tudo', 'toda', 'todo', 'muito',
                     'mais', 'quando', 'onde', 'porque', 'porquê', 'assim',
                     'mesmo', 'ainda', 'depois', 'antes', 'agora', 'aqui'}
        return [w for w in words if w not in stopwords and len(w) > 3]

    def detect_nicho(self, transcription: str) -> Nicho:
        """Detecta automaticamente o nicho baseado em keywords."""
        if not transcription:
            return Nicho.GERAL

        text_lower = transcription.lower()
        scores = {}

        for nicho, keywords in self.NICHO_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            words = self._extract_keywords(transcription)
            score += sum(2 for w in words if any(kw in w for kw in keywords))
            scores[nicho] = score

        if not scores or max(scores.values()) == 0:
            return Nicho.GERAL

        return max(scores, key=scores.get)

    def analyze_audience(self, transcription: str) -> Dict[str, Any]:
        """Analisa a audiência e retorna perfil demográfico e comportamental."""
        nicho = self.detect_nicho(transcription)

        idade_map = {
            Nicho.INVESTIMENTOS: {"min": 25, "max": 45, "media": 32},
            Nicho.FITNESS: {"min": 18, "max": 35, "media": 26},
            Nicho.TECNOLOGIA: {"min": 18, "max": 40, "media": 28},
            Nicho.RELACIONAMENTOS: {"min": 18, "max": 35, "media": 24},
            Nicho.EMPREENDEDORISMO: {"min": 22, "max": 45, "media": 30},
            Nicho.GERAL: {"min": 18, "max": 45, "media": 28}
        }

        idade_info = idade_map.get(nicho, idade_map[Nicho.GERAL])
        gatilhos = self.GATILHOS_POR_NICHO.get(nicho, self.GATILHOS_POR_NICHO[Nicho.GERAL])
        dores = self.DORES_POR_NICHO.get(nicho, self.DORES_POR_NICHO[Nicho.GERAL])

        horarios = {
            "tiktok": self.HORARIOS_OTIMOS[Platform.TIKTOK].get(nicho,
                     self.HORARIOS_OTIMOS[Platform.TIKTOK]["geral"]),
            "reels": self.HORARIOS_OTIMOS[Platform.REELS].get(nicho,
                    self.HORARIOS_OTIMOS[Platform.REELS]["geral"]),
            "shorts": self.HORARIOS_OTIMOS[Platform.SHORTS].get(nicho,
                     self.HORARIOS_OTIMOS[Platform.SHORTS]["geral"])
        }

        tons = {
            Nicho.INVESTIMENTOS: "autoritário mas acessível, dados concretos",
            Nicho.FITNESS: "motivacional, energético, disciplinado",
            Nicho.TECNOLOGIA: "curioso, explicativo, futurista",
            Nicho.RELACIONAMENTOS: "empático, direto, vulnerável",
            Nicho.EMPREENDEDORISMO: "inspirador, prático, transparente",
            Nicho.GERAL: "conversacional, autêntico, dinâmico"
        }

        return {
            "nicho_detectado": nicho.value,
            "demografia": {
                "idade_media": idade_info["media"],
                "faixa_etaria": f"{idade_info['min']}-{idade_info['max']} anos",
                "genero_predominante": "unissex" if nicho in [Nicho.TECNOLOGIA, Nicho.GERAL] else "variável"
            },
            "psicografia": {
                "dores_principais": dores,
                "gatilhos_emocionais": gatilhos,
                "desejos_ocultos": self._extract_desires(nicho),
                "objecoes_comuns": self._extract_objections(nicho)
            },
            "comportamento": {
                "horarios_otimos_postagem": horarios,
                "frequencia_ideal": "diária" if nicho in [Nicho.FITNESS, Nicho.RELACIONAMENTOS] else "3-5x semana",
                "tom_recomendado": tons.get(nicho, tons[Nicho.GERAL])
            },
            "keywords_detectadas": self._extract_keywords(transcription)[:10]
        }

    def _extract_desires(self, nicho: Nicho) -> List[str]:
        """Extrai desejos profundos por nicho."""
        desires = {
            Nicho.INVESTIMENTOS: ["liberdade financeira", "segurança", "status", "autonomia"],
            Nicho.FITNESS: ["corpo ideal", "saúde", "disciplina", "autoconfiança"],
            Nicho.TECNOLOGIA: ["eficiência", "vantagem competitiva", "modernidade", "poder"],
            Nicho.RELACIONAMENTOS: ["conexão genuína", "amor recíproco", "segurança afetiva", "validação"],
            Nicho.EMPREENDEDORISMO: ["liberdade de tempo", "reconhecimento", "impacto", "riqueza"],
            Nicho.GERAL: ["crescimento pessoal", "felicidade", "equilíbrio", "realização"]
        }
        return desires.get(nicho, desires[Nicho.GERAL])

    def _extract_objections(self, nicho: Nicho) -> List[str]:
        """Extrai objeções comuns por nicho."""
        objections = {
            Nicho.INVESTIMENTOS: ["não tenho dinheiro", "é muito arriscado", "não entendo de finanças"],
            Nicho.FITNESS: ["não tenho tempo", "genética ruim", "gym bro intimidante"],
            Nicho.TECNOLOGIA: ["é muito complexo", "vai me substituir", "não sou técnico"],
            Nicho.RELACIONAMENTOS: ["não sou bom o suficiente", "vou magoar de novo", "não confio em ninguém"],
            Nicho.EMPREENDEDORISMO: ["posso falhar", "mercado saturado", "preciso de dinheiro para começar"],
            Nicho.GERAL: ["não sou capaz", "já tentei e não deu", "medo do julgamento"]
        }
        return objections.get(nicho, objections[Nicho.GERAL])

    def detect_archetype(self, text: str) -> Archetype:
        """Detecta o arquétipo emocional predominante no texto."""
        text_lower = text.lower()

        patterns = {
            Archetype.DESPERTAR: ["acordei", "percebi", "descobri", "abri os olhos", "não sabia que"],
            Archetype.TENSAO: ["tensão", "suspeito", "algo errado", "estranho", "inquietante"],
            Archetype.CONFRONTO: ["discordo", "você está errado", "mentira", "enganação", "farsa"],
            Archetype.VIRADA: ["quando descobri", "mudou tudo", "plot twist", "virada", "reviravolta"],
            Archetype.REVELACAO: ["segredo", "revelar", "finalmente", "a verdade", "o que escondem"],
            Archetype.JUSTO_ENGOLIDO: ["fui enganado", "acreditei", "manipulado", "mentira", "iludido"],
            Archetype.TRANSFORMACAO: ["mudei", "transformei", "evoluí", "antes e depois", "deixei de ser"],
            Archetype.RESOLUCAO: ["resolvi", "solução", "acabou", "finalizei", "concluí"],
            Archetype.IMPACTO: ["chocado", "impactado", "números", "dados", "estatística", "prova"],
            Archetype.ENCERRAMENTO: ["conclusão", "aprendi", "lição", "encerramento", "final"]
        }

        scores = {archetype: 0 for archetype in Archetype}

        for archetype, keywords in patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[archetype] += 1

        if max(scores.values()) == 0:
            if "?" in text and text_lower.startswith(("você", "já", "por que")):
                return Archetype.DESPERTAR
            elif "!" in text and len(text) < 100:
                return Archetype.IMPACTO
            elif any(w in text_lower for w in ["antes", "depois", "agora"]):
                return Archetype.TRANSFORMACAO
            else:
                return Archetype.REVELACAO

        return max(scores, key=scores.get)

    def generate_hooks(self, cut: Cut, archetype: Optional[Archetype] = None) -> List[Dict[str, Any]]:
        """Gera 3 variações de hook para um corte específico."""
        if archetype is None:
            archetype = self.detect_archetype(cut.text)

        keywords = self._extract_keywords(cut.text)
        tema = keywords[0] if keywords else "isso"

        templates = self.HOOK_TEMPLATES.get(archetype, self.HOOK_TEMPLATES[Archetype.REVELACAO])

        hooks = []
        used_templates = random.sample(templates, min(3, len(templates)))

        for i, template in enumerate(used_templates):
            hook_text = template.format(
                tema=tema,
                estado_ruim="quebrado" if i == 0 else "perdido",
                estado_bom="milionário" if i == 0 else "bem-sucedido",
                tempo="1 ano" if i == 0 else "90 dias"
            )

            score_curiosidade = self._score_curiosity(hook_text)
            score_urgencia = self._score_urgency(hook_text)
            score_emocao = self._score_emotion(hook_text)

            total_score = (score_curiosidade + score_urgencia + score_emocao) / 3

            hooks.append({
                "hook": hook_text,
                "archetype": archetype.value,
                "scoring": {
                    "curiosidade": round(score_curiosidade, 1),
                    "urgencia": round(score_urgencia, 1),
                    "emocao": round(score_emocao, 1),
                    "total": round(total_score, 1)
                },
                "estimativa_retencao": f"{min(95, int(total_score * 0.9))}%"
            })

        hooks.sort(key=lambda x: x["scoring"]["total"], reverse=True)
        return hooks

    def _score_curiosity(self, text: str) -> float:
        """Score de 0-100 para curiosidade gerada."""
        score = 50.0
        text_lower = text.lower()

        curiosity_words = ["segredo", "revelação", "descobri", "não vai acreditar",
                          "ninguém sabe", "escondido", "proibido", "mistério"]

        for word in curiosity_words:
            if word in text_lower:
                score += 8

        score += text.count("?") * 5
        score += text.count("...") * 3

        return min(100, score)

    def _score_urgency(self, text: str) -> float:
        """Score de 0-100 para senso de urgência."""
        score = 40.0
        text_lower = text.lower()

        urgency_words = ["agora", "imediato", "urgente", "hoje", "não perca",
                        "última chance", "antes que", "corra", "aviso"]

        for word in urgency_words:
            if word in text_lower:
                score += 10

        score += text.count("!") * 4

        return min(100, score)

    def _score_emotion(self, text: str) -> float:
        """Score de 0-100 para carga emocional."""
        score = 45.0
        text_lower = text.lower()

        emotion_words = ["chocante", "incrível", "revoltante", "inspirador",
                        "destruidor", "transformador", "indignante", "emocionante"]

        for word in emotion_words:
            if word in text_lower:
                score += 12

        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        score += caps_ratio * 20

        return min(100, score)

    def score_cut(self, cut_text: str, duration: float) -> Dict[str, Any]:
        """Analisa um corte e retorna viral score completo."""
        text_lower = cut_text.lower()

        retencao = self._estimate_retention(cut_text, duration)
        shareability = self._estimate_shareability(cut_text)
        comentabilidade = self._estimate_commentability(cut_text)
        watch_time = self._estimate_watch_time(cut_text, duration)

        viral_score = (
            retencao * 0.35 +
            shareability * 0.30 +
            comentabilidade * 0.20 +
            watch_time * 0.15
        )

        archetype = self.detect_archetype(cut_text)
        hooks = self.generate_hooks(Cut(id="temp", text=cut_text, duration=duration), archetype)

        platform = self._suggest_platform(cut_text, duration, viral_score)

        return {
            "viral_score": round(viral_score, 1),
            "classificacao": self._classify_score(viral_score),
            "metricas": {
                "retencao_estimada": round(retencao, 1),
                "shareability": round(shareability, 1),
                "comentabilidade": round(comentabilidade, 1),
                "watch_time_potencial": round(watch_time, 1)
            },
            "analise_conteudo": {
                "archetype_detectado": archetype.value,
                "palavras_gancho_encontradas": [w for w in self.PALAVRAS_GANCHO if w in text_lower],
                "sentimento_predominante": self._detect_sentiment(cut_text),
                "complexidade": "baixa" if len(cut_text.split()) < 50 else "média" if len(cut_text.split()) < 100 else "alta"
            },
            "recomendacoes": {
                "melhor_plataforma": platform.value,
                "hooks_sugeridos": hooks,
                "duracao_otima": self._suggest_duration(platform, viral_score),
                "pontos_melhoria": self._suggest_improvements(viral_score, retencao, shareability)
            }
        }

    def _estimate_retention(self, text: str, duration: float) -> float:
        """Estima retenção baseada no gancho inicial."""
        score = 60.0
        text_lower = text.lower()

        first_words = " ".join(text_lower.split()[:10])

        for word in self.PALAVRAS_GANCHO:
            if word in first_words:
                score += 15

        if 15 <= duration <= 45:
            score += 10
        elif duration > 90:
            score -= 15

        if text.startswith(("O que", "Por que", "Como", "Você")):
            score += 8

        return min(100, max(0, score))

    def _estimate_shareability(self, text: str) -> float:
        """Estima propensão a compartilhamento."""
        score = 40.0
        text_lower = text.lower()

        for word in self.PALAVRAS_SHARE:
            if word in text_lower:
                score += 12

        story_markers = ["quando eu", "nunca vou esquecer", "o dia que", "minha vida mudou"]
        for marker in story_markers:
            if marker in text_lower:
                score += 10

        if any(w in text_lower for w in ["todo mundo", "ninguém", "geral", "milhares"]):
            score += 8

        if any(w in text_lower for w in ["2024", "2025", "agora", "hoje em dia"]):
            score += 5

        return min(100, score)

    def _estimate_commentability(self, text: str) -> float:
        """Estima propensão a comentários."""
        score = 35.0
        text_lower = text.lower()

        for word in self.PALAVRAS_COMENTARIO:
            if word in text_lower:
                score += 10

        polarizing = ["mas isso é mentira", "a verdade é", "vocês não estão prontos",
                     "vou ser sincero", "opinião impopular"]
        for p in polarizing:
            if p in text_lower:
                score += 15

        if any(w in text_lower for w in ["comenta", "comentem", "o que acham", "discordam?"]):
            score += 20

        controversy = ["errado", "certo", "deveria", "nunca", "sempre"]
        cont_count = sum(1 for c in controversy if c in text_lower)
        score += cont_count * 3

        return min(100, score)

    def _estimate_watch_time(self, text: str, duration: float) -> float:
        """Estima watch time potencial."""
        score = 50.0

        words = len(text.split())
        density = words / max(duration, 1)

        if 2 <= density <= 4:
            score += 20
        elif density > 5:
            score -= 10

        continuity = ["então", "depois", "por isso", "porque", "mas", "e por fim"]
        text_lower = text.lower()
        cont_score = sum(3 for c in continuity if c in text_lower)
        score += min(cont_score, 15)

        if any(w in text_lower[-50:] for w in ["...", "você não imagina", "e adivinha", "o pior ainda vem"]):
            score += 15

        return min(100, score)

    def _detect_sentiment(self, text: str) -> str:
        """Detecta sentimento predominante."""
        text_lower = text.lower()

        positive = ["amor", "incrível", "fantástico", "melhor", "sucesso", "feliz", "conquista"]
        negative = ["ódio", "pior", "terrível", "fracasso", "triste", "raiva", "decepção"]
        neutral = ["importante", "necessário", "fato", "dado", "estudo", "pesquisa"]

        pos_count = sum(1 for p in positive if p in text_lower)
        neg_count = sum(1 for n in negative if n in text_lower)
        neu_count = sum(1 for n in neutral if n in text_lower)

        if pos_count > neg_count and pos_count > neu_count:
            return "positivo"
        elif neg_count > pos_count and neg_count > neu_count:
            return "negativo"
        elif neu_count > pos_count and neu_count > neg_count:
            return "neutro/informativo"
        else:
            return "misto"

    def _suggest_platform(self, text: str, duration: float, viral_score: float) -> Platform:
        """Sugere melhor plataforma baseada em características do conteúdo."""
        text_lower = text.lower()

        tiktok_score = 0
        if duration <= 30:
            tiktok_score += 2
        if any(w in text_lower for w in ["trend", "desafio", "dueto", "react"]):
            tiktok_score += 3
        if viral_score > 75:
            tiktok_score += 1

        reels_score = 0
        if 30 <= duration <= 60:
            reels_score += 2
        if any(w in text_lower for w in ["lifestyle", "rotina", "aesthetic", "visual"]):
            reels_score += 3
        if viral_score > 60:
            reels_score += 1

        shorts_score = 0
        if any(w in text_lower for w in ["como", "tutorial", "dica", "guia", "aprenda"]):
            shorts_score += 3
        if duration <= 45:
            shorts_score += 2
        if viral_score > 50:
            shorts_score += 1

        scores = {Platform.TIKTOK: tiktok_score,
                 Platform.REELS: reels_score,
                 Platform.SHORTS: shorts_score}

        return max(scores, key=scores.get)

    def _suggest_duration(self, platform: Platform, viral_score: float) -> str:
        """Sugere duração ótima."""
        if platform == Platform.TIKTOK:
            return "15-30s" if viral_score > 70 else "30-45s"
        elif platform == Platform.REELS:
            return "30-60s" if viral_score > 65 else "15-30s"
        else:
            return "45-60s" if viral_score > 60 else "30-45s"

    def _suggest_improvements(self, viral_score: float, retencao: float, share: float) -> List[str]:
        """Sugere melhorias baseadas nas métricas."""
        suggestions = []

        if viral_score < 60:
            suggestions.append("Considerar refazer o gancho inicial - score muito baixo")

        if retencao < 50:
            suggestions.append("Primeiros 3 segundos precisam de mais impacto imediato")
            suggestions.append("Usar pattern interrupt visual no início")

        if share < 50:
            suggestions.append("Aumentar carga emocional ou storytelling")
            suggestions.append("Incluir elemento de surpresa ou revelação")

        if not suggestions:
            suggestions.append("Manter formato atual - performance satisfatória")
            if viral_score > 80:
                suggestions.append("Considere fazer versões em outros formatos (carrossel, texto)")

        return suggestions

    def _classify_score(self, score: float) -> str:
        """Classifica o score viral."""
        if score >= 80:
            return "EXCELENTE (Alta probabilidade de viralização)"
        elif score >= 60:
            return "BOM (Potencial de bom desempenho)"
        elif score >= 40:
            return "REGULAR (Necessita otimização)"
        else:
            return "BAIXO (Recomendado descartar ou refazer)"

    def rank_cuts(self, cuts_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Recebe lista de cortes e retorna ordenado por viral_score."""
        scored_cuts = []

        for cut_data in cuts_list:
            cut = Cut(
                id=cut_data.get("id", str(random.randint(1000, 9999))),
                text=cut_data.get("text", ""),
                duration=cut_data.get("duration", 30.0)
            )

            score_result = self.score_cut(cut.text, cut.duration)
            cut.viral_score = score_result["viral_score"]
            cut.platform = Platform(score_result["recomendacoes"]["melhor_plataforma"])
            cut.hooks = [h["hook"] for h in score_result["recomendacoes"]["hooks_sugeridos"]]

            scored_cuts.append({
                "cut": cut,
                "full_analysis": score_result
            })

        scored_cuts.sort(key=lambda x: x["cut"].viral_score, reverse=True)

        excelentes = [c for c in scored_cuts if c["cut"].viral_score >= 80]
        bons = [c for c in scored_cuts if 60 <= c["cut"].viral_score < 80]
        regulares = [c for c in scored_cuts if 40 <= c["cut"].viral_score < 60]
        ruins = [c for c in scored_cuts if c["cut"].viral_score < 40]

        matar = [c["cut"].id for c in scored_cuts if c["cut"].viral_score < 60]

        return {
            "ranking_geral": [
                {
                    "rank": i+1,
                    "cut_id": item["cut"].id,
                    "viral_score": item["cut"].viral_score,
                    "classificacao": item["full_analysis"]["classificacao"],
                    "melhor_plataforma": item["cut"].platform.value,
                    "top_hook": item["cut"].hooks[0] if item["cut"].hooks else None
                }
                for i, item in enumerate(scored_cuts)
            ],
            "categorias": {
                "excelentes_80plus": len(excelentes),
                "bons_60_79": len(bons),
                "regulares_40_59": len(regulares),
                "ruins_menos40": len(ruins)
            },
            "recomendacoes_producao": {
                "prioridade_maxima": [c["cut"].id for c in excelentes],
                "produzir_se_houver_tempo": [c["cut"].id for c in bons],
                "descartar_ou_reformular": matar,
                "justificativa_descarte": "Cortes abaixo de 60 pontos têm baixa probabilidade de engajamento positivo"
            },
            "estimativa_performance": {
                "potencial_viral": len(excelentes) > 0,
                "volume_total_analisado": len(cuts_list),
                "taxa_aprovacao": f"{((len(excelentes) + len(bons)) / len(cuts_list) * 100):.1f}%"
            }
        }

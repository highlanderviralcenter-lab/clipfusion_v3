import os
import yaml

class ScoringEngine:
    def __init__(self, config_path=None):
        if config_path is None:
            base_dir = os.path.dirname(__file__)
            config_path = os.path.join(base_dir, '..', 'config', 'scoring.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.hook_keywords = self.config['hook']['keywords']
        self.hook_weights = self.config['hook']['weights']
        self.retention_keywords = self.config['retention']['keywords']
        self.moment_keywords = self.config['moment']['keywords']
        self.shareability_keywords = self.config['shareability']['keywords']

    def hook_strength(self, text, start_time):
        first_3s_text = text
        words = first_3s_text.lower().split()
        presence_score = sum(1 for kw in self.hook_keywords if kw in first_3s_text) / max(len(self.hook_keywords),1)
        position_score = 1.0 if start_time < 3 else 0.5
        intensity = 1.0 if '?' in text or '!' in text else 0.5
        weighted = (
            presence_score * self.hook_weights['presence'] +
            position_score * self.hook_weights['position'] +
            intensity * self.hook_weights['intensity']
        )
        return weighted

    def retention_score(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.retention_keywords) / len(words)
        return min(score * 5, 1.0)

    def moment_strength(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.moment_keywords) / len(words)
        return min(score * 5, 1.0)

    def shareability(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.shareability_keywords) / len(words)
        return min(score * 5, 1.0)

    def platform_fit(self, text, platform):
        word_count = len(text.split())
        if platform == 'tiktok':
            return 1.0 if word_count < 30 else 0.5
        elif platform == 'reels':
            return 1.0 if word_count < 50 else 0.6
        elif platform == 'shorts':
            return 1.0 if word_count < 70 else 0.7
        return 0.5

    def score_candidate(self, candidate):
        text = candidate['text']
        start = candidate['start']
        hook = self.hook_strength(text, start)
        retention = self.retention_score(text)
        moment = self.moment_strength(text)
        share = self.shareability(text)
        tiktok_fit = self.platform_fit(text, 'tiktok')
        reels_fit = self.platform_fit(text, 'reels')
        shorts_fit = self.platform_fit(text, 'shorts')
        platform_fit = (tiktok_fit + reels_fit + shorts_fit) / 3
        combined = (
            hook * 0.3 +
            retention * 0.25 +
            moment * 0.2 +
            share * 0.15 +
            platform_fit * 0.1
        )
        return {
            'hook': hook,
            'retention': retention,
            'moment': moment,
            'shareability': share,
            'platform_fit_tiktok': tiktok_fit,
            'platform_fit_reels': reels_fit,
            'platform_fit_shorts': shorts_fit,
            'combined': combined
        }

#!/usr/bin/env python3
"""赤・青のRGB値を分類する小規模なGaussian Naive Bayesモデル。

学習には合成RGBデータを使用する。実環境に合わせて調整する場合は、
Gazeboカメラから取得したRGBサンプルへの置き換えを検討する。"""
import math
import random


def training_samples():
    rng = random.Random(2026)
    # 照明と素材の反射率の変動を模擬する。
    prototypes = {"red": (205, 43, 45), "blue": (45, 58, 205)}
    rows = []
    for name, mean in prototypes.items():
        for _ in range(200):
            brightness = rng.uniform(0.65, 1.15)
            rgb = [max(0, min(255, int(brightness * v + rng.gauss(0, 15))))
                   for v in mean]
            rows.append((tuple(rgb), name))
    return rows


class GaussianColorClassifier:
    def __init__(self):
        groups = {"red": [], "blue": []}
        for rgb, label in training_samples():
            # RGB値を総和で正規化し、明るさへの依存を抑える。
            s = max(1.0, sum(rgb))
            groups[label].append([c / s for c in rgb])
        self.stats = {}
        for label, data in groups.items():
            mu = [sum(v[j] for v in data) / len(data) for j in range(3)]
            var = [max(0.0006, sum((v[j] - mu[j]) ** 2 for v in data) / len(data))
                   for j in range(3)]
            self.stats[label] = (mu, var)

    def predict(self, rgb):
        if len(rgb) != 3 or not all(0 <= float(v) <= 255 for v in rgb):
            raise ValueError("Expected three RGB values in [0, 255]")
        s = max(1.0, sum(rgb))
        feats = [c / s for c in rgb]
        logp = {}
        for label, (means, variances) in self.stats.items():
            logp[label] = -0.5 * sum(
                math.log(v) + (x - m) ** 2 / v
                for x, m, v in zip(feats, means, variances))
        best = max(logp, key=logp.get)
        gap = logp[best] - logp["blue" if best == "red" else "red"]
        confidence = 1.0 / (1.0 + math.exp(-min(500.0, gap)))
        return best, confidence


if __name__ == "__main__":
    clf = GaussianColorClassifier()
    for rgb in [(220, 35, 40), (40, 65, 220), (110, 110, 110)]:
        print(rgb, clf.predict(rgb))

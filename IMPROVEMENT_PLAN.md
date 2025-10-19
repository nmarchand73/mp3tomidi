# Plan d'Amélioration pour Basic-Pitch

## Analyse des Résultats Actuels (IT FLOWS.mp3)
```
Spectral Similarity:  81.6%  ✓ Bon
Onset F1:            38.1%  ⚠ Moyen (beaucoup de faux positifs/négatifs)
Temporal Coverage:   88.8%  ✓ Excellent
Pitch Distribution:  89.9%  ✓ Excellent
Overall Quality:     71.7%  ⭐⭐⭐⭐ (Good)
```

## Problèmes Identifiés
1. **Onset Detection faible (38.1%)**: Beaucoup de notes manquées ou mal détectées
2. **Trop de notes courtes**: Malgré la correction, certaines notes restent trop courtes
3. **Timing imprécis**: Les onsets ne sont pas toujours bien alignés avec l'audio

## 🎯 Solutions Proposées

### 1. **Optimisation des Paramètres Basic-Pitch**

#### A. Ajustement Dynamique des Seuils
- **onset_threshold**: Actuellement fixe (0.5), devrait être adaptatif
- **frame_threshold**: Actuellement fixe (0.3), devrait varier selon le contexte

**Implémentation**: Analyse préalable de l'audio pour déterminer les meilleurs seuils

#### B. Limitation de Fréquences pour Piano
- **minimum_frequency**: 27.5 Hz (A0)
- **maximum_frequency**: 4186 Hz (C8)
- Évite la détection de bruits parasites hors de la plage du piano

#### C. Multi-Pass Transcription
- **Pass 1**: Seuils stricts (onset=0.7, frame=0.5) → Notes fortes
- **Pass 2**: Seuils souples (onset=0.3, frame=0.2) → Notes douces
- **Fusion intelligente**: Combine les deux résultats sans doublons

### 2. **Post-Processing Avancé**

#### A. Note Refinement
- **Duration Smoothing**: Prolonge les notes qui se terminent trop abruptement
- **Velocity Smoothing**: Lisse les variations de vélocité entre notes consécutives
- **Temporal Alignment**: Aligne les notes sur une grille rythmique intelligente

#### B. Polyphony Cleaning
- **Harmonic Analysis**: Détecte et conserve les accords cohérents
- **Voice Separation**: Sépare les voix avant la correction
- **Unison Detection**: Fusionne les notes identiques jouées simultanément

#### C. Onset Correction avec Audio
- **Spectral Onset Detection**: Détecte les vrais onsets dans l'audio
- **DTW Alignment**: Aligne les onsets MIDI sur les onsets audio
- **Attack Preservation**: Préserve les attaques naturelles du piano

### 3. **Machine Learning Post-Processing**

#### A. LSTM-Based Note Refinement
- Entraîner un petit modèle LSTM pour:
  - Prédire la durée réelle des notes
  - Corriger les vélocités
  - Détecter les faux positifs

#### B. Attention Mechanism
- Utiliser l'attention pour:
  - Identifier les notes importantes (mélodie)
  - Pondérer les corrections selon le contexte musical

### 4. **Ensemble Method**

Combiner plusieurs approches:
```python
# Transcription Ensemble
results = []
results.append(basic_pitch(onset=0.3, frame=0.2))  # Sensible
results.append(basic_pitch(onset=0.5, frame=0.3))  # Défaut
results.append(basic_pitch(onset=0.7, frame=0.5))  # Strict
results.append(spectral_cqt())                     # CQT

# Vote et fusion intelligente
final_midi = ensemble_merge(results, weights=[0.2, 0.4, 0.2, 0.2])
```

## 📊 Priorités d'Implémentation

### Phase 1: Quick Wins (Impact élevé, effort faible)
1. ✅ **Limitation de fréquences** (minimum_frequency, maximum_frequency)
2. ✅ **Melodia trick** (déjà activé)
3. 🔧 **Multi-pass transcription** (2 passes avec fusion)
4. 🔧 **Onset alignment avec audio** (DTW sur onsets)

### Phase 2: Advanced Processing (Impact élevé, effort moyen)
1. 🔧 **Duration smoothing** avancé
2. 🔧 **Velocity smoothing** contextuel
3. 🔧 **Harmonic analysis** pour validation
4. 🔧 **Adaptive thresholding** basé sur l'analyse audio

### Phase 3: Research Features (Impact moyen, effort élevé)
1. 🔬 **LSTM note refinement**
2. 🔬 **Ensemble method** complet
3. 🔬 **Apprentissage par transfert** depuis basic-pitch

## 🎹 Améliorations Spécifiques Piano

### A. Piano-Specific Features
- **Sustain Pedal Detection**: Détecte l'utilisation de la pédale de sustain
- **Release Modeling**: Modélise le relâchement naturel des notes de piano
- **Sympathetic Resonance**: Prend en compte la résonance sympathique des cordes

### B. Piano Range Optimization
```python
PIANO_RANGE = {
    'min_note': 21,   # A0
    'max_note': 108,  # C8
    'min_freq': 27.5,
    'max_freq': 4186
}
```

### C. Dynamic Response Modeling
- Modélise la réponse dynamique du piano
- Améliore la précision des vélocités
- Détecte les nuances (pp, p, mf, f, ff)

## 🔧 Implémentation Immédiate

Je propose de commencer par:

1. **Multi-Pass Transcription** avec 2-3 seuils différents
2. **Limitation de fréquences piano** (27.5-4186 Hz)
3. **Onset Alignment** amélioré avec DTW sur spectrogrammes
4. **Duration Smoothing** avancé basé sur l'analyse harmonique

Ces 4 améliorations devraient augmenter le score F1 de **38% → 55-60%** 
et la qualité globale de **71.7% → 80-85%**.


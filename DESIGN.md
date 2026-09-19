# DESIGN.md : Design System Épuré « Pro Football Analytics » (Inspiration Hudl / Veo / StatsBomb)

## 1. Philosophie & Direction Visuelle
L'interface combine l'élégance éditoriale d'un dashboard pro (**Hudl Sportscode, Veo Editor, StatsBomb IQ**) avec une identité visuelle immédiatement reconnaissable dédiée au football d'élite :
- **Léger, Contrasté & Visible** : Clarté maximale, typographie soignée (`Plus Jakarta Sans` & `JetBrains Mono`), palette warm monochrome avec pastels discrets.
- **Zéro Emoji & Règle Éditoriale Stricte** : Codes pays FIFA textuels (`ARG`, `FRA`, `CRO`, `MAR`), badges d'événements purs (`GOAL`, `ASSIST`, `PENALTY`, `TURNOVER`).
- **Cloisonnement Strict** : Vue tactique 100% métier entraîneur, métriques techniques isolées dans *Supervision & Benchmark*.

---

## 2. Palette Graphique & Surfaces
- **Fond & Surfaces** : Blanc crème chaud & Ardoise très claire (`#F8FAFC` / `#FFFFFF`) avec trame tactique discrète.
- **Accents Pelouse & Tactique** :
  - *Vert Émeraude Pitch* (`#10B981` / `#059669` / `#ECFDF5`) : Badges live, indicateurs de phase et points d'attention.
  - *Violet Améthyste & Indigo* (`#6366F1` / `#4F46E5` / `#EEF2FF`) : Actions clés, boutons et focus tactique.
  - *Ardoise & Graphite Profond* (`#0F172A` / `#334155` / `#64748B`) : Typographie haute lisibilité et fort contraste.
- **Scoreboard HUD Haute Lisibilité** : Fond blanc pur `#FFFFFF` avec bordure `#E2E8F0` et typographie noir ardoise `#0F172A`.

---

## 3. Identité & Actifs Visuels Intégrés
1. **Logo & Favicon de Marque (`foot_gpt_icon_badge.jpg`)** :
   - Icône géométrique hexagonale combinant un ballon de football et des vecteurs de passes tactiques en vert émeraude et violet.
2. **Hero Banner Tactique (`football_tactical_hero.jpg`)** :
   - Rendu 3D isométrique d'un tableau d'analyse tactique pro (Zone 14, demi-espaces / *Halbräume*, réseaux de passes et heatmaps).

---

## 4. Composants Métier Football
- **Bandeau Scoreboard HUD Épuré** : Présentation du match en cours avec codes FIFA, score et phase active.
- **Cartes Match Fixtures Uniformes** : Cartes à hauteur identique avec alignement strict des boutons d'action.
- **Pills de Zones Spatiales** : Étiquetage automatique des actions (`ZONE 14`, `HALF-SPACE`, `ATT. 3RD`, `DEF. 3RD`).
- **Timeline d'Événements Clés** : Flux chronologique compact avec badges textuels uppercase stricts.

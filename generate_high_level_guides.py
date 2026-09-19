"""
Générateur des 3 Guides Tactiques High-Level au format PDF (ReportLab) et Markdown.

Ces guides fournissent le cadre théorique global permettant à l'agent IA d'effectuer
un premier niveau de routage sémantique et de cadrage conceptuel (Hierarchical RAG).
"""

import os
from pathlib import Path
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_DIR = Path("data/high_level_guides")

GUIDE_1_MD = """---
title: "Guide High-Level 1 : Les 4 Phases du Jeu & Principes Opérationnels Fondamentaux"
category: "High-Level Tactical Theory"
level: "Framework / Routing"
---

# Guide High-Level 1 : Les 4 Phases du Jeu & Principes Opérationnels Fondamentaux

## 1. La Structure Universelle du Match : Le Cycle des 4 Phases

Le football moderne est un continuum dynamique non-linéaire articulé autour de 4 moments indissociables. Chaque action offensive porte en elle les germes de la sécurité défensive future, et inversement.

1. **Organisation Offensive (Attaque Placée)** :
   - Objectif : Déséquilibrer le bloc adverse pour créer et exploiter des espaces de finition.
   - Leviers : Utilisation de la largeur maximale pour étirer les lignes adverses, occupation échelonnée des interlignes et recherche de profondeur.
2. **Transition Défensive (Perte de Balle / Attaque -> Défense)** :
   - Objectif : Neutraliser l'attaque rapide adverse immédiatement ou reformer un bloc compact.
   - Choix stratégique : Contre-pressing agressif (Gegenpressing) dans les 5 secondes OU repli axial temporisé pour sécuriser la profondeur.
3. **Organisation Défensive (Bloc Médian / Bas / Haut)** :
   - Objectif : Protéger l'axe central du but, réduire l'espace entre les lignes et orienter la circulation adverse vers les zones inoffensives (les flancs).
   - Leviers : Compacité horizontale (< 35m) et verticale (< 15m), coulissement coordonné sur le temps de passe.
4. **Transition Offensive (Récupération de Balle / Défense -> Attaque)** :
   - Objectif : Exploiter la désorganisation temporaire du bloc adverse qui vient de perdre le ballon.
   - Leviers : Première passe verticale rapide vers l'avant, courses de soutien en rupture et projection dans les demi-espaces libres.

---

## 2. Géométrie du Terrain & Zonage Stratégique

L'analyse de données d'événements (coordonnées x, y) repose sur une grille de lecture spatiale en 5 couloirs verticaux et 3 tiers horizontaux :

- **Les 5 Couloirs Verticaux** :
  1. *Flanc Gauche (Wide Left)* : Zone de débordement, centres et fixation périphérique.
  2. *Demi-Espace Gauche (Left Half-Space / Halbraum)* : Zone décisionnelle clé reliant l'axe et le flanc, offrant un angle diagonal vers le but.
  3. *Couloir Central (Center Lane)* : Zone de menace maximale, chemin le plus direct vers le but, soumise à la plus forte densité.
  4. *Demi-Espace Droit (Right Half-Space / Halbraum)* : Miroir du demi-espace gauche, zone de créativité et de passes cassant les lignes.
  5. *Flanc Droit (Wide Right)* : Zone de fixation et d'étirement horizontal.

- **La Zone 14 (L'espace entre les lignes)** :
  Située juste devant la surface de réparation adverse (entre 18m et 30m du but adverse), la Zone 14 est statistiquement la zone générant la plus forte conversion d'occasions et de passes décisives (*xG generation*).

---

## 3. Principes Opérationnels et Supériorités Tactiques

Dans le modèle de jeu contemporain, la supériorité ne se réduit pas au nombre :

- **Supériorité Numérique** : Avoir plus de joueurs dans une zone donnée (ex: 3 contre 2 au milieu).
- **Supériorité Positionnelle** : Placement d'un joueur dans le dos ou entre les lignes défensives adverses, rendant son intervention impossible sans rupture de structure.
- **Supériorité Qualitative** : Création intentionnelle d'un duel 1 contre 1 favorable (ex: ailier dribbleur rapide contre un défenseur latéral lent).
- **Supériorité Socio-Affective** : Synergies relationnelles et automatismes entre certains profils de joueurs (double pivot, paires d'ailiers/latéraux).

---

## 4. Guide de Cadrage pour l'Agent IA (High-Level Mapping)

Quand le coach formule une question, l'agent utilise ce guide pour déduire :
1. **La Phase de Jeu ciblée** (ex: Perte de maîtrise = Rupture en Transition Défensive ou défaillance du Contre-pressing).
2. **La Zone Spatiale clé** (ex: Si pertes de balle = vérifier la Zone 14 ou le Demi-espace).
3. **Les Métriques SQL à solliciter** : Volume de passes réussies/échouées, passes sous pression (`under_pressure=1`), localisation moyenne des pertes, taux de duels défensifs gagnés.
"""

GUIDE_2_MD = """---
title: "Guide High-Level 2 : Structures Tactiques, Blocs & Dynamique Spatiale"
category: "High-Level Tactical Theory"
level: "Framework / Routing"
---

# Guide High-Level 2 : Structures Tactiques, Blocs & Dynamique Spatiale

## 1. Hauteurs de Bloc & Compacité Défensive

La gestion de la hauteur du bloc conditionne les espaces accordés à l'adversaire et les exigences physiques de l'équipe :

- **Bloc Haut (High Pressing / Pressing Tout-Terrain)** :
  - Ligne défensive au niveau de la ligne médiane (x > 50-60m).
  - Objectif : Forcer des relances imprécises du gardien et des défenseurs centraux pour récupérer le ballon dans les 40 mètres adverses.
  - Risque majeur : Espace béant dans le dos de la défense; exige un gardien libéro (Sweeper-Keeper) et des défenseurs très rapides.
- **Bloc Médian (Mid-Block)** :
  - Ligne défensive entre 25m et 40m de son propre but.
  - Objectif : Fermer l'accès aux demi-espaces centraux et piéger les passes intérieures. Meilleur compromis entre sécurité et menace de transition.
- **Bloc Bas (Low Block / Défense de Surface)** :
  - Ligne défensive devant la surface (< 20m de son but).
  - Objectif : Refuser toute profondeur, densifier l'axe et forcer l'adversaire à centrer ou tenter des tirs lointains à faible xG.

---

## 2. Maîtrise Spatiale, Ombres de Couverture & Lignes de Passes

- **Ombre de Couverture (Cover Shadow / Deckungsschatten)** :
  Technique fondamentale par laquelle un joueur presse le porteur du ballon tout en positionnant son propre corps dans la trajectoire de passe directe vers un joueur adverse placé derrière lui. Permet de contrôler 2 joueurs avec 1 seul défenseur.
- **Principe du Troisième Homme (Third-Man Run)** :
  Si le joueur A ne peut pas passer directement au joueur C (bloqué par l'ombre de couverture de B), A transmet au joueur B (appui) qui remet instantanément en une touche vers C lancé. Le joueur libre est rendu accessible par une déviation intermédiaire.
- **Surcharges & Isolations (Overload to Isolate)** :
  Accumulation délibérée de 4 à 5 joueurs dans le demi-espace gauche pour aspirer le bloc défensif adverse, suivie d'un changement d'aile rapide vers l'ailier droit isolé en situation de 1 contre 1 sur grand espace.

---

## 3. Architecture de Rest-Defense (Sécurité Préventive)

La **Rest-Defense** (*Restverteidigung*) désigne la disposition structurelle des joueurs situés derrière la ligne du ballon pendant que l'équipe est en phase de possession :

- **Structure 3-2** (3 défenseurs centraux/latéraux bas + 2 milieux axiaux) : Assure une couverture complète des 3 couloirs intérieurs contre les contre-attaques rapides.
- **Structure 2-3** (2 centraux + 2 latéraux inversés montant au milieu avec la sentinelle) : Maximise la présence au cœur du jeu et permet un contre-pressing immédiat à la perte.
- **Conséquence d'une Rest-Defense défaillante** : Si les milieux s'engagent trop haut sans compensation, la moindre perte de balle expose les défenseurs centraux à des 2 contre 2 ou 3 contre 2 en infériorité numérique sur transition rapide.

---

## 4. Pièges au Pressing (Pressing Traps)

Un pressing efficace ne consiste pas à courir vers le ballon, mais à guider délibérément l'adversaire vers une zone piège :
- **Déclencheurs (Triggers)** : Passe latérale flottante, contrôle dos au jeu, passe vers un joueur isolé le long de la ligne de touche.
- **Exécution** : Dès le déclencheur activé, fermeture coordonnée de toutes les lignes de passes axiales par les ombres de couverture, forçant l'adversaire à dégager ou concéder la perte.
"""

GUIDE_3_MD = """---
title: "Guide High-Level 3 : Périodisation Tactique & Systèmes Complexes"
category: "High-Level Tactical Theory"
level: "Framework / Routing"
---

# Guide High-Level 3 : Périodisation Tactique & Systèmes Complexes

## 1. Le Football comme Système Complexe Adaptatif

Une équipe de football n'est pas une simple somme d'individualités, mais un **système complexe adaptatif** régi par des interactions non-linéaires :

- **Émergence & Synergies** : L'efficacité collective découle de la synchronisation locale entre paires et triplets de joueurs (sous-structures relationnelles), créant des propriétés globales qu'aucun joueur seul ne possède.
- **Auto-Organisation sous Contraintes** : Les joueurs adaptent continuellement leur positionnement en fonction des contraintes de l'environnement (ballon, partenaires, adversaires, score, temps).
- **Ruptures de Phase & Temps Faibles** : Une désynchronisation mineure (ex: un milieu qui tarde de 2 secondes à compenser la montée d'un latéral) peut provoquer l'effondrement systémique de tout le bloc défensif.

---

## 2. Fondements de la Périodisation Tactique (Méthodologie Vítor Frade)

Créée par le professeur Vítor Frade à l'Université de Porto, la Périodisation Tactique unifie la préparation physique, technique, psychologique et tactique au sein du **Modèle de Jeu** :

- **Le Modèle de Jeu** : La matrice comportementale et culturelle définissant comment l'équipe entend répondre aux situations des 4 phases de jeu.
- **Hiérarchie des Principes** :
  1. *Macro-Principes* : Intentions fondamentales (ex: circulation rapide par les demi-espaces, pressing immédiat à la perte).
  2. *Sous-Principes* : Comportements inter-secteurs (ex: coulissement du double pivot pour fermer l'interligne).
  3. *Sous-Sous-Principes* : Directives micro-individuelles (ex: orientation des appuis du défenseur central lors du recul-frein).
- **Principe de Spécificité** : Tout exercice d'entraînement doit être une situation de jeu réelle reflétant le modèle de jeu, excluant le travail physique décontextualisé.

---

## 3. Dynamique Écologique & Coordination Inter-Individuelle

- **Théorie des Affordances** : Les opportunités d'action perçues par le joueur sur le terrain (ex: une ligne de passe ouverte est une *affordance* qui n'apparaît que si le partenaire se déplace avec le bon tempo).
- **Dynamique des Centroïdes d'Équipe** :
  - Le *centroïde* est le centre de gravité géométrique (barycentre x, y) de l'ensemble des 10 joueurs de champ.
  - La distance relative entre le centroïde de l'équipe attaquante et celui de l'équipe défendante est un indicateur mathématique de la maîtrise spatiale.
- **Synchronisation & Phase Relative** : Lorsque deux lignes (milieu et défense) perdent leur synchronisation temporelle, la distance inter-lignes s'élargit, créant des poches de vulnérabilité exploitables.

---

## 4. Métriques Modernes de Santé Systémique d'une Équipe

- **Centralité de Réseau (Network Centrality)** : Mesure si le jeu dépend exagérément d'un seul distributeur (vulnérabilité au marquage individuel) ou s'il est résilient et polycentrique.
- **Coefficient de Clustering & Triangulation** : Mesure la densité des triangles de passes créés autour du porteur.
- **VAEP (Valuing Actions by Estimating Probabilities)** : Évaluation probabiliste de chaque geste technique par rapport à l'augmentation de la chance de but ou la réduction du risque d'encaisser.
"""


def create_styled_pdf(filename: str, title: str, subtitle: str, content_blocks: List[Tuple[str, List[str]]]) -> None:
    """Génère un PDF professionnel et élégant via ReportLab."""
    pdf_path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#1A365D")   # Deep navy
    secondary_color = colors.HexColor("#2B6CB0") # Cobalt blue
    accent_color = colors.HexColor("#2C7A7B")    # Teal
    dark_neutral = colors.HexColor("#2D3748")    # Charcoal body text
    bg_box = colors.HexColor("#EDF2F7")          # Light grey

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=14,
        textColor=accent_color,
        spaceAfter=15,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=secondary_color,
        spaceBefore=14,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=dark_neutral,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletItem",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
        leftIndent=12,
        spaceAfter=4,
    )

    story = []

    # En-tête
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(subtitle, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=secondary_color, spaceBefore=2, spaceAfter=14))

    # Corps du document
    for section_title, paragraphs in content_blocks:
        story.append(Paragraph(section_title, h1_style))
        for p_text in paragraphs:
            if p_text.startswith("•") or p_text.startswith("-"):
                story.append(Paragraph(f"• {p_text.lstrip('•- ')}", bullet_style))
            else:
                story.append(Paragraph(p_text, body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    print(f"[SUCCESS] PDF généré -> {pdf_path.name}")


def main() -> None:
    """Génère les fichiers Markdown et PDF des 3 guides."""
    print("=== Génération des 3 Guides Tactiques High-Level ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Écriture des versions Markdown
    (OUTPUT_DIR / "01_football_game_phases_and_core_principles.md").write_text(GUIDE_1_MD, encoding="utf-8")
    (OUTPUT_DIR / "02_tactical_structures_and_spatial_dynamics.md").write_text(GUIDE_2_MD, encoding="utf-8")
    (OUTPUT_DIR / "03_tactical_periodization_and_complex_systems.md").write_text(GUIDE_3_MD, encoding="utf-8")
    print("[SUCCESS] 3 fichiers Markdown enregistrés.")

    # 2. Génération PDF 1
    create_styled_pdf(
        filename="01_football_game_phases_and_core_principles.pdf",
        title="Guide High-Level 1 : Les 4 Phases du Jeu & Principes Fondamentaux",
        subtitle="Assistant Tactique Football AI — Cadre de Routage & Taxonomie (Phase 1)",
        content_blocks=[
            (
                "1. La Structure Universelle du Match : Le Cycle des 4 Phases",
                [
                    "Le football moderne est un continuum dynamique articulé autour de 4 moments interdépendants. Chaque phase conditionne immédiatement la structure de la phase suivante.",
                    "• <b>Organisation Offensive (Attaque Placée)</b> : Déséquilibrer le bloc adverse en occupant la largeur et les interlignes.",
                    "• <b>Transition Défensive (Perte du Ballon)</b> : Moment critique nécessitant soit un contre-pressing immédiat (5s), soit un repli axial structuré.",
                    "• <b>Organisation Défensive (Bloc Équipe)</b> : Protection de l'axe central du but, réduction de la distance inter-lignes (<15m) et coulissement coordonné.",
                    "• <b>Transition Offensive (Récupération du Ballon)</b> : Exploitation de la désorganisation adverse par une passe verticale rapide en rupture.",
                ],
            ),
            (
                "2. Géométrie du Terrain & Zonage Stratégique",
                [
                    "L'analyse événementielle (x, y) s'appuie sur une grille en 5 couloirs verticaux et 3 tiers horizontaux :",
                    "• <b>Demi-Espaces (Half-Spaces / Halbraum)</b> : Couloirs intérieurs situés entre l'axe et la ligne de touche. Zones idéales de passes diagonales décisives et de fixation.",
                    "• <b>Couloir Central & Zone 14</b> : Zone située juste devant la surface de réparation (18-30m), hautement déterminante dans la création de xG.",
                    "• <b>Flancs Extérieurs</b> : Zones d'étirement horizontal et de centres.",
                ],
            ),
            (
                "3. Typologie des Supériorités Tactiques",
                [
                    "• <b>Supériorité Numérique</b> : Avoir plus de joueurs dans une zone donnée (ex: 3v2 au milieu).",
                    "• <b>Supériorité Positionnelle</b> : Placement optimal dans le dos ou entre les lignes rendant le marquage impossible sans désorganisation.",
                    "• <b>Supériorité Qualitative</b> : Création délibérée d'un duel 1v1 avantageux pour un joueur clé.",
                    "• <b>Supériorité Socio-Affective</b> : Synergies relationnelles et complicité technique entre binômes de joueurs.",
                ],
            ),
        ],
    )

    # 3. Génération PDF 2
    create_styled_pdf(
        filename="02_tactical_structures_and_spatial_dynamics.pdf",
        title="Guide High-Level 2 : Structures Tactiques, Blocs & Dynamique Spatiale",
        subtitle="Assistant Tactique Football AI — Cadre de Détection Spatiale & Pressing (Phase 2)",
        content_blocks=[
            (
                "1. Hauteurs de Blocs & Compacité Défensive",
                [
                    "• <b>Bloc Haut (High Pressing)</b> : Ligne défensive sur la ligne médiane (x > 50-60m). Récupération haute mais risque dans le dos nécessitant un gardien libéro actif.",
                    "• <b>Bloc Médian (Mid-Block)</b> : Ligne défensive entre 25m et 40m. Contrôle des demi-espaces et pièges axiaux.",
                    "• <b>Bloc Bas (Low Block)</b> : Protection de la surface (<20m), densité axiale maximale et gestion des centres.",
                    "• <b>Compacité d'Équipe</b> : Distance inter-lignes resserrée (<15-20m) et largeur d'équipe contenue (<35-40m).",
                ],
            ),
            (
                "2. Contrôle de l'Espace, Ombres de Couverture & Lignes de Passes",
                [
                    "• <b>Ombre de Couverture (Cover Shadow)</b> : Bloquer la ligne de passe vers un joueur placé derrière soi tout en cadrant le porteur.",
                    "• <b>Principe du Troisième Homme (Third-Man Run)</b> : Utiliser un appui intermédiaire pour atteindre un partenaire lancé rendu inaccessible par l'adversaire.",
                    "• <b>Surcharge & Isolation (Overload to Isolate)</b> : Densifier une zone pour aspirer la défense et libérer un 1v1 à l'opposé.",
                ],
            ),
            (
                "3. Organisation de la Rest-Defense (Sécurité Préventive)",
                [
                    "• <b>Structures 3-2 ou 2-3</b> : Positionnement permanent de 5 joueurs derrière la ligne du ballon pour prévenir les transitions rapides.",
                    "• <b>Règle de compensation</b> : Toute montée d'un latéral ou d'un milieu doit être compensée par le coulissement du double pivot.",
                ],
            ),
        ],
    )

    # 4. Génération PDF 3
    create_styled_pdf(
        filename="03_tactical_periodization_and_complex_systems.pdf",
        title="Guide High-Level 3 : Périodisation Tactique & Systèmes Complexes",
        subtitle="Assistant Tactique Football AI — Cadre Systémique & Dynamique Collective (Phase 3)",
        content_blocks=[
            (
                "1. L'Équipe comme Système Complexe Adaptatif",
                [
                    "• <b>Non-Linéarité & Émergence</b> : Une équipe n'est pas une addition de joueurs mais un ensemble d'interactions dynamiques créant une synchronisation collective.",
                    "• <b>Auto-Organisation</b> : Adaptation collective permanente aux contraintes spatio-temporelles du match.",
                    "• <b>Ruptures de Phase</b> : Une baisse d'intensité ou un retard de compensation de 2 secondes peut rompre l'équilibre de tout le bloc.",
                ],
            ),
            (
                "2. Fondements de la Périodisation Tactique (Vítor Frade)",
                [
                    "• <b>Le Modèle de Jeu</b> : Référentiel unifié guidant les comportements collectifs dans les 4 phases de jeu.",
                    "• <b>Hiérarchie des Principes</b> : Macro-principes généraux, sous-principes d'inter-secteurs, et sous-sous-principes individuels.",
                    "• <b>Principe de Spécificité</b> : Tout apprentissage tactique doit être contextualisé avec la présence de partenaires, d'adversaires et d'un but.",
                ],
            ),
            (
                "3. Indicateurs Quantitatifs de Santé Systémique",
                [
                    "• <b>Réseaux de Passes (Passing Networks)</b> : Centralité, densité des connexions et détection des surcharges locales.",
                    "• <b>Dynamique des Centroïdes</b> : Suivi de l'évolution du centre de gravité de l'équipe et de la distance inter-lignes.",
                    "• <b>VAEP & Menace Attendue (xT)</b> : Quantification de la valeur tactique de chaque geste dans la progression vers le but adverse.",
                ],
            ),
        ],
    )

    print("\n" + "=" * 50)
    print("[RÉSUMÉ DE LA GÉNÉRATION HIGH-LEVEL]")
    print(f"  * 3 PDF générés dans : {OUTPUT_DIR.resolve()}")
    print(f"  * 3 Markdown sources créés dans : {OUTPUT_DIR.resolve()}")
    print("=" * 50)


if __name__ == "__main__":
    main()

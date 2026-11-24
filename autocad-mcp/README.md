# Agent DCE BAAK

Outils qui vérifient et corrigent les plans DCE (PROJECT Site) directement dans AutoCAD.

## Utilisation dans Claude Code (abonnement actuel, sans clé API)

Les outils sont déjà enregistrés dans Claude Code sous le nom `dce-autocad` (fichier `C:\Users\sbs\.claude.json`).

1. Ouvrez AutoCAD.
2. Ouvrez une **nouvelle** session Claude Code (les outils n'apparaissent pas dans une session déjà ouverte).
3. Demandez simplement, par exemple :
   - « Ouvre le plan mezzanine du DCE et liste les calques »
   - « Quels murs Revit manquent à la mezzanine ? Propose les corrections »
   - « Redessine la cloison du local SPA en polyligne sur le calque des cloisons »
   - « Enregistre une copie indicée sous D:\DCE SITE\ARCHITECTURE\DWG »

Claude Code vous demande l'autorisation avant chaque outil qui modifie le plan (dessin, déplacement, suppression,
enregistrement). Les outils de lecture (documents, calques, entités, fichiers, différences Revit) ne modifient rien.

## Règles intégrées (appliquées par les outils eux-mêmes)

- Rien n'est jamais écrit sur G: ; les plans sur G: s'ouvrent en lecture seule.
- Les enregistrements se font uniquement sous `D:\DCE SITE`, sous un nouveau nom (jamais d'écrasement).
- Dessin en LWPOLYLINE sur les calques existants de la charte BAAK (aucun calque inventé), blocs existants (LEGENDE, cartouche).
- Détails classés par code CAH-01 à CAH-09.
- Journal de toutes les actions : `C:\Users\sbs\.dce-agent\logs\journal_AAAA-MM-JJ.txt`.

## Désactiver ou retirer les outils

Dans un terminal : `claude mcp remove dce-autocad -s user`, ou supprimez l'entrée `dce-autocad` de `mcpServers` dans
`C:\Users\sbs\.claude.json`. Une copie du fichier avant l'ajout est gardée : `C:\Users\sbs\.claude.json.bak-before-dce-autocad`.

## Option : agent autonome (nécessite une clé API payante, séparée de l'abonnement)

`run_dce_agent.cmd` lance le même agent hors de Claude Code. Il faut une clé créée sur https://console.anthropic.com,
enregistrée par vous-même avec `setx ANTHROPIC_API_KEY "votre-clé"`. Chaque modification est demandée `[o/N]` ;
`run_dce_agent.cmd --auto` applique sans demander.

## Fichiers

- `dce_mcp_server.py` — serveur MCP utilisé par Claude Code.
- `acad_tools.py` — outils AutoCAD (COM) et fichiers DCE.
- `agent.py`, `run_dce_agent.cmd` — agent autonome (option clé API).
- `venv\` — environnement Python de l'agent (anthropic, pywin32).

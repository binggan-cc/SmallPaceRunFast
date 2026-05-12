---
name: image-prompt-architect
description: Use when creating, reverse engineering, improving, or templating image generation prompts for posters, infographics, product shots, portraits, typography, worldbuilding, miniatures, social media visuals, or visual style systems.
---

# Image Prompt Architect

Use this skill for still-image generation and image prompt reverse engineering.

## 1. Build The Image Prompt Pack

For non-trivial image work, output:

```markdown
## Image Prompt Pack

### Visual Goal

### Selected Template Family

### Core Prompt

### Style Shell
- Medium:
- Composition:
- Lighting:
- Camera / lens:
- Material:
- Palette:
- Detail density:

### Content Slots
- {SUBJECT}
- {SCENE}
- {OBJECT}
- {TEXT}
- {COLOR_ACCENT}

### Negative Constraints

### Variants

### First Test Focus
```

## 2. Select The Template Family

Use `docs/visual-generation-prompt-extraction.md` when available.

| Goal | Template family |
| --- | --- |
| Knowledge, teaching, explanatory layout | Knowledge infographic |
| High-end science or tech poster | Apple-style science poster |
| Object, anatomy, specimen, structure | Specimen / anatomical plate |
| Wordmark, macro letterform, water text | Typography / macro typography |
| Product, fashion, commercial still | Fashion / product editorial |
| Character, avatar, portrait | Theme-driven editorial portrait |
| Game, film, fiction setting | Worldbuilding visual system |
| Miniature, paper world, diorama | Paper diorama / miniature world |
| Lifestyle grid or social cover | Xiaohongshu / social visual grid |

## 3. Reverse Images Before Rewriting Them

When given a reference image or existing prompt, first produce:

- core visual identity
- non-negotiable keywords
- implicit visual features
- magic ingredient
- weaknesses to improve
- strict version vs elevated version

Then write the reconstructed prompt.

## 4. Keep Prompts Modular

Separate:

- stable Style Shell
- replaceable Content Slots
- optional enhancements
- negative constraints
- platform parameters

Do not bury subject, style, lighting, camera, and composition in one unstructured paragraph when the prompt is intended for reuse.

## 5. Tune By Visible Deviation

| Problem | Adjust |
| --- | --- |
| Too generic | Add medium, lens, composition, material, and detail hierarchy |
| Too cluttered | Reduce elements, simplify background, add negative constraints |
| Style drift | Strengthen Style Shell and remove conflicting style words |
| Subject wrong | Rewrite Content Slot with identity, proportions, and key attributes |
| Looks cheap | Add editorial composition, restrained palette, refined materials |
| Text fails | Reduce generated text or move text to post-production |

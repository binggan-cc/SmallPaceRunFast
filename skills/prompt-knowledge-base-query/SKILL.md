---
name: prompt-knowledge-base-query
description: Use when the user wants to query, mine, summarize, or reuse the local prompt knowledge base for visual prompt references, including camera angle, shot type, lens, lighting, style, subject, product, portrait, and similar prompt pattern lookup. Applies when using prompt-knowledge-base data to support image prompts, video prompts, reverse prompts, or template recommendations.
---

# Prompt Knowledge Base Query

Use this skill to turn the local prompt knowledge base into actionable visual prompt references.

Primary local sources, when available:

- `prompt-knowledge-base/README.md`
- `prompt-knowledge-base/QUICK-REFERENCE.md`
- `prompt-knowledge-base/05-analysis/FINAL-COMPREHENSIVE-REPORT.md`
- `prompt-knowledge-base/02-parsed-data/`
- `prompt-knowledge-base/exports/`
- `docs/prompt-knowledge-base-analysis.md`

## 1. Classify The Query

| User asks for | Action |
| --- | --- |
| Examples like "85mm portrait" | Search by lens, subject, style, and lighting |
| Camera angle usage | Use angle taxonomy and statistics |
| Prompt pattern or formula | Extract reusable blocks, not just examples |
| Similar references for a new prompt | Match by schema dimensions |
| Dataset statistics | Report counts and practical implications |
| Template recommendations | Pass useful blocks to a template composer |

## 2. Use The Visual Prompt Schema

Map the request to these dimensions:

- subject
- action / pose
- shot type
- camera angle
- lens
- composition
- lighting
- mood
- era / style
- color / tone
- background
- technical tags
- material
- additional elements

Only use dimensions that help the current task. Do not over-parse simple requests.

## 3. Output References As Patterns

Prefer this format:

```markdown
## Query Intent

## Matching Dimensions

## Reference Patterns
- Pattern:
- Why it works:
- Useful prompt blocks:

## Reusable Prompt Blocks

## Suggested Template
```

When giving examples, summarize or extract short reusable blocks. Avoid dumping long raw prompt lists unless the user explicitly requests raw data.

## 4. Coordinate With Other Visual Skills

If the user is building a final image prompt, hand off the useful blocks to `image-prompt-architect`.

If the user is building a video prompt, hand off camera, motion, shot, and continuity patterns to `video-prompt-architect`.

If the user wants a reusable prompt, hand off the patterns to `visual-prompt-template-composer`.

## 5. Practical Heuristics

- Treat statistics as guidance, not rules.
- Common tags can improve stability but can also make prompts generic.
- Prefer combinations that match the user goal over high-frequency combinations.
- For image generation, camera angle, shot type, lens, lighting, and composition usually matter more than generic quality tags.
- For video generation, timeline, camera movement, subject lock, and continuity matter more than still-image quality tags.

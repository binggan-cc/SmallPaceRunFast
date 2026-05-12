---
name: visual-prompt-architect
description: Use when the user asks for visual prompt work across image generation, image reverse engineering, video prompts, image-to-video, storyboards, visual style systems, prompt tuning, or reusable visual prompt templates. Routes the task to the right workflow and keeps iteration small, testable, and documented.
---

# Visual Prompt Architect

Use this skill as the entry router for visual creation prompts.

Core rule:

```text
先判入口，再选模板；
先建结构，再写 Prompt；
小步验证，偏差回流；
最终沉淀为可复用模板。
```

## 1. Classify The Request

| User request | Route | First action |
| --- | --- | --- |
| Reference image, good image, existing prompt | Reverse engineering | Decode Style DNA before writing a prompt |
| Generate an image | Image prompt | Select an image template family |
| Animate an image | Image-to-video | Lock identity, motion, camera, duration |
| Generate a video | Video prompt | Build timeline, shots, motion, camera |
| Create storyboard, movement sheet, character sheet | Storyboard / sheet | Define panels, poses, continuity |
| Improve a failed output | Tuning loop | Diagnose the deviation first |
| Build a reusable look | Style system | Separate Style Shell from Content Slots |

If the repo contains `docs/visual-generation-prompt-extraction.md`, use it as the template library. Use `docs/visual-prompt-system.md` as the method reference.

## 2. Choose The Output Contract

Use one of these deliverable shapes:

- `Image Prompt Pack`
- `Video Prompt Pack`
- `I2V Prompt Pack`
- `Storyboard Prompt Pack`
- `Reverse Prompt Pack`
- `Tuning Notes`
- `Golden Template`

Do not return only a raw prompt for medium or complex visual work. Include the structure that makes the prompt adjustable.

## 3. Ask Only For Missing Inputs That Block Quality

Proceed with assumptions when the goal is clear. Ask a concise question only when a necessary input is missing:

- target model or platform
- image or video format
- target audience or channel
- strict replication vs upgraded interpretation
- subject, product, or character identity
- duration and aspect ratio for video

## 4. Apply Small Pace Tuning

When the user provides output feedback:

1. Identify the visible problem.
2. Classify the likely cause.
3. Change only the most important 1-3 prompt variables.
4. Explain the expected effect.
5. Preserve working parts of the previous prompt.

Use this format:

```markdown
## Architect's Analysis
- Problem:
- Cause:
- Adjustment:
- Expected effect:

## Updated Prompt
...

## What Changed
- ...
```

## 5. Preserve Reusable Assets

When a prompt becomes stable, extract:

- Style Shell
- Content Slots
- negative constraints
- model parameters
- reference image instructions
- variants
- test focus

End with a reusable template when the task is no longer a one-off generation.

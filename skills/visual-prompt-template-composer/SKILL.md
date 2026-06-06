---
name: visual-prompt-template-composer
description: Use when the user wants to convert visual prompts into reusable templates, build PromptFill-style {{variable}} prompt templates, separate Style Shell from Content Slots, create variable banks, compose image or video prompt variants, or turn a successful prompt into a Golden Template.
---

# Visual Prompt Template Composer

Use this skill to convert visual prompts into reusable, variable-based templates.

Core rule:

```text
锁定风格壳，拆出内容槽；
变量可替换，结构可复用；
示例可生成，模板可沉淀。
```

## 1. Use `{{variable}}` Syntax

Use double braces for replaceable variables:

```text
{{subject}}, {{shot_type}}, {{camera_angle}}, {{lens}},
{{lighting}}, {{style_shell}}, {{background}},
{{quality_tags}}, {{negative_constraints}}
```

Rules:

- Same variable name must mean the same thing everywhere in the template.
- Variables inside Style Shell are locked by default unless marked replaceable.
- Variables inside Content Slots are replaceable by default.
- Keep generation-facing terms in English when the target model benefits from English.
- Add Chinese explanations when the user needs to understand or edit the template.

## 2. Split Prompt Into Layers

For each prompt, identify:

| Layer | Meaning |
| --- | --- |
| Style Shell | Stable visual identity, medium, lighting, camera, material, composition |
| Content Slots | Subject, object, scene, text, brand, color accent |
| Control Tags | Aspect ratio, lens, resolution, model parameters |
| Negative Constraints | Things to avoid |
| Test Focus | What the first generation should verify |

## 3. Output Contract

Use this format:

```markdown
## Template

## Variables
| Variable | Role | Default | Replaceable? |
| --- | --- | --- | --- |

## Variable Bank

## Locked Style Shell

## Replaceable Slots

## Example Instantiations

## First Test Focus
```

## 4. Template Families

Choose variables based on the use case:

| Use case | Must-have variables |
| --- | --- |
| Portrait | `{{subject}}`, `{{expression}}`, `{{shot_type}}`, `{{lens}}`, `{{lighting}}` |
| Product | `{{product}}`, `{{material}}`, `{{background}}`, `{{lighting}}`, `{{composition}}` |
| Infographic | `{{topic}}`, `{{layout}}`, `{{visual_metaphor}}`, `{{text_density}}`, `{{palette}}` |
| Worldbuilding | `{{world}}`, `{{environment}}`, `{{era_style}}`, `{{key_objects}}`, `{{mood}}` |
| Image-to-video | `{{reference_image}}`, `{{locked_identity}}`, `{{motion}}`, `{{camera_move}}`, `{{duration}}` |
| Storyboard | `{{shot_count}}`, `{{shot_duration}}`, `{{framing}}`, `{{action}}`, `{{transition}}` |

## 5. Quality Check

Before finalizing:

- Is the Style Shell reusable with a different subject?
- Are Content Slots clearly replaceable?
- Are camera, lighting, and composition explicit enough?
- Are negative constraints specific rather than generic?
- Does each example instantiation preserve the same visual identity?

If the template is too broad, split it into smaller templates.

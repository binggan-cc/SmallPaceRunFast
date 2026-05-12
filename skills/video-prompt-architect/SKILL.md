---
name: video-prompt-architect
description: Use when creating, improving, or reverse engineering video prompts, image-to-video prompts, shot lists, storyboards, movement sheets, VFX prompts, short-form ads, or cinematic camera instructions for video generation models.
---

# Video Prompt Architect

Use this skill for video generation, image-to-video, storyboards, motion sheets, and cinematic prompt design.

## 1. Route The Video Task

| Request | Route | Key control |
| --- | --- | --- |
| Text creates video | Text-to-video | Timeline, subject, scene, camera, motion |
| Image becomes video | Image-to-video | Identity lock, motion strength, camera path |
| Multi-shot short | Shot list | Shot order, duration, transition, continuity |
| Storyboard | Storyboard prompt | Panels, framing, action, dialogue, SFX |
| Movement sheet | Action sheet | Pose sequence, motion arc, readability |
| VFX clip | VFX prompt | effect origin, physics, timing, integration |

## 2. Build The Video Prompt Pack

```markdown
## Video Prompt Pack

### Format
- Text-to-video / Image-to-video / storyboard
- Duration:
- Aspect ratio:
- Platform:

### Subject Lock
- Identity:
- Clothing / object consistency:
- Scene consistency:

### Timeline
- 0-3s:
- 3-6s:
- 6-10s:
- 10-15s:

### Motion
- Subject motion:
- Environmental motion:
- Transition:

### Camera
- Framing:
- Movement:
- Lens behavior:

### Visual Style

### Negative Constraints

### Verification Focus
```

## 3. Write Image-to-Video Prompts Differently

For I2V, do not redescribe the whole image as if it were a new scene. Anchor the reference and specify only what should move.

Include:

- reference image role
- immutable identity and objects
- allowed motion
- camera movement
- duration
- negative constraints against warping, flicker, identity drift, and scene jumps

## 4. Use Shot-Level Structure

For videos longer than a single moment, break the prompt into time blocks or shots. Each shot should include:

- duration
- framing
- subject action
- camera action
- transition
- continuity constraint

## 5. Tune By Motion Failure

| Problem | Adjust |
| --- | --- |
| Identity drift | Strengthen subject lock and reduce scene changes |
| Flicker | Simplify lighting and reduce fast motion |
| Warped anatomy | Reduce motion amplitude and specify natural movement |
| Scene jumps | Use one continuous shot or explicit transition |
| Camera chaos | Use one camera move and remove competing directions |
| Weak cinematic effect | Add framing, lens behavior, foreground/background motion |

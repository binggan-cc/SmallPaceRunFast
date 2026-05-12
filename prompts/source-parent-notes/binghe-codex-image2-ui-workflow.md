# Binghe Codex Image2 UI Workflow

Source post:
- Account: `冰河 @binghe`
- Post URL: `https://x.com/binghe/status/2046964997272871411`

## Summary

This post describes a compact UI generation workflow that loops between `Codex` and `image-2`:

1. let `Codex` generate a simple product web page
2. use `image-2` on the page screenshot to generate a better-looking UI
3. generate a full UI spec from the generated image
4. send the screenshot and UI spec back to `Codex` to reconstruct the design

The quoted earlier post extends the same idea with:

- product discussion with `Opus 4.7`
- `Codex` for implementation
- `GPT-image-2` for UI mockups and functional-detail prompts
- `Claude design` for UI design
- then back to `Codex`

## Why It Matters

- This is a practical AI-native design-to-code loop
- It treats screenshots as an intermediate representation between code and visual polish
- It is especially relevant for fast solo prototyping where exact design ownership is secondary to speed

## Classification

- Category: `AI technique / workflow`
- Secondary category: `frontend prototyping`
- Contains reusable prompt: `no`

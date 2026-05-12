# Codex Built-In GPT-Image-2 Resolution Limit

Source post:
- Account: `Tz @Tz_2022`
- Post URL: `https://x.com/Tz_2022/status/2047022797289881881`

## Summary

The post reports that Codex can generate images directly without a separate API key and claims the built-in model is `gpt-image-2`.

The key observation is that different aspect ratios all land around the same total pixel budget, roughly `1.57M` pixels.

## Reported Output Sizes

- `1:1` -> about `1254 x 1254` = `1,572,516` pixels
- `16:9` -> about `1672 x 941` = `1,573,352` pixels
- `3:1` -> about `2172 x 724` = `1,572,528` pixels
- `1:3` -> about `724 x 2172` = `1,572,528` pixels

## Claimed Conclusions

1. Codex built-in image generation uses `gpt-image-2`
2. It can handle complex images and non-Latin text
3. Resolution appears capped at roughly `1.57M` total pixels
4. It does not reach `2K`, let alone `4K`

## Why It Matters

- Useful for estimating the upper bound of built-in image output quality
- Important when planning infographic, poster, or UI mockup generation inside Codex
- Suggests aspect ratio can change, but the total pixel budget stays nearly fixed

## Notes

- This is a user-side measurement from X, not an official spec
- Treat the resolution limit as an observed behavior, not a confirmed platform guarantee

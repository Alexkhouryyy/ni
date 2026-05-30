# Apex portrait avatar

Drop your Apex face render here to make it the **living avatar** shown in the
dashboard's **Vision** tab.

## How

Save your file as one of the following (checked in this order — video wins):

| Priority | File | Notes |
|----------|------|-------|
| 1 | `apex.mp4` | Looping video — most alive |
| 2 | `apex.webm` | Looping video (smaller file) |
| 3 | `apex.png` | Still image — preferred format |
| 4 | `apex.jpg` | Still image |
| 5 | `apex.webp` | Still image |

Place the file in this folder: `dashboard/static/apex/`

Then open the dashboard → **Vision** tab. The face appears automatically.

## Video (recommended)

Generate a short looping video of Apex with Sora, Runway, Kling, or Pika.
Even a 2–4 second loop works great — the browser plays it seamlessly.
Export as MP4 (H.264) or WebM (VP9) and drop it here.

The video plays muted and looped. The aura and brightness effects still
animate on top of it in sync with Apex's real voice.

## Still image

If no video is present, the dashboard falls back to the still image.

- **Portrait orientation** with a dark/transparent background looks best.
- PNG with transparency is ideal. Roughly 800×1000 px or larger keeps it crisp.

## What the animations do

Regardless of video or image mode:

- **Idle** — gentle breathing + a soft cyan aura that slowly pulses
- **Thinking** — steady glow
- **Speaking** — the aura swells and brightens **in sync with Apex's real
  voice** (turn on "Speak replies" in the Chat tab), and the face breathes faster

## Fallback chain

If nothing is placed here, the dashboard falls back in order to:
1. 3D Ready Player Me human head (requires internet)
2. Built-in 2D canvas face (always works, fully offline)

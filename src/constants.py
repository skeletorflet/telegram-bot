PRE_MODIFIERS = [
    "masterpiece, best quality", "ultra-detailed, intricate details", "4k, 8k, uhd",
    "photorealistic, realistic", "cinematic, movie still", "anime style, vibrant colors",
    "concept art, digital painting", "illustration, sharp focus", "low poly, isometric",
    "minimalist, simple background", "epic composition, dramatic", "golden hour, soft light",
    "vivid, saturated colors", "monochrome, black and white", "surreal, dreamlike",
    "fantasy, magical", "sci-fi, futuristic", "steampunk, mechanical details",
    "cyberpunk, neon lights", "vintage, retro style", "watercolor painting",
    "oil painting, classic", "sketch, charcoal drawing", "cel-shaded, cartoonish",
    "flat design, vector art", "hdr, high dynamic range", "long exposure, motion blur",
    "macro photography, close-up", "double exposure", "glitch effect, distorted"
]

POST_MODIFIERS = [
    "cinematic lighting", "dramatic shadows", "volumetric lighting, god rays",
    "studio lighting, softbox", "rim lighting, backlight", "neon glow, vibrant",
    "underwater lighting, caustic effects", "fire and embers", "lens flare, anamorphic",
    "bokeh, shallow depth of field", "highly detailed background", "simple background, clean",
    "fog, mist, atmospheric", "rain, wet surface", "snow, winter scene",
    "starry night sky", "aurora borealis", "reflections, reflective surface",
    "dynamic angle, action shot", "fisheye lens", "vignette, dark corners",
    "color grading, cinematic tones", "film grain, noisy", "light leaks, vintage effect",
    "chromatic aberration", "bloom, soft glow", "particle effects, dust motes",
    "sun rays, crepuscular rays", "glowing eyes", "smoke, atmospheric"
]

ASPECT_CHOICES = ["1:1", "4:3", "3:4", "9:16", "16:9"]
BASE_CHOICES = [512, 640, 768, 896, 1024]
STEPS_CHOICES = list(range(4, 51))
CFG_CHOICES = [i * 0.5 for i in range(2, 25)]

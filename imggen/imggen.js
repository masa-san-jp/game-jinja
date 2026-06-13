// Local image generation client for browser games (DGX Spark / Qwen).
// The service (server.py) wraps ComfyUI behind one endpoint with CORS open.
//
//   const url = await generateImage("a torii gate at dawn, anime game art");
//   document.querySelector("img").src = url;   // url is a data: URL
//
// NOTE on latency: one image is ~9s. Do NOT call this on the hot path of a
// running game. Pre-generate at load/standby (e.g. while the title screen is
// up) and cache the data URLs. See INTEGRATION.md.

const IMGGEN_ENDPOINT =
  (window.IMGGEN_ENDPOINT || "http://127.0.0.1:8771") + "/generate";

async function generateImage(prompt, opts = {}) {
  const { width = 720, height = 720, seed } = opts;
  const res = await fetch(IMGGEN_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      width,
      height,
      seed: seed ?? Math.floor(Math.random() * 1e9),
      format: "dataurl",
    }),
  });
  if (!res.ok) throw new Error(`imggen ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.image; // "data:image/png;base64,..."
}

// Pre-generate a batch concurrently (server runs them one at a time, ~9s each).
async function generateImages(prompts, opts = {}) {
  return Promise.all(prompts.map((p) => generateImage(p, opts)));
}

if (typeof module !== "undefined") module.exports = { generateImage, generateImages };

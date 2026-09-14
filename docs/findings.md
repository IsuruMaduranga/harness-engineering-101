# Findings

Facts about tools and libraries we do not control, confirmed by running them
in this repo. Global to both books.

- **mdBook copies every non-markdown file under `src/` into the build
  output.** A 548 MB weights directory under `llms-101/src/gpt/` produced a
  544 MB `book/gpt/`. Weights now live in `llms-101/models/` (gitignored,
  outside `src/`); checkpoints and logs are pruned by
  `llms-101/scripts/sync-to-blog.sh` before copying to the blog.
- **`urllib.request.urlretrieve` from Hugging Face resets mid-download on
  large files** (`ConnectionResetError: [Errno 54]` at ~436 of 548 MB).
  `curl -L -C - --retry 5` resumes cleanly. `download_gpt2.py` still uses
  urllib; rerun it or fall back to curl if it fails.
- **Hugging Face `openai-community/gpt2` `model.safetensors` contains twelve
  `h.N.attn.bias` tensors of shape (1,1,1024,1024).** They are stored causal
  masks, not weights; counting them gives 137,022,720 instead of the true
  124,439,808 parameters. `v3_forward.py` skips names ending in `.attn.bias`.
  Linear weights are stored `(in, out)` (HF Conv1D convention), so `x @ W`
  works without a transpose.
- **PyTorch default `nn.Embedding` init (std 1) with a tied unembedding gives a
  step-0 loss of ~84, not ln(vocab).** GPT-2's init (`normal_(std=0.02)`,
  zero biases) gives 6.255 against ln(512)=6.24. `v4_train.py` and `gpt.py`
  apply it.
- **The toy GPT (875k params, 83k training tokens) overfits after ~500
  steps**: validation loss bottoms at 3.49 and climbs past ln(512) by step
  2300 while training loss reaches 0.21. Same numbers on every run with
  `torch.manual_seed(0)` on CPU. Both trainers keep the best-validation
  checkpoint.
- **A NumPy KV cache barely helps on short prompts.** 12-token prompt, 40
  tokens: 1.3x. 509-token prompt: 5.3x (36.2 s vs 6.8 s). Per-step time with
  the cache (~0.17 s) is dominated by streaming the 500 MB of weights, which
  is the decode-is-bandwidth-bound point chapter 13 makes.
- **mdbook-mermaid 0.5.0 warns when called from mdbook 0.5.4** but renders
  fine. Harmless.

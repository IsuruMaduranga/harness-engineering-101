#!/usr/bin/env python3
"""The complete toy GPT, in one file. Every chapter of LLMs 101, runnable.

    python3 gpt.py train                 # ~3 min on a laptop CPU -> gpt.pt, gpt_loss.csv
    python3 gpt.py generate "The harness" --temperature 0.8 --top-p 0.9 -n 200

Numbers in the block comments are chapter references. The training data is
the text of Harness Engineering 101 (corpus.txt, built by make_corpus.py).
"""
import argparse, csv, math, re, sys, time
from collections import Counter
import torch, torch.nn as nn, torch.nn.functional as F

# ---- configuration --------------------------------------------------------
VOCAB, BLOCK = 512, 128                    # ch 2: tokens in the vocabulary; ch 4/14: the context window
N_LAYER, N_HEAD, N_EMBD = 4, 4, 128        # ch 6: blocks, heads per block, width of the residual stream
STEPS, BATCH, LR = 1500, 32, 1e-3          # ch 8: training budget (stops before memorising sets in)
N_KV_HEAD = 2                              # ch 13: grouped-query attention; 2 K/V heads shared by 4 query heads


# ============================================================================
# Chapter 2: the tokenizer. Bytes in, merge the most common pair, repeat.
# ============================================================================
CHUNK = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d| ?\w+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+")

def _merge(word, pair, new_id):
    out, i = [], 0
    while i < len(word):
        if i < len(word) - 1 and (word[i], word[i + 1]) == pair:
            out.append(new_id); i += 2
        else:
            out.append(word[i]); i += 1
    return tuple(out)

class Tokenizer:
    def __init__(self, merges=None):
        self.merges = merges or {}
        self._build_vocab()

    def _build_vocab(self):
        self.vocab = {i: bytes([i]) for i in range(256)}
        for (a, b), i in self.merges.items():
            self.vocab[i] = self.vocab[a] + self.vocab[b]

    def train(self, text, vocab_size):
        words = {tuple(c.encode()): n for c, n in Counter(CHUNK.findall(text)).items()}
        for new_id in range(256, vocab_size):
            pairs = Counter()
            for w, n in words.items():
                for p in zip(w, w[1:]):
                    pairs[p] += n
            if not pairs: break
            best = max(pairs, key=pairs.get)
            self.merges[best] = new_id
            words = {_merge(w, best, new_id): n for w, n in words.items()}
        self._build_vocab()
        return self

    def encode(self, text):
        ids = []
        for chunk in CHUNK.findall(text):
            w = tuple(chunk.encode())
            while len(w) > 1:
                rank, pair = min((self.merges.get(p, 1e9), p) for p in zip(w, w[1:]))
                if rank == 1e9: break
                w = _merge(w, pair, self.merges[pair])
            ids.extend(w)
        return ids

    def decode(self, ids):
        return b"".join(self.vocab[i] for i in ids).decode("utf-8", errors="replace")


# ============================================================================
# Chapters 5, 6, 13: the model. Attention with a KV cache, MLP, residuals.
# ============================================================================
class Attention(nn.Module):
    def __init__(self):
        super().__init__()
        hd = N_EMBD // N_HEAD
        self.q = nn.Linear(N_EMBD, N_EMBD)                       # ch 5: what am I looking for
        self.kv = nn.Linear(N_EMBD, 2 * N_KV_HEAD * hd)          # ch 13: fewer K/V heads = smaller cache
        self.proj = nn.Linear(N_EMBD, N_EMBD)                    # ch 6: let the heads mix

    def forward(self, x, cache=None):
        B, T, C = x.shape
        hd = C // N_HEAD
        q = self.q(x).view(B, T, N_HEAD, hd).transpose(1, 2)                    # (B, heads, T, hd)
        k, v = self.kv(x).split(N_KV_HEAD * hd, dim=-1)
        k = k.view(B, T, N_KV_HEAD, hd).transpose(1, 2)
        v = v.view(B, T, N_KV_HEAD, hd).transpose(1, 2)
        if cache is not None:                                                    # ch 13: reuse old K, V
            if "k" in cache:
                k = torch.cat([cache["k"], k], dim=2); v = torch.cat([cache["v"], v], dim=2)
            cache["k"], cache["v"] = k, v
        k = k.repeat_interleave(N_HEAD // N_KV_HEAD, dim=1)                       # each K/V head serves 2 query heads
        v = v.repeat_interleave(N_HEAD // N_KV_HEAD, dim=1)
        T_all = k.shape[2]
        scores = q @ k.transpose(-2, -1) / math.sqrt(hd)                          # ch 5: how well queries match keys
        mask = torch.ones(T, T_all, dtype=torch.bool, device=x.device).triu(T_all - T + 1)
        scores = scores.masked_fill(mask, float("-inf"))                          # ch 5: no looking at the future
        out = F.softmax(scores, dim=-1) @ v                                       # ch 5: weighted average of values
        return self.proj(out.transpose(1, 2).reshape(B, T, C))

class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln_1, self.attn = nn.LayerNorm(N_EMBD), Attention()
        self.ln_2 = nn.LayerNorm(N_EMBD)
        self.mlp = nn.Sequential(nn.Linear(N_EMBD, 4 * N_EMBD), nn.GELU(), nn.Linear(4 * N_EMBD, N_EMBD))

    def forward(self, x, cache=None):
        x = x + self.attn(self.ln_1(x), cache)      # ch 6: add, don't replace (residual stream)
        return x + self.mlp(self.ln_2(x))           # ch 6: the MLP, where the facts live

class GPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.wte = nn.Embedding(VOCAB, N_EMBD)      # ch 3: what
        self.wpe = nn.Embedding(BLOCK, N_EMBD)      # ch 6: where
        self.blocks = nn.ModuleList([Block() for _ in range(N_LAYER)])
        self.ln_f = nn.LayerNorm(N_EMBD)
        for m in self.modules():
            if isinstance(m, (nn.Linear, nn.Embedding)): nn.init.normal_(m.weight, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None: nn.init.zeros_(m.bias)

    def forward(self, ids, caches=None, pos=0):
        """ids: (B, T) new tokens starting at position `pos`. Returns logits (B, T, VOCAB)."""
        T = ids.shape[1]
        x = self.wte(ids) + self.wpe(torch.arange(pos, pos + T, device=ids.device))
        for i, block in enumerate(self.blocks):
            x = block(x, None if caches is None else caches[i])
        return self.ln_f(x) @ self.wte.weight.T     # ch 3: unembed with the same table


# ============================================================================
# Chapter 15: the serving layer picks a token. Temperature, top-k, top-p.
# ============================================================================
def pick(logits, temperature=1.0, top_k=0, top_p=1.0):
    if temperature == 0:
        return int(logits.argmax())
    probs = F.softmax(logits / temperature, dim=-1)
    probs, order = probs.sort(descending=True)
    if top_k: probs, order = probs[:top_k], order[:top_k]
    if top_p < 1.0:
        keep = probs.cumsum(0) - probs < top_p                      # smallest set covering top_p of the mass
        probs, order = probs[keep], order[keep]
    return int(order[torch.multinomial(probs / probs.sum(), 1)])

@torch.no_grad()
def generate(model, tok, prompt, n=200, **sampling):
    model.eval()
    ids = tok.encode(prompt)[-BLOCK:]
    caches = [{} for _ in model.blocks]
    logits = model(torch.tensor([ids]), caches, pos=0)[0, -1]      # ch 13: PREFILL the prompt once
    out = list(ids)
    for _ in range(n):                                             # ch 13: DECODE one token at a time
        if len(out) >= BLOCK: break                                # ch 14: the context window is a hard wall
        nxt = pick(logits, **sampling)
        out.append(nxt)
        logits = model(torch.tensor([[nxt]]), caches, pos=len(out) - 1)[0, -1]
    return tok.decode(out)


# ============================================================================
# Chapter 8: training. Measure surprise, find which way to nudge, nudge.
# ============================================================================
def train():
    torch.manual_seed(0)
    text = open("corpus.txt").read()
    tok = Tokenizer().train(text, VOCAB)
    data = torch.tensor(tok.encode(text))
    n = int(0.9 * len(data))
    splits = {"train": data[:n], "val": data[n:]}                  # ch 8: hold out text to catch memorising

    def batch(split):
        d = splits[split]
        ix = torch.randint(len(d) - BLOCK - 1, (BATCH,))
        x = torch.stack([d[i:i + BLOCK] for i in ix])
        y = torch.stack([d[i + 1:i + BLOCK + 1] for i in ix])      # ch 8: the target is the next token
        return x, y

    @torch.no_grad()
    def loss_on(split, iters=20):
        model.eval()
        l = sum(F.cross_entropy(model(x).flatten(0, 1), y.flatten()).item()
                for x, y in (batch(split) for _ in range(iters))) / iters
        model.train(); return l

    model = GPT()
    print(f"{sum(p.numel() for p in model.parameters()):,} parameters, {n:,} training tokens, "
          f"random-guess loss ln({VOCAB}) = {math.log(VOCAB):.2f}")
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    log = csv.writer(open("gpt_loss.csv", "w", newline="")); log.writerow(["step", "train_loss", "val_loss"])
    best, t0 = float("inf"), time.time()
    for step in range(STEPS + 1):
        if step % 100 == 0:
            tr, va = loss_on("train"), loss_on("val")
            log.writerow([step, f"{tr:.4f}", f"{va:.4f}"])
            print(f"step {step:5d}  train {tr:.3f}  val {va:.3f}  ({time.time() - t0:.0f}s)")
            if va < best:                                          # ch 9: keep the weights that generalise best
                best, best_step = va, step
                torch.save({"model": model.state_dict(), "merges": tok.merges}, "gpt.pt")
        x, y = batch("train")
        loss = F.cross_entropy(model(x).flatten(0, 1), y.flatten())  # ch 8: surprise at the true next token
        opt.zero_grad(); loss.backward(); opt.step()               # ch 8: which way to nudge; nudge
    print(f"saved best checkpoint (step {best_step}, val {best:.2f}) -> gpt.pt")


def load():
    ck = torch.load("gpt.pt")
    model = GPT(); model.load_state_dict(ck["model"])
    return model, Tokenizer(ck["merges"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["train", "generate"])
    ap.add_argument("prompt", nargs="?", default="The harness")
    ap.add_argument("-n", type=int, default=200)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=0)
    ap.add_argument("--top-p", type=float, default=1.0)
    a = ap.parse_args()
    if a.command == "train":
        train()
    else:
        torch.manual_seed(0)
        model, tok = load()
        print(generate(model, tok, a.prompt, n=a.n, temperature=a.temperature, top_k=a.top_k, top_p=a.top_p))

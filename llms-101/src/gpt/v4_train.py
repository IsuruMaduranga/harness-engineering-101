#!/usr/bin/env python3
"""Toy GPT v4: train a small GPT on the text of Harness Engineering 101.

Same architecture as v3_forward.py (embed, attention, MLP, residuals, layer
norm, unembed), now in PyTorch so gradients come for free. ~0.8M
parameters, a few minutes on a laptop. It learns the book's vocabulary and
rhythm and none of its meaning, which is the point of chapter 9.

    python3 v4_train.py            # writes loss.csv, toy_gpt.pt, prints samples
"""
import math, time, csv
import torch, torch.nn as nn, torch.nn.functional as F
from v1_tokenizer import train as train_bpe, Tokenizer

torch.manual_seed(0)
VOCAB, BLOCK, N_LAYER, N_HEAD, N_EMBD = 512, 128, 4, 4, 128
STEPS, BATCH, LR = 3000, 32, 1e-3
device = "cpu"                                          # tiny model: CPU is fine and portable


# ---- data: the whole book as one token stream ----------------------------
text = open("corpus.txt").read()
tok = Tokenizer(train_bpe(text, VOCAB))
data = torch.tensor(tok.encode(text))
n = int(0.9 * len(data))
train_data, val_data = data[:n], data[n:]              # hold out the last 10% to detect memorising

def get_batch(split):
    d = train_data if split == "train" else val_data
    ix = torch.randint(len(d) - BLOCK - 1, (BATCH,))
    x = torch.stack([d[i:i + BLOCK] for i in ix])       # BLOCK tokens of context ...
    y = torch.stack([d[i + 1:i + BLOCK + 1] for i in ix])  # ... and the token after each one
    return x.to(device), y.to(device)


# ---- model: v3_forward.py, in PyTorch ------------------------------------
class Attention(nn.Module):
    def __init__(self):
        super().__init__()
        self.c_attn = nn.Linear(N_EMBD, 3 * N_EMBD)
        self.c_proj = nn.Linear(N_EMBD, N_EMBD)
        self.register_buffer("mask", torch.tril(torch.ones(BLOCK, BLOCK)).bool())

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.c_attn(x).split(N_EMBD, dim=-1)
        split = lambda m: m.view(B, T, N_HEAD, C // N_HEAD).transpose(1, 2)   # (B, heads, T, 32)
        q, k, v = split(q), split(k), split(v)
        scores = q @ k.transpose(-2, -1) / math.sqrt(C // N_HEAD)
        scores = scores.masked_fill(~self.mask[:T, :T], float("-inf"))
        out = F.softmax(scores, dim=-1) @ v
        return self.c_proj(out.transpose(1, 2).reshape(B, T, C))

class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln_1, self.attn = nn.LayerNorm(N_EMBD), Attention()
        self.ln_2 = nn.LayerNorm(N_EMBD)
        self.mlp = nn.Sequential(nn.Linear(N_EMBD, 4 * N_EMBD), nn.GELU(), nn.Linear(4 * N_EMBD, N_EMBD))

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        return x + self.mlp(self.ln_2(x))

class GPT(nn.Module):
    def __init__(self):
        super().__init__()
        self.wte, self.wpe = nn.Embedding(VOCAB, N_EMBD), nn.Embedding(BLOCK, N_EMBD)
        self.blocks = nn.Sequential(*[Block() for _ in range(N_LAYER)])
        self.ln_f = nn.LayerNorm(N_EMBD)
        for m in self.modules():                        # GPT-2's init: small weights, so early logits are near-uniform
            if isinstance(m, (nn.Linear, nn.Embedding)):
                nn.init.normal_(m.weight, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

    def forward(self, ids):
        T = ids.shape[1]
        x = self.wte(ids) + self.wpe(torch.arange(T, device=ids.device))
        x = self.ln_f(self.blocks(x))
        return x @ self.wte.weight.T                    # tied unembedding, as in GPT-2

    @torch.no_grad()
    def generate(self, ids, n, temperature=1.0):
        for _ in range(n):
            logits = self(ids[:, -BLOCK:])[:, -1] / temperature
            nxt = torch.multinomial(F.softmax(logits, -1), 1)
            ids = torch.cat([ids, nxt], dim=1)
        return ids


# ---- training: nudge every weight in the direction that lowers surprise --
model = GPT().to(device)
print(f"{sum(p.numel() for p in model.parameters()):,} parameters, "
      f"{len(train_data):,} training tokens, vocab {VOCAB}")
print(f"random-guess loss would be ln({VOCAB}) = {math.log(VOCAB):.2f}")
opt = torch.optim.AdamW(model.parameters(), lr=LR)

@torch.no_grad()
def estimate_loss(split, iters=20):
    model.eval()
    losses = [F.cross_entropy(model(x).flatten(0, 1), y.flatten()).item()
              for x, y in (get_batch(split) for _ in range(iters))]
    model.train()
    return sum(losses) / len(losses)

log = open("loss.csv", "w", newline="")
writer = csv.writer(log); writer.writerow(["step", "train_loss", "val_loss"])
t0 = time.time()
best_val, best_state = float("inf"), None
for step in range(STEPS + 1):
    if step % 100 == 0:
        tr, va = estimate_loss("train"), estimate_loss("val")
        writer.writerow([step, f"{tr:.4f}", f"{va:.4f}"]); log.flush()
        print(f"step {step:5d}  train {tr:.3f}  val {va:.3f}  ({time.time() - t0:.0f}s)")
        if va < best_val:                                   # keep the weights from before memorising set in
            best_val, best_step = va, step
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    x, y = get_batch("train")
    logits = model(x)
    loss = F.cross_entropy(logits.flatten(0, 1), y.flatten())   # surprise at the true next token
    opt.zero_grad(); loss.backward(); opt.step()                 # which way to nudge, then nudge

def show(label):
    model.eval()
    for temp in (0.8, 1.0):
        ids = torch.tensor([tok.encode("The harness")])
        print(f"\n--- {label}, temperature {temp} ---")
        print(tok.decode(model.generate(ids, 150, temperature=temp)[0].tolist()))

show(f"FINAL weights, step {STEPS} (train {tr:.2f}, val {va:.2f})")
model.load_state_dict(best_state)
torch.save({"model": best_state, "merges": tok.merges}, "toy_gpt.pt")
show(f"BEST-VAL weights, step {best_step} (val {best_val:.2f})")

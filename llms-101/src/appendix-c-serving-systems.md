# Appendix C: Serving Systems

*LLMs 101, Appendix. [Series index](index.html) · [Prev](appendix-b-training-at-scale.md) ·
[Next: Appendix D](appendix-d-what-the-layers-do.md)*

---

Chapters 13 and 17 described what a serving system has to do: keep a KV
cache per conversation, batch many users' decode steps into one weight
read, and swap requests in and out as they finish. This appendix is how
that's actually built, because the design explains several things you see
from the outside: rate limits in tokens per minute, prompt caches that
expire, and latency that depends on who else is online.

> **A serving system is a memory manager for KV caches plus a scheduler
> for decode steps.** The hard problem is memory: caches are big, variable
> in size, and unpredictable in lifetime. The solution borrowed the
> operating-system idea of paging, and once caches were paged, batching,
> prefix sharing and eviction all became bookkeeping.

## The memory problem

A request's KV cache grows by one token per decode step, for an unknown
number of steps, and then vanishes when the reply ends. Early servers
allocated each request a contiguous block sized for the maximum possible
length. Most of that block was never used, so GPU memory that could have
held another user's cache sat reserved and empty. Measured waste in
2022-era servers was 60 to 80 percent of cache memory.

**Paged attention** (vLLM, 2023) fixed it the way operating systems fixed
the same problem in the 1960s. Divide GPU memory into fixed-size pages,
each holding the K and V for, say, sixteen tokens. Give each request a
page table mapping its logical positions to physical pages, and allocate a
new page only when the current one fills. Attention kernels follow the page
table when they read keys and values. Fragmentation drops to under a page
per request, and the freed memory holds more concurrent users, which
(chapter 17) is the whole source of throughput.

## Prefix sharing is a page table trick

Once caches live in pages with page tables, two requests that start with
the same tokens can point their page tables at the *same physical pages*
for the shared prefix, copy-on-write when they diverge. That's prompt
caching (body book chapter 5, this book chapter 13) as an implementation:
no separate cache store, just shared pages with reference counts. It also
explains the expiry: a shared prefix stays resident as long as some request
holds a reference or until the memory is needed for someone else, which on
a busy system is minutes. The five-minute TTL on your prompt cache is an
eviction policy on GPU pages.

## The scheduler

With memory paged, the scheduler's job is to decide, every few
milliseconds, which requests get a decode step. **Continuous batching**
(chapter 17) admits new requests as soon as pages are free and drops
finished ones, so the batch changes composition every step. Two further
refinements matter to what you experience:

**Chunked prefill.** A new request with a 100,000-token prompt needs a
long prefill, and if it runs as one operation, every other user's decode
step waits behind it and their tokens-per-second stalls. So prefill is cut
into chunks and interleaved with decode steps: a bit of your long prompt,
one token for everyone else, repeat. Your first token arrives later than it
otherwise might; everyone else's stream stays smooth.

**Prefill/decode disaggregation.** Since prefill is compute-bound and decode
is bandwidth-bound (chapter 13), some systems run them on different GPUs,
sized for each kind of work, and ship the KV cache from the prefill GPU to
the decode GPU over the interconnect. It's the kind of optimisation that
only pays at very high volume, and providers at that volume do it.

## Why the limits look the way they do

**Tokens per minute** is the natural unit of a rate limit because it's the
resource being scheduled: prefill tokens consume compute and decode tokens
consume memory-bandwidth-time, and both consume cache pages. Requests per
minute is a poor proxy, and providers moved away from it as soon as they
had the accounting.

**Latency service levels** are quoted as two numbers, time to first token
and time per output token, because they're produced by different phases
(prefill and decode) under different scheduling policies. A system tuned
for low time-to-first-token admits prefill aggressively; one tuned for
smooth streaming protects decode. You can't have both at full load, and
the "priority" or "fast" tiers on a price list are usually scheduler
policy, not different hardware.

**Overload errors** happen when there are no free pages. A 529 or 503 from
a provider is, mechanically, the memory manager declining a new page table.
The body book's Appendix D on retries is the client-side response to this
appendix.

## Model, session, and where they live

One subtlety worth stating plainly. The *weights* are loaded once per GPU
and shared by every request. The *KV cache* is per request and is the only
per-user state on the server, and it's discarded when the reply ends or
the pages are evicted. That's the mechanical truth behind the body book's
"the API is stateless": the server keeps nothing about you between calls
except, briefly and as an optimisation, some pages of keys and values that
it will happily throw away. Statelessness isn't a policy. It's that the
only state there is doesn't fit in memory for long.

*[Next: Appendix D — What the Layers Seem to Do](appendix-d-what-the-layers-do.md)*

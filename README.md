# Cellular Automata Music Experiments

I'm a hobbyist musician who has worked sporadically with sound and generative systems for many years. 

Between 2020 and 2022 I collaborated with Thomas Jackson Park (better known as [Mystified](https://spottedpeccary.com/artists/mystified)) on the **Oriondrive** project, a blend of procedural music generation and AI text-to-audio systems. That project combined [GenerIter](https://pypi.org/project/GenerIter) (Mystified's generative music tool), a custom [R Plumber](https://www.rplumber.io) API I wrote that used an early GPT model to produce text, [Amazon Polly](https://aws.amazon.com/polly) to render speech and [FFmpeg](https://www.ffmpeg.org) to merge those results with GenerIter's output. Later iterations of Oriondrive introduced a linear model challenge with extraction of numerical data from two separate music tracks and fitting a regression. Effectively, we built a full-fledged hip-hop band without human performers before LLM audio generators like Suno appeared on the market.

After that experience I became interested in [cellular automata](https://en.wikipedia.org/wiki/Cellular_automaton) (CA) as a source of structured randomness for musical generation, especially for producing MIDI patterns that serve as starting points for new tracks. Since 2022 I've released music under my own name, **LR Friberg**, using various CA rules to generate melodic skeletons. These MIDI sequences are then edited, layered and used in diverse synth setups (subtractive, additive, granular or sample-based) depending on the concept of each piece. Every composition is intentional and idea-driven. I don't use LLMs currently since they still tend to create generic "mood stickers" in ambient contexts, and I've shifted away from sampling as well. I embrace synth minimalism, often using no more than three synths per track; the approach "less is more" helps me to maintain focus and sonic clarity. As a result, my work has moved from relatively static textures to something more alive and deliberate. And, in general, music making helps me stay sane during my studies and develop my creativity further.

My musical influences include [State Azure](https://www.youtube.com/channel/UClKIjbgtWGzHtXhBDS_I0pg) (modular workflows), [Klaus Schulze](https://en.wikipedia.org/wiki/Klaus_Schulze) (aesthetic roots) and [Artificial Memory Trace](https://www.gruenrekorder.de/?page_id=4538) a.k.a. Slavek Kwi (organic, field-recording-based sound design). I've collaborated with Slavek on several albums and these projects continue to shape my thinking about generative processes, natural systems and sonic evolution.

Some of my collaborative works use external data as well. For instance, a collaboration with [Wayne DeFehr](https://www.waynedefehr.com) and other artists uses CA sounds modulated by a [Max for Live](https://www.ableton.com/en/live/max-for-live) device that filters the sound according to various parameters. The dataset used in the piece is time series data from [NOAA NCEI Climate at a Glance](https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series). This piece was featured in the [UNPOP](https://unpopularmusic.camp/playlist.html) installation at **Burning Man 2024**.

**Selected works:**

* Aura Colemount (with Artificial Memory Trace; [Mahorka](https://mahorka.org/release/320), 2022)
* Hope Prevails ([TH_TIMEPEACE](https://thtimepeace.bandcamp.com/album/hope-prevails), 2022)
* Light Expansion ([Attenuation Circuit](https://emerge.bandcamp.com/album/light-expansion), 2023)
* Twenty Thousand ([Attenuation Circuit](https://emerge.bandcamp.com/album/twenty-thousand), 2024)
* Green Sun ([Attenuation Circuit](https://emerge.bandcamp.com/album/green-sun), 2025)

## Turning a Cellular Automaton into MIDI

Below is a compact explanation of how to turn one-dimensional elementary cellular automaton output into MIDI using **Rule 190** as an example. The repository also contains a simple Python implementation for the algorithm.

We have a line of cells, each either 0 (off) or 1 (on). At time $`t`$, the state is $` \{ s_i^{(t)} \in \{0,1\} \mid i \in \mathbb{Z} \} `$. Each cell looks at its $`radius‑1`$ neighborhood:

$$
\mathbf n_i^{(t)}=\big(s_{i-1}^{(t)},s_i^{(t)},s_{i+1}^{(t)}\big)\in\{0,1\}^3
$$

and all cells update simultaneously using a rule table.

**Elementary cellular automata** are the 256 rules that only depend on those three bits. Wolfram's numbering encodes the outputs for neighborhoods $`(111,110,\ldots,000)`$ as one 8‑bit integer number.

### Rule 190 

Decimal 190 is binary $`10111110₂`$. Reading against $`(111,110,101,100,011,010,001,000)`$ gives the table:

| neigh. | 111 | 110 | 101 | 100 | 011 | 010 | 001 | 000 |
|:------:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| next   |  1  |  0  |  1  |  1  |  1  |  1  |  1  |  0  |

So

$$
s_i^{(t+1)} = f(\mathbf n_i^{(t)})
$$

with outputs as above. For audio‑friendly continuity I use **toroidal boundaries** rather than fixed zeros at the ends.

I start from a single 1 (one live cell, all other cells are 0). Because Rule 190 is quiescent (its output for neighborhood $`000`$ is 0), I can read each time‑row as a binary integer. This produces

$$
a_0,a_1,a_2,\ldots = 1,7,29,119,477,1911,7645,30583,\ldots
$$

with generating function

$$
F(x)=\sum_{t\ge0} a_t x^t=\frac{1+3x}{(1-x^2)(1-4x)}.
$$

### MIDI Mapping

I choose tempo (BPM), PPQ (pulses per quarter) and ticks per CA step $`q`$.  

A CA step lasts

$$
\Delta t=\frac{60}{\mathrm{BPM}}\cdot\frac{q}{\mathrm{PPQ}} \quad\text{seconds}.
$$

Number of steps in 8 seconds:

$$
\text{steps}=\left\lfloor \frac{8}{\Delta t}\right\rfloor
= \left\lfloor 8\cdot\frac{\mathrm{BPM}\cdot \mathrm{PPQ}}{60\,q}\right\rfloor .
$$

**Example:** BPM = 120, PPQ = 480, $`q=240`$ (an eighth‑note), so $`\Delta t=0.25`$ s (32 steps is ca 8 s)

Let the line have width $`W`$. For pitch mapping, I build a pitch array $`P[0..W-1]`$ (chromatic or a scale stretched across octaves) and set

$$
\mathrm{pitch}(i)=P[i].
$$

At step boundary $`t`$ (tick $`(t\cdot q)`$):

* Birth (0 to 1): I send `note_on(pitch(i), velocity)`.

* Death (1 to 0): send `note_off(pitch(i))`.

* Sustain vs Staccato: "sustain‑until‑death" (only birth/death events), staccato (for any cell that stays 1 also send `note_off` at $`t\cdot q + \mathrm{gate}\cdot q`$

* Velocity: $`30 + 10×age_i`$, capped at 110. 

### Pseudocode

```pseudo
RULE190 = {
  0b111:1, 0b110:0, 0b101:1, 0b100:1,
  0b011:1, 0b010:1, 0b001:1, 0b000:0
}

function next_rule190(row):           # Row: length W, values 0/1
    W = len(row)
    nxt = zeros(W)
    for i in 0..W-1:
        l = row[(i-1+W)%W]
        c = row[i]
        r = row[(i+1)%W]
        key = (l<<2) | (c<<1) | r
        nxt[i] = RULE190[key]
    return nxt
```

## References

[Wikipedia](https://en.wikipedia.org/wiki/Elementary_cellular_automaton)

[MathWorld](https://mathworld.wolfram.com/Rule190.html)

"""Build the Approach-E-only report with inlined figures."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIG = HERE / "results" / "e_figures"
OUTS = [HERE / "report-approach-e.html", HERE.parent / "docs" / "conjunction-e.html"]


def svg(name):
    text = (FIG / name).read_text()
    # matplotlib emits an XML decl + doctype; keep the <svg>… only
    start = text.find("<svg")
    return text[start:]


def main():
    html = TEMPLATE
    for key, name in (
        ("SATURATION", "saturation.svg"),
        ("CLUSTER_PRESSURE", "cluster_pressure.svg"),
        ("LOAD_SCALING", "load_scaling.svg"),
        ("TIMING", "timing.svg"),
        ("THREADS", "threads.svg"),
        ("ATTACK_SURFACE", "attack_surface.svg"),
        ("ATTACK_STATUS", "attack_status.svg"),
    ):
        html = html.replace("[[" + key + "]]", svg(name))
    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        print(f"wrote {out} ({len(html):,} bytes)")


TEMPLATE = """<!DOCTYPE html>
<title>Encrypted Conjunction Assessment — Approach E</title>
<style>
:root{
  --bg:#eef1ef; --surface:#ffffff; --surface-alt:#e3e9e6; --ink:#131a1f; --ink-soft:#55636a;
  --rule:#c7d1cd; --accent:#2f6f7a; --accent-soft:#d9e8ea; --accent-ink:#0f3339;
  --good:#2f7d4f; --good-soft:#dff0e4; --bad:#a8412a; --bad-soft:#f6e1da; --warn:#a5741e; --warn-soft:#f3e6cd;
  --mono: "SF Mono","IBM Plex Mono","JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
  --sans: -apple-system, "Neue Haas Grotesk Text Pro", "Helvetica Neue", "Segoe UI", Arial, sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1214; --surface:#141b1e; --surface-alt:#1b2528; --ink:#e7edee; --ink-soft:#9fb0b4;
    --rule:#2a3538; --accent:#5fb8c4; --accent-soft:#17313a; --accent-ink:#bfe9ee;
    --good:#6fce93; --good-soft:#173226; --bad:#e5896e; --bad-soft:#33201b; --warn:#e0b15a; --warn-soft:#332612;
  }
}
*{box-sizing:border-box;}
body{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans); line-height:1.55; -webkit-font-smoothing:antialiased; }
::selection{ background:var(--accent-soft); }
.wrap{ max-width:920px; margin:0 auto; padding:0 24px 96px; }
.masthead{ background:var(--surface); border-bottom:1px solid var(--rule); padding:40px 24px 32px; }
.masthead-inner{ max-width:920px; margin:0 auto; }
.eyebrow{ font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:600; }
h1{ font-size:clamp(26px,4vw,36px); font-weight:700; letter-spacing:-.01em; margin:10px 0 8px; text-wrap:balance; }
.subtitle{ color:var(--ink-soft); font-size:15.5px; max-width:66ch; margin:0; }
.meta-row{ display:flex; gap:20px; flex-wrap:wrap; margin-top:18px; font-family:var(--mono); font-size:12px; color:var(--ink-soft); }
.meta-row b{ color:var(--ink); font-weight:600; }
.panel{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1px; background:var(--rule); border:1px solid var(--rule); margin:28px 0 8px; }
.tile{ background:var(--surface); padding:16px 16px 14px; }
.tile .label{ font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-soft); }
.tile .value{ font-family:var(--mono); font-size:22px; font-weight:600; margin-top:6px; font-variant-numeric:tabular-nums; }
.tile .sub{ font-size:11.5px; color:var(--ink-soft); margin-top:3px; }
section{ margin-top:56px; }
h2{ font-size:22px; font-weight:700; margin:0 0 6px; letter-spacing:-.005em; }
h3{ font-size:15.5px; font-weight:700; margin:28px 0 10px; }
.section-eyebrow{ font-family:var(--mono); font-size:14px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--accent-ink); margin-bottom:6px; }
p{ margin:0 0 14px; max-width:70ch; }
p.wide{ max-width:none; }
.callout{ border-left:3px solid var(--accent); background:var(--accent-soft); padding:12px 16px; border-radius:2px; margin:16px 0; font-size:14px; max-width:70ch; }
.callout.warn{ border-color:var(--warn); background:var(--warn-soft); }
.callout.good{ border-color:var(--good); background:var(--good-soft); }
table{ border-collapse:collapse; width:100%; font-size:13px; }
.tbl-wrap{ overflow-x:auto; border:1px solid var(--rule); margin:14px 0 20px; }
th,td{ padding:9px 12px; text-align:right; border-bottom:1px solid var(--rule); white-space:nowrap; font-family:var(--mono); font-variant-numeric:tabular-nums; }
th{ background:var(--surface-alt); font-size:11px; letter-spacing:.04em; text-transform:uppercase; color:var(--ink-soft); font-weight:600; }
th:first-child, td:first-child{ text-align:left; font-family:var(--sans); white-space:normal; }
tr:last-child td{ border-bottom:none; }
tbody tr:hover{ background:var(--surface-alt); }
.tag{ display:inline-block; font-family:var(--mono); font-size:10.5px; padding:1px 6px; border-radius:3px; letter-spacing:.03em; }
.tag.good{ background:var(--good-soft); color:var(--good); }
.tag.bad{ background:var(--bad-soft); color:var(--bad); }
.tag.warn{ background:var(--warn-soft); color:var(--warn); }
.flow{ display:flex; align-items:stretch; gap:0; margin:20px 0; overflow-x:auto; border:1px solid var(--rule); }
.flow-step{ flex:1; min-width:150px; padding:16px; border-right:1px solid var(--rule); }
.flow-step:last-child{ border-right:none; }
.flow-step .who{ font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }
.flow-step .what{ font-weight:600; margin-top:4px; font-size:14px; }
.flow-step .cost{ font-family:var(--mono); font-size:11.5px; color:var(--ink-soft); margin-top:6px; }
.flow-step.once{ background:var(--surface-alt); }
.findings{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:16px; }
@media (max-width:640px){ .findings{ grid-template-columns:1fr; } }
.findings-col h3{ margin-top:0; }
.finding{ padding:12px 14px; border:1px solid var(--rule); margin-bottom:10px; font-size:13.5px; }
.finding.good{ border-left:3px solid var(--good); }
.finding.bad{ border-left:3px solid var(--bad); }
.finding.warn{ border-left:3px solid var(--warn); }
.finding b{ display:block; margin-bottom:3px; }
footer{ margin-top:64px; padding-top:20px; border-top:1px solid var(--rule); font-size:12px; color:var(--ink-soft); }
code{ font-family:var(--mono); font-size:12px; background:var(--surface-alt); padding:1px 5px; border-radius:3px; }
a{ color:var(--accent); text-decoration:none; border-bottom:1px solid var(--accent-soft); }
.curve-wrap{ border:1px solid var(--rule); background:var(--surface); padding:12px 12px 8px; margin:16px 0 20px; }
.curve-wrap svg{ width:100%; height:auto; display:block; }
.curve-caption{ font-size:12px; color:var(--ink-soft); margin:8px 4px 4px; max-width:none; }
.toc{ font-size:13px; color:var(--ink-soft); }
.toc a{ margin-right:8px; }
</style>

<div class="masthead">
  <div class="masthead-inner">
    <div class="eyebrow">Follow-on write-up · Approach E · OpenFHE CKKS bootstrapping</div>
    <h1>Two encrypted ephemerides, one decrypted count, nothing else in the clear</h1>
    <p class="subtitle">A later step in this series, after the
    <a href="https://jehadbaeth.github.io/homoenc/conjunction.html">multi-approach conjunction study</a>.
    Same real Starlink OEMs; this time only the protocol that finishes under encryption
    and decrypts a count. Positions, distances, times, and per-point flags stay ciphertext.</p>
    <div class="meta-row">
      <span><b>Pair:</b> STARLINK-35712 × STARLINK-3845</span>
      <span><b>Events:</b> 7 real close approaches</span>
      <span><b>Scheme:</b> OpenFHE CKKS + bootstrap</span>
      <span><b>Host:</b> Ryzen 9 5950X, 62 GB, Linux</span>
    </div>
  </div>
</div>

<div class="wrap">

<section style="margin-top:40px;">
  <div class="section-eyebrow">Abstract</div>
  <h2>What this report is</h2>
  <p class="wide" style="max-width:70ch; font-size:15px;">
  This is the Approach E write-up — the next report after
  <a href="https://jehadbaeth.github.io/homoenc/conjunction.html">the multi-approach conjunction study</a>,
  not a replacement for it. Two operators encrypt their
  <a class="acr" title="Orbit Ephemeris Message">OEM</a> position tables under CKKS. A third party,
  which never holds a decryption key, interpolates both trajectories at a public list of times,
  forms squared distance, iterates an offline sign polynomial until every flag saturates at ±1,
  bootstrapping whenever the modulus chain runs out, then sums the flags homomorphically.
  One scalar is decrypted. On the real STARLINK-35712 / STARLINK-3845 pair that scalar is
  <b>61.0000</b> against an ideal 61, which reads as a count of <b>exactly 1</b> — the 5.432 km
  conjunction — with the two near-boundary non-events at 11.698 km and 13.276 km left unflagged.
  </p>
  <p class="toc">
    <a href="#protocol">Protocol</a> ·
    <a href="#data">Real data</a> ·
    <a href="#attacks">Attack vectors</a> ·
    <a href="#pressure">Under pressure</a> ·
    <a href="#latency">Latency</a> ·
    <a href="#findings">Findings</a> ·
    <a href="#reproduce">Reproduce</a>
  </p>
</section>

<div class="panel">
  <div class="tile"><div class="label">Decrypted output</div><div class="value">1.0000</div><div class="sub">violation count, (n − sum) / 2</div></div>
  <div class="tile"><div class="label">Flag-sum</div><div class="value">61.0000</div><div class="sub">vs. ideal 61, 63 packed times</div></div>
  <div class="tile"><div class="label">True CPA</div><div class="value">5.432 km</div><div class="sub">t = +0.5 s, real TLEs</div></div>
  <div class="tile"><div class="label">Near-boundary</div><div class="value">11.7 / 13.3 km</div><div class="sub">correctly unflagged</div></div>
  <div class="tile"><div class="label">7-event wall time</div><div class="value">8.55 s</div><div class="sub">OMP=8, demo ring 2¹³</div></div>
  <div class="tile"><div class="label">Peak RSS</div><div class="value">4.52 GB</div><div class="sub">full 7-event process</div></div>
</div>

<section id="protocol">
  <div class="section-eyebrow">Protocol</div>
  <h2>A full encrypted round</h2>
  <p>Each operator encrypts only the position samples of their OEM — <code>x, y, z</code> at the
  public sample times. Query times, the 10 km threshold, and the interpolation weights (which
  depend only on those times) stay in the clear. Everything that is an orbit stays a ciphertext
  until the very last step.</p>
  <div class="flow">
    <div class="flow-step once"><div class="who">Each owner, once</div><div class="what">Encrypt OEM x/y/z</div><div class="cost">130 ms for both, packed</div></div>
    <div class="flow-step"><div class="who">Host, no key</div><div class="what">Lagrange interpolate + distance²</div><div class="cost">one SIMD pass, 0.94 s</div></div>
    <div class="flow-step"><div class="who">Host, no key</div><div class="what">11× sign poly, 3 bootstraps</div><div class="cost">1.92 s + 4.61 s</div></div>
    <div class="flow-step"><div class="who">Key holder, once</div><div class="what">Decrypt the masked sum</div><div class="cost">50 ms · one number</div></div>
  </div>
  <p>All 63 candidate times ride in one ciphertext: a 64-slot block per time (next power of two
  above the 59-sample local OEM window), 4032 of 4096 slots used. After the flags saturate,
  a one-hot plaintext mask keeps only slot 0 of each block — the only slot
  <code>EvalInnerProduct</code> reliably populates — and <code>EvalSum</code> folds those
  63 values into one scalar. A naive average over the whole block silently corrupts the count;
  that bug is why the mask exists.</p>
  <div class="callout warn">
    Parameters are <code>HEStd_NotSet</code> at ring dimension 2<sup>13</sup> — OpenFHE’s own
    bootstrapping-demo set, not 128-bit production security. A real deployment needs a much
    larger ring. Every latency number on this page is a feasibility measurement at that demo
    size, not a service-level target.
  </div>
</section>

<section id="data">
  <div class="section-eyebrow">Real data</div>
  <h2>One Starlink pair, seven real close approaches</h2>
  <p>The OEMs are 60-second-cadence position tables from live CelesTrak TLEs for
  <b>STARLINK-35712</b> and <b>STARLINK-3845</b>, spanning ±3 hours around the closest
  approach. A dense plaintext SGP4 search found seven genuine local minima — not constructed
  geometries. Each event gets a ±40 s / 10 s monitoring window (9 times). That is 63 public
  query times, packed together.</p>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Cluster</th><th>Offset from CPA</th><th>Miss distance</th><th style="text-align:left;">Ground truth</th><th style="text-align:left;">Encrypted flag</th></tr></thead>
      <tbody>
        <tr><td>0</td><td>−8438.0 s</td><td>61.867 km</td><td style="text-align:left;">safe</td><td style="text-align:left;">+1.0000</td></tr>
        <tr><td>1</td><td>−5625.0 s</td><td>28.934 km</td><td style="text-align:left;">safe</td><td style="text-align:left;">+1.0000</td></tr>
        <tr><td>2</td><td>−2812.5 s</td><td>37.470 km</td><td style="text-align:left;">safe</td><td style="text-align:left;">+1.0000</td></tr>
        <tr><td>3</td><td>+0.5 s</td><td><b>5.432 km</b></td><td style="text-align:left;"><b>violation</b></td><td style="text-align:left;"><b>−1.0000</b></td></tr>
        <tr><td>4</td><td>+2813.5 s</td><td>13.276 km</td><td style="text-align:left;">safe, 3.3 km outside</td><td style="text-align:left;">+1.0000</td></tr>
        <tr><td>5</td><td>+5626.5 s</td><td>20.363 km</td><td style="text-align:left;">safe</td><td style="text-align:left;">+1.0000</td></tr>
        <tr><td>6</td><td>+8439.5 s</td><td>11.698 km</td><td style="text-align:left;">safe, 1.7 km outside</td><td style="text-align:left;">+1.0000</td></tr>
      </tbody>
    </table>
  </div>
  <p>The decrypted production output is not this table. This table is a diagnostic decrypt of
  slot 0 in each block, used only to check saturation and to write this report. The number a
  deployment would hand a key holder is the sum, 61.0000.</p>
</section>

<section id="attacks">
  <div class="section-eyebrow">Attack vectors</div>
  <h2>Who sees what, and what we did not close</h2>
  <p>CKKS gives confidentiality against anyone who does not hold the secret key. That is the
  whole mitigation for an honest-but-curious host. Everything else is either a design choice
  already in the protocol, or explicitly out of scope.</p>
  <div class="curve-wrap">
    [[ATTACK_SURFACE]]
    <p class="curve-caption">Two owners encrypt locally. The host evaluates on ciphertext and
    never decrypts. The key holder sees one integer-valued count, not which time it was and
    not how close.</p>
  </div>
  <div class="curve-wrap">
    [[ATTACK_STATUS]]
    <p class="curve-caption">Residual exposure this design does not close, qualitatively.
    Green / teal: handled or measured. Amber: accepted as public or as a disclosed limit.
    Red: out of scope.</p>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Vector</th><th style="text-align:left;">What an adversary wants</th><th style="text-align:left;">Status</th></tr></thead>
      <tbody>
        <tr><td><span class="tag good">handled</span> Honest-but-curious host</td><td style="text-align:left; font-family:var(--sans);">Read OEM positions, distances, or flags from memory or logs</td><td style="text-align:left; font-family:var(--sans);">Host never holds a key. Its entire view is ciphertext plus public metadata.</td></tr>
        <tr><td><span class="tag good">handled</span> Over-disclosure of the answer</td><td style="text-align:left; font-family:var(--sans);">A non-owning receiver learns the other party’s orbit from the result</td><td style="text-align:left; font-family:var(--sans);">Production decrypt is one count. No curve, no per-point flag, no miss distance.</td></tr>
        <tr><td><span class="tag good">measured</span> CKKS misclassification</td><td style="text-align:left; font-family:var(--sans);">Noise flips a near-threshold event</td><td style="text-align:left; font-family:var(--sans);">On this pair, the 5.432 km event and both near-boundary safes classify correctly after 11 compositions. Not a general margin guarantee.</td></tr>
        <tr><td><span class="tag warn">acknowledged</span> Public candidate times</td><td style="text-align:left; font-family:var(--sans);">Infer that a conjunction search already happened, and when</td><td style="text-align:left; font-family:var(--sans);">The 7 query windows come from a plaintext TLE search run before any ciphertext exists. E answers “how many of these known times,” not “find a CPA in a private window.”</td></tr>
        <tr><td><span class="tag warn">disclosed</span> Demo-grade parameters</td><td style="text-align:left; font-family:var(--sans);">Break the CKKS instance at this ring size</td><td style="text-align:left; font-family:var(--sans);"><code>HEStd_NotSet</code>, ring 2<sup>13</sup>. Stated, not hidden. Production would be much slower.</td></tr>
        <tr><td><span class="tag bad">out of scope</span> Tampering host</td><td style="text-align:left; font-family:var(--sans);">Return a wrong count, swap in another customer’s OEM</td><td style="text-align:left; font-family:var(--sans);">CKKS is confidentiality, not integrity. Needs authenticated or verifiable computation on top.</td></tr>
        <tr><td><span class="tag bad">out of scope</span> Host + one owner collude</td><td style="text-align:left; font-family:var(--sans);">Combine the key and the other party’s ciphertext</td><td style="text-align:left; font-family:var(--sans);">Would need threshold / multi-key FHE or MPC. Neither is built here.</td></tr>
      </tbody>
    </table>
  </div>
</section>

<section id="pressure">
  <div class="section-eyebrow">Under pressure</div>
  <h2>The same ciphertext, harder real geometry</h2>
  <p>The interesting failure mode for this protocol is not “FHE is slow.” It is a flag that
  sits too close to zero to be a trustworthy ±1, so the decrypted sum cannot be read as a
  count. That is exactly what happens at composition 1 on this pair: the 5.432 km violation
  decrypts to <b>−4.8×10<sup>−5</sup></b> and the 11.698 km safe event to
  <b>+2.5×10<sup>−5</sup></b>. The sign is already correct. The magnitude is not a count.</p>
  <p>Each extra composition of <code>g(x) = (3x − x³)/2</code> pushes those values away from
  zero. The far-safe 61.9 km event saturates by composition 7. The violation and the two
  near-boundary safes need the full 11, and three <code>EvalBootstrap</code> calls to pay for
  that depth.</p>
  <div class="curve-wrap">
    [[SATURATION]]
    <p class="curve-caption">Encrypted flag at each cluster’s own CPA, after every composition.
    Red: 5.432 km violation. Amber: 11.698 km and 13.276 km. Green: 61.867 km. Dashed lines
    are ±1. The near-boundary pair is still in the linear region at composition 6; only the
    last two compositions pin them to ±1.</p>
  </div>
  <div class="curve-wrap">
    [[CLUSTER_PRESSURE]]
    <p class="curve-caption">Final flags for all seven real CPAs against the public 10 km
    line. One point is below, six are above, and the two closest safes are on the correct
    side after saturation. Distances on the x-axis are the dense-SGP4 ground truth, not
    something the encrypted path ever decrypts.</p>
  </div>
  <p>Adding those harder events to the same ciphertext does not make the evaluation more
  expensive. Packing 1, 3, 5, then all 7 real clusters — violation first, then the two
  near-boundary safes, then the rest — keeps wall-clock at <b>8.4–8.6 s</b>. Bootstrap
  dominates and is a property of the ring, not of how many of the 4096 slots we use.</p>
  <div class="curve-wrap">
    [[LOAD_SCALING]]
    <p class="curve-caption">End-to-end time and its three heavy stages as more real events
    share one ciphertext. The estimated count stays 1.0000 at every step. SIMD packing is
    why “more conjunctions” is not “more seconds” until the slot budget fills.</p>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Events packed</th><th>Times</th><th>Flag-sum</th><th>Count</th><th>True</th><th>Total</th><th>Bootstrap</th></tr></thead>
      <tbody>
        <tr><td>1 (violation only)</td><td>9</td><td>7.0000</td><td>1.0000</td><td>1</td><td>8.57 s</td><td>4.65 s</td></tr>
        <tr><td>3 (+ two near-boundary)</td><td>27</td><td>25.0000</td><td>1.0000</td><td>1</td><td>8.41 s</td><td>4.54 s</td></tr>
        <tr><td>5</td><td>45</td><td>43.0000</td><td>1.0000</td><td>1</td><td>8.61 s</td><td>4.68 s</td></tr>
        <tr><td>7 (full window)</td><td>63</td><td>61.0000</td><td>1.0000</td><td>1</td><td>8.55 s</td><td>4.59 s</td></tr>
      </tbody>
    </table>
  </div>
</section>

<section id="latency">
  <div class="section-eyebrow">Latency</div>
  <h2>Where the time goes, and how many cores help</h2>
  <p>On this host (AMD Ryzen 9 5950X, 16 cores / 32 threads, 62 GB, Linux), with
  <code>OMP_NUM_THREADS=8</code>, the full 7-event run spends most of its time refreshing
  levels. Encryption of both OEMs is a rounding error.</p>
  <div class="curve-wrap">
    [[TIMING]]
    <p class="curve-caption">Stage times for the 63-point, 7-event ciphertext. Peak RSS
    4.52 GB. Demo ring 2<sup>13</sup>, multiplicative depth 37.</p>
  </div>
  <p>OpenFHE parallelizes NTTs and bootstrapping with OpenMP. The default on this machine
  is 32 threads (every hyperthread). That is slower than 8 physical cores. Sixteen is
  already slightly worse than 8: at this ring size the inner loops run out of RNS limbs
  before they can feed the whole chip.</p>
  <div class="curve-wrap">
    [[THREADS]]
    <p class="curve-caption">Single-event 61-point ciphertext, quiet machine. 1 thread ≈ 34 s
    end-to-end; 8 threads ≈ 9 s; 32 threads ≈ 14 s. Use physical cores, not SMT.</p>
  </div>
</section>

<section id="findings">
  <div class="section-eyebrow">Findings</div>
  <h2>What holds, stated narrowly</h2>
  <div class="findings">
    <div class="findings-col">
      <h3>What holds up</h3>
      <div class="finding good"><b>The encrypted round is real.</b> Both OEM position tables stay ciphertext through interpolation, distance², eleven nonlinear compositions, and the sum. The key holder decrypts one number. That number is a correct count on this pair.</div>
      <div class="finding good"><b>Near-boundary real events classify correctly once saturated.</b> 11.698 km and 13.276 km — 1.7 km and 3.3 km outside the line — finish at +1.0000. The 5.432 km event finishes at −1.0000. The recipe was not retuned for the 7-event window.</div>
      <div class="finding good"><b>More real events are almost free until the ring fills.</b> 1 through 7 clusters stay at 8.4–8.6 s. The limit is 64 blocks × 64 slots in this parameter set, not “one pair at a time.”</div>
    </div>
    <div class="findings-col">
      <h3>What does not</h3>
      <div class="finding bad"><b>Without bootstrapping, the sum is not a count.</b> After one composition the interesting flags are 10<sup>−5</sup>. Sign is right; magnitude is useless. That is why this protocol is OpenFHE, not a shallow CKKS context.</div>
      <div class="finding warn"><b>Candidate times are a public input.</b> Whoever runs this already knows the seven approach windows. The hidden fact is which of them crossed 10 km, and by how much — the “how much” never leaves encryption at all.</div>
      <div class="finding warn"><b>Security parameters are not production.</b> Ring 2<sup>13</sup>, <code>HEStd_NotSet</code>. Moving to a 128-bit bootstrap (typically 2<sup>16</sup>–2<sup>17</sup>) is expected to cost one to two orders of magnitude per refresh. Untested here.</div>
    </div>
  </div>
</section>

<section id="reproduce">
  <div class="section-eyebrow">Reproduce</div>
  <h2>How these numbers were produced</h2>
  <p>Python 3.12, <code>openfhe==1.5.1.0.24.4</code> (the Linux x86_64 wheel — it will not
  import on 3.14 or on macOS/arm64). From the repo root:</p>
  <p><code>OMP_NUM_THREADS=8 PYTHONPATH=oem-conjunction .venv-openfhe/bin/python oem-conjunction/09_approach_e_openfhe_bootstrap.py</code></p>
  <p><code>OMP_NUM_THREADS=8 PYTHONPATH=oem-conjunction .venv-openfhe/bin/python oem-conjunction/13_multi_approach_e_openfhe_bootstrap.py</code></p>
  <p><code>OMP_NUM_THREADS=8 PYTHONPATH=oem-conjunction .venv-openfhe/bin/python oem-conjunction/benchmark_e.py</code></p>
  <p>Then <code>plot_e.py</code> and <code>build_report_e.py</code>. Inputs are
  <code>data/oem_a_multi.csv</code>, <code>data/oem_b_multi.csv</code>,
  <code>data/multi_ground_truth.csv</code>, <code>data/sign_poly_coeffs.json</code> — real
  TLE-derived OEMs, not synthetic trajectories. The production decrypt path is
  <code>masked_flag_sum</code> in <code>openfhe_e.py</code>. Per-point flag CSVs are
  diagnostics for this write-up.</p>
</section>

<footer>
  Follow-on to the <a href="https://jehadbaeth.github.io/homoenc/conjunction.html">multi-approach conjunction study</a>
  and the <a href="https://jehadbaeth.github.io/homoenc/">SGP4/CKKS feasibility study</a>.
  Approach E only. Real STARLINK-35712 × STARLINK-3845 OEMs, OpenFHE 1.5.1, measured on
  Llama-Desktop (Ryzen 9 5950X, Linux, 62 GB) with <code>OMP_NUM_THREADS=8</code>.
</footer>
</div>
"""


if __name__ == "__main__":
    main()

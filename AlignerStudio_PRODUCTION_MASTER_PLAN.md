# ALIGNER STUDIO
# PRODUCTION MASTER PLAN
## World-Class 3D Clear-Aligner Planning Platform

**Version:** 2.0  
**Status:** ACTIVE / AUTHORITATIVE  
**Planning principle:** Build a production-grade dental CAD / clear-aligner platform, not a visual demo.

---

# 00 — PRODUCT NORTH STAR

Aligner Studio should feel like a serious professional dental CAD system:

- large, high-quality 3D workspace
- precise tooth interaction
- clear upper/lower anatomy
- coherent clinical workflow
- fast and truthful processing
- editable treatment setup
- dynamic staging
- real geometric validation
- auditable doctor changes
- reproducible export
- manufacturing-aware architecture
- model-assisted planning only where it is measurable and explainable

The goal is not to copy one competitor.

The goal is to combine the strongest proven ideas from dental CAD, 3D geometry, orthodontic planning research, and modern professional application UX into one coherent system.

---

# 01 — ARCHITECTURE PRINCIPLES

## 1.1 Layered architecture

```text
CASE SESSION
      │
      ├─────────────── WORKFLOW STATE
      │
      ▼
DENTAL SCENE
      │
      ├── Real Scan
      ├── Teeth
      ├── Real Gingiva
      ├── Visual Gingiva
      ├── Occlusion
      ├── Segmentation
      ├── Target Setup
      └── Stage State
      │
      ▼
GEOMETRY / SPATIAL ENGINE
      │
      ├── measurements
      ├── proximity
      ├── contacts
      ├── collisions
      ├── intersections
      └── mesh operations
      │
      ▼
DENTAL INTELLIGENCE
      │
      ├── identity
      ├── landmarks
      ├── local axes
      ├── arch form
      └── occlusion
      │
      ▼
PLANNING ENGINE
      │
      ├── target setup
      ├── constraints
      ├── staging
      └── alternatives
      │
      ▼
DOCTOR REFINEMENT
      │
      ▼
VALIDATION
      │
      ▼
MANUFACTURING / EXPORT
```

The UI is a presentation and interaction layer above these systems.

Clinical/geometry calculations must not live inside UI components.

---

# 02 — OPEN-SOURCE STRATEGY

## We WILL use open source when it provides real leverage.

There is no rule saying that Aligner Studio should implement everything ourselves.

The correct rule is:

> **Use proven open-source components when they reduce implementation time, improve quality/performance, fit the architecture, and have acceptable licensing.**

Do not reject a library merely because it is external.

Do not add a library merely because it is popular.

Every dependency must pass this gate:

```text
Does it solve a real problem?
        ↓
Is the license commercially acceptable?
        ↓
Is it technically compatible?
        ↓
Does it preserve our data/provenance model?
        ↓
Does it improve performance or implementation effort?
        ↓
Can we isolate it behind an adapter/boundary?
        ↓
YES → ADOPT / INTEGRATE
NO  → EVALUATE / REFERENCE / REJECT
```

## 2.1 Dependency categories

### ADOPT
Production dependency.

Use when:
- mature enough
- license acceptable
- measurable benefit
- architecture-compatible
- testable

### ADAPTER
Integrated behind our own interface.

Use for:
- AI models
- segmentation
- landmarks
- planning models
- geometry engines
- replaceable algorithms

### EVALUATE
Benchmark first.

No production dependency until:
- real-case benchmark
- correctness comparison
- performance measurement
- licensing check

### REFERENCE
Study architecture/algorithms, do not import code.

### REJECT
Do not use because:
- license conflict
- poor technical fit
- obsolete environment
- unacceptable performance
- insufficient reliability
- duplicates existing capability

---

# 03 — CURRENT OPEN-SOURCE / MODEL POSITION

## 3.1 Dental-CAD-Designer
**Decision: REFERENCE + SELECTIVE PATTERN ADOPTION**

Useful ideas:
- imperative Three.js engine separated from React UI
- geometry workers
- Float64 data-of-record
- render-only copies
- BVH acceleration
- export re-validation
- QC gates
- explicit data mutation

This is strongly aligned with our architecture. It should influence implementation patterns, not become a wholesale dependency. Its current scope is restoration CAD rather than aligner planning. citeturn0search0turn0search3

## 3.2 OpenSourceOrtho
**Decision: PRIMARY ARCHITECTURAL REFERENCE**

Useful areas:
- clear-aligner workflow
- staged movement
- upper/lower review
- crown proximity
- data gaps
- provenance
- reproducible exports
- doctor/technician workflow
- future root/bone-aware boundary

It explicitly describes itself as a research toolkit rather than complete treatment-planning/medical-device software, so we use its transparent architecture and safety boundaries rather than treating it as a drop-in clinical engine. citeturn0search4

## 3.3 three-mesh-bvh
**Decision: STRONG CANDIDATE FOR ADOPTION**

This is not a library we should avoid.

It directly solves a real 3D performance problem:
- accelerated raycasting
- spatial queries
- distance/intersection tooling
- worker generation
- large-mesh interaction

It is MIT licensed and designed specifically for Three.js mesh acceleration. citeturn0search1turn0search8

Adopt it when the current profiling shows the relevant viewer/spatial workloads benefit from it, and isolate it through a geometry/spatial adapter.

## 3.4 Manifold3D
**Decision: EVALUATE → ADOPT IF REQUIRED**

Use if we need:
- robust booleans
- watertight solid operations
- shell/offset operations
- manufacturing geometry

Do not hand-build a complex solid-geometry kernel if a mature, compatible library gives us a materially better result.

## 3.5 ToothInstanceNet
**Decision: CURRENT SEGMENTATION ADAPTER**

Remain behind the existing adapter.

Do not replace it without measured evidence.

## 3.6 3DTeethSAM
**Decision: BENCHMARK CANDIDATE**

It provides 3D tooth instance segmentation using SAM2-based methods and reports strong Teeth3DS benchmark numbers, but its stack is substantial (PyTorch3D, checkpoints, preprocessing). It should be benchmarked against our real artifacts before any production replacement decision. citeturn0search5

## 3.7 STTAlign
**Decision: RESEARCH ADAPTER / BENCHMARK**

Potentially useful for:
- tooth alignment
- occlusion-aware prediction
- collision-aware prediction
- landmark/transformer ideas

Its published implementation currently depends on an older CUDA/PyTorch/PyTorch3D environment, so it should be isolated rather than coupled directly into production. citeturn0search6

## 3.8 TADPM
**Decision: RESEARCH ADAPTER / BENCHMARK**

Potentially useful for:
- automatic tooth arrangement
- point + mesh representations
- diffusion-based planning

Its current environment is specialized and CUDA-dependent, so it should be evaluated offline before any production integration. citeturn0search2

## 3.9 Manufacturing / Dental CAD references

Open dental CAD projects can reduce implementation work for:
- undercut analysis
- blockout
- shell generation
- manufacturing QC
- watertight export

But they must be evaluated individually for:
- commercial licensing
- real-scan reliability
- architectural compatibility
- maintenance
- output correctness

No proprietary commercial aligner algorithm or asset is to be copied.

---

# 04 — P0
# PRODUCTION ACCEPTANCE CLOSURE

**Status: ACTIVE**

This is the only active phase before visual production work.

## Objective

Close the remaining real-case acceptance issues discovered after the performance work.

### P0.1 — Two-Arch Correctness
Verify:
- upper arch exists
- lower arch exists
- correct transforms
- correct visibility
- correct scene composition
- correct camera/framing
- correct segmentation layers

### P0.2 — Validation Reconciliation
Reconcile browser versus benchmark results for:
- collisions
- contacts
- proximity
- stage selection
- mesh states
- semantic identity
- thresholds

No suppression or artificial PASS.

### P0.3 — Export Integrity
Fix:
- source/stage geometry comparison
- target/final geometry comparison
- semantic-only tooth identity
- provenance
- stage integrity

Never invent FDI.

### P0.4 — Clean Browser Acceptance

```text
CASE
 ↓
UNDERSTAND
 ↓
PLAN
 ↓
REVIEW
 ↓
REFINE
 ↓
VALIDATE
 ↓
EXPORT
```

## Gate

P0 closes only when:
- real case passes end-to-end
- both arches are correctly represented
- validation is reconciled
- export succeeds
- exported data remains auditable

---

# 05 — P1
# PRODUCTION VISUAL FOUNDATION

**Status: QUEUED**

This phase is visual/interaction foundation only.

## Visual language

- dark premium CAD environment
- ivory realistic teeth
- realistic soft-pink gingiva
- professional lighting
- shadows
- highlights
- depth and spatial separation
- premium typography
- consistent design tokens
- contextual controls
- polished buttons
- professional toolbars
- responsive panel hierarchy

## Gingiva

### Real data
If usable gingiva exists:
→ use real gingival geometry.

### No usable gingiva
→ generate a synthetic gingival envelope.

Target appearance:

- continuous gingival envelope
- natural gingival margins around crowns
- soft-pink realistic material
- integrated upper/lower presentation
- no obvious rectangular/base-like appearance
- professional CAD presentation

Synthetic gingiva is:

**PRESENTATION ONLY**

It must never affect:
- treatment calculations
- measurements
- contacts
- collisions
- proximity
- staging
- clinical validation
- clinical approval

It must exist as an independently toggleable scene layer.

## Interaction

- selected tooth
- target ghost
- movement vectors
- contextual toolbar
- camera controls
- upper/lower presentation
- layer controls
- smooth transitions
- loading experience using Aligner Studio branding
- truthful progress

## Hard constraints

- no Three.js rewrite
- no R3F migration for cosmetic reasons
- no duplicate viewer
- no duplicate store
- no treatment-math rewrite

---

# 06 — P2
# PROFESSIONAL CLINICAL-CAD WORKFLOW

**Status: QUEUED**

The product workflow must use terminology that feels native to professional dental CAD / orthodontic software.

## Master workflow labels

```text
CASE INTAKE
    ↓
ANALYSIS
    ↓
TREATMENT SETUP
    ↓
STAGING
    ↓
REFINEMENT
    ↓
VALIDATION
    ↓
PRODUCTION
```

### Why these labels

- **Case Intake** is more professional and precise than `Case`.
- **Analysis** is more natural to a clinical/dental workflow than `Understand`.
- **Treatment Setup** describes the actual virtual setup rather than the vague `Plan`.
- **Staging** is the established orthodontic/CAD concept for sequence generation.
- **Refinement** clearly describes doctor adjustments.
- **Validation** remains the correct engineering/geometry term.
- **Production** is more useful than `Export` because the final workflow includes manufacturing preparation, appliance stages, reports, and export.

## 2.1 Case Intake

UI label examples:
- New Case
- Case Information
- Scan Import
- Data Readiness
- Upper Arch
- Lower Arch
- Case Status

Capabilities:
- case identity
- scan intake
- data completeness
- upper/lower status
- processing state

## 2.2 Analysis

UI label examples:
- Analysis
- Tooth Identification
- Arch Analysis
- Occlusion
- Measurements
- Data Quality
- Review Findings

Capabilities:
- anatomy overview
- tooth identities
- landmarks
- local axes
- arch orientation
- occlusion
- measurements
- warnings/data gaps

## 2.3 Treatment Setup

UI label examples:
- Treatment Setup
- Initial Position
- Target Position
- Tooth Movement
- Setup Comparison

Capabilities:
- target setup
- movement summary
- original vs target
- plan versions
- setup alternatives

## 2.4 Staging

UI label examples:
- Staging
- Stage Timeline
- Movement Sequence
- Stage Goals
- Stage Parameters

Capabilities:
- stage timeline
- original/current/target
- upper/lower controls
- movement vectors
- stage goals
- dynamic staging
- playback
- per-tooth movement review

## 2.5 Refinement

UI label examples:
- Refinement
- Tooth Controls
- Movement
- Attachments
- IPR
- Edit History

Capabilities:
- tooth selection
- 6-DOF transform
- tip
- torque
- angulation
- intrusion/extrusion
- lock/exclude
- undo/redo
- recalculate

## 2.6 Validation

UI label examples:
- Validation
- Geometry
- Contacts
- Proximity
- Collisions
- Movement Constraints
- Stage Consistency
- Data Completeness
- Review Status

Capabilities:
- geometry
- contacts
- proximity
- collisions
- movement constraints
- stage consistency
- data completeness
- doctor-review status

Avoid the phrase `Clinical Approval` unless a separately validated clinical/regulatory workflow actually exists.

## 2.7 Production

UI label examples:
- Production
- Appliance Stages
- Manufacturing Preparation
- IPR Report
- Attachment Plan
- Auxiliary Features
- Export Package
- Production QA

World-class production scope should also leave explicit room for:
- attachment groups
- hooks / elastic cutouts where supported
- bite stops where supported
- pontic workflow where supported
- trim/cutout tools
- model trimming
- arch-form controls
- space-management visualization
- production labels/identifiers
- printable stage preparation

Capabilities:
- reproducible package
- stage artifacts
- plan version
- doctor edits
- validation
- provenance
- manifest/hashes
- manufacturing preparation
- appliance outputs where implemented

## 2.8 Contextual navigation

The application should not force the user through seven full-screen pages.

Use:
- persistent workflow header
- context-sensitive left tools
- large central 3D viewport
- context-sensitive right inspector
- stage timeline when applicable
- contextual actions

The current workflow step should be visually obvious without making the interface feel like a wizard.


---

# 07 — P3
# DENTAL DATA & ANATOMICAL INTELLIGENCE

**Status: QUEUED**

This is the foundation required for genuinely professional orthodontic planning.

## Tooth intelligence

- stable semantic tooth identity
- FDI only when genuinely supported
- tooth orientation
- local tooth coordinate frame
- crown landmarks
- tooth axes
- movement reference frames

## Arch intelligence

- upper/lower arch orientation
- arch form
- midline
- tooth-to-arch relationship
- inter-tooth relationships

## Occlusion

- upper/lower registration
- occlusal relationship
- bite record representation
- occlusal contacts where data supports them

## Data quality

- scale validation
- units
- mesh quality
- incomplete scans
- missing teeth
- ambiguous identity
- incomplete occlusion
- missing anatomy

## Root/bone boundary

Crown-only STL data must remain clearly distinct from:
- roots
- bone
- periodontal structures

When CBCT/DICOM is genuinely available, architecture should support a future root/bone-aware pathway.

Never infer invisible anatomy as fact.

---

# 08 — P4
# DOCTOR REFINEMENT & TREATMENT PLANNING

**Status: QUEUED**

## Target setup

- deterministic target representation
- tooth-local movement
- doctor-controlled movement
- constraints
- lock/exclude
- plan versions

## 6-DOF controls

- translation X/Y/Z
- rotation
- tip
- torque
- angulation
- intrusion
- extrusion

## Staging

- dynamic stage count
- macro/micro staging
- accumulated movement
- stage playback
- original/current/target comparison
- stage validation

## Recalculation

Any doctor edit must trigger:

```text
Doctor Edit
 ↓
Target Update
 ↓
Staging Rebuild
 ↓
Validation
 ↓
Updated Review
```

No stale validation.

---

# 09 — P5
# VALIDATION + MANUFACTURING + EXPORT

**Status: QUEUED**

## Validation

- exact geometry checks
- collision
- contact
- proximity
- stage consistency
- movement constraints
- data completeness
- provenance

## IPR

- pair
- current amount
- target amount
- proposed amount
- stage
- review state

## Attachments

- tooth
- type
- reference position
- dimensions
- stage
- review state
- generated state

No fake geometry.

## Appliance/manufacturing boundary

Architecture must support:

- stage model export
- appliance shell generation boundary
- trimline/cutline representation
- shell thickness/material profile
- undercut/engagement checks where supported
- printable model preparation
- manufacturing QC report
- manufacturing versus treatment geometry separation

The system must clearly distinguish:
- treatment design
- geometric validation
- manufacturing preparation
- manufacturing validation

---

# 10 — P6
# ADVANCED PLANNING INTELLIGENCE

**Status: QUEUED**

Only after P3–P5 are stable.

## Model-assisted planning

Potential capabilities:

- landmark-assisted target setup
- arch-form-aware planning
- occlusion-aware planning
- collision-aware candidate generation
- constrained 6-DOF trajectories
- staging proposals
- alternative setups

## Candidate research adapters

- STTAlign
- TADPM
- 3DTeethSAM
- other validated research models discovered through benchmarking

## Rules

Every model output must carry:
- model/version
- input provenance
- confidence/uncertainty where legitimately available
- limitations
- deterministic validation result

AI proposes.

Deterministic geometry validates.

Doctor decides.

No model is allowed to silently bypass validation.

---

# 11 — P7
# PERFORMANCE, RELIABILITY & SCALE

**Status: QUEUED**

## Performance targets

Optimize measured bottlenecks, not guesses.

Potential tools:
- three-mesh-bvh for frontend spatial queries/raycasting
- worker pools
- transferable buffers
- geometry acceleration
- WASM where justified
- Manifold3D where robust solid operations justify it
- caching only where correctness/provenance remains deterministic

## Reliability

- case recovery
- browser refresh
- backend restart
- interrupted processing
- duplicate job protection
- stale job recovery
- large scans
- high mesh density
- repeated edits
- repeated exports

## Performance evidence

Every significant optimization must include:
- before benchmark
- after benchmark
- correctness comparison
- representative real case
- memory/runtime impact

---

# 12 — P8
# WORLD-CLASS QA & RELEASE CANDIDATE

**Status: QUEUED**

## Real-case matrix

- multiple real cases
- upper + lower
- upper only
- lower only
- different orientations
- different mesh densities
- missing data
- ambiguous identity
- processing interruption
- browser refresh
- backend restart
- doctor editing
- undo/redo
- validation
- export
- re-import
- manufacturing handoff

## Engineering gate

Must pass:

- backend tests
- frontend tests
- typecheck
- lint
- build
- browser/E2E
- real artifact tests
- performance benchmarks
- geometry correctness comparisons
- export integrity
- provenance integrity
- model adapter regression
- memory/lifecycle checks

## Clean-machine final acceptance

```text
CLEAN MACHINE
      ↓
CLEAN BROWSER
      ↓
REAL CASE
      ↓
REAL SEGMENTATION
      ↓
ANATOMICAL REVIEW
      ↓
TARGET SETUP
      ↓
STAGING
      ↓
DOCTOR REFINEMENT
      ↓
VALIDATION
      ↓
APPLIANCE / MANUFACTURING OUTPUT
      ↓
EXPORT
      ↓
REOPEN + VERIFY
```

Only after P8 passes:

# PRODUCTION CANDIDATE

---

# 13 — WORLD-CLASS CAPABILITY GATE

Before calling Aligner Studio world-class, all of these must be demonstrated:

1. CAD-grade 3D presentation.
2. Fast, precise tooth interaction.
3. Real segmentation.
4. Stable tooth identity.
5. Tooth landmarks and local axes.
6. Upper/lower arch intelligence.
7. Occlusion representation.
8. Target setup.
9. Doctor-controlled 6-DOF refinement.
10. Dynamic staging.
11. Real contact/proximity/collision validation.
12. IPR.
13. Attachments.
14. Plan versions and audit history.
15. Real-time revalidation after edits.
16. Manufacturing-aware architecture.
17. Reproducible export/re-import.
18. Model-assisted planning behind adapters.
19. Deterministic validation around model outputs.
20. Root/bone-aware pathway when real CBCT/DICOM data exists.
21. Performance suitable for representative real cases.
22. Clean-machine end-to-end acceptance.

The visual layer alone is never sufficient.

---

# 14 — SMART DEPENDENCY POLICY

We will not build from scratch when a high-quality open-source component gives us:

- less implementation
- better performance
- proven algorithms
- mature testing
- commercial-compatible licensing
- clean integration
- replaceability

We will not integrate a library when it creates:

- architecture coupling
- license risk
- opaque clinical behavior
- incompatible data models
- poor performance
- obsolete runtime dependencies
- inability to test/reproduce results

**Default decision: integrate first when the evidence is strong; reinvent only where the product needs proprietary/domain-specific behavior or where integration would be worse.**

---

# 14A — PROFESSIONAL TERMINOLOGY STANDARD

The following terms are the preferred production labels.

| Avoid | Use |
|---|---|
| Case | Case Intake |
| Understand | Analysis |
| Plan | Treatment Setup |
| Review | Staging / Validation / Review Findings depending on context |
| Refine Tools | Refinement |
| Tooth Editor | Tooth Controls / Refinement |
| Generate Plan | Generate Treatment Setup |
| Treatment Proposal | Treatment Setup |
| Stage Review | Staging |
| Review Treatment Proposal | Review Treatment Setup |
| Failed to process | Analysis could not be completed |
| Fixture | Never shown to doctors |
| Experimental | Never shown to doctors unless clinically/research relevant |
| Engineering | Never shown to doctors |
| Demo | Never shown to doctors |
| Treatment plan unavailable | Use the actual production state/action |
| Export | Production / Export Package |
| PASS | Computed / Verified / Requires Review / Not Available |
| Collision Engine | Collision Analysis |
| Movement Vectors | Tooth Movement |
| Target Ghost | Target Position / Target Overlay |
| Fake Gingiva | Visual Gingival Envelope |
| AI Plan | Model-Assisted Treatment Setup, only when genuinely model-generated |

### Language principle

Doctor-facing terminology should describe the dental task, not the implementation.

The interface must never expose:
- fixture
- adapter
- backend
- worker
- deterministic planner
- experimental engine
- internal model name
- engineering state

unless a dedicated technical/diagnostic view is explicitly opened.


# 15 — PHASE DISCIPLINE

A phase may contain:

```text
Phase
 ├── implementation
 ├── open-source/model evaluation
 ├── tests
 ├── benchmarks
 ├── browser acceptance
 ├── evidence
 ├── blockers
 └── acceptance gate
```

Screenshots are evidence.

They are never phases by themselves.

No random feature may be inserted into the active phase without identifying:
- why it belongs there
- what requirement it satisfies
- what architecture it touches
- what tests prove it
- whether it changes a later phase

---

# 16 — STATUS REPORT FORMAT

Every project update must contain:

## CURRENT PHASE
Name + progress.

## PHASE STATUS
PASS / PASS WITH BLOCKER / IN PROGRESS / FAIL.

## COMPLETED
Concrete completed work.

## REMAINING
Concrete remaining work.

## TESTING / ACCEPTANCE
Exact evidence required.

## OVERALL PRODUCTION PROGRESS
P0 → current phase → remaining phases.

## NEXT ALLOWED STEP
One clearly defined next action.

---

# CURRENT STATE

**Active:** P0 — Production Acceptance Closure

**Next:** P1 — Production Visual Foundation

No P1 implementation should begin until P0 closes.

The previous completed engineering history is intentionally NOT part of this new roadmap. It remains project history, not future work.

---

# FINAL PRINCIPLE

Do not ask:

> "Can we make it look like a world-class aligner?"

Ask:

> "Can every layer of the product behave like a professional dental CAD / aligner planning system?"

Visual quality + geometry quality + workflow quality + validation quality + data integrity + performance + manufacturing readiness must converge.

That is the production standard.

# 17 — WORLD-CLASS READINESS SCORECARD

The software must not be called world-class merely because it looks polished.

After implementation, evaluate it using a weighted capability score.

## Scoring model

### A. UI / UX — 20%
- visual hierarchy
- terminology
- workflow coherence
- interaction consistency
- information density
- motion
- loading/progress
- accessibility/usability
- no page-scroll / no duplicated workflows

### B. 3D CAD Interaction — 20%
- rendering quality
- tooth picking
- 6-DOF editing
- camera/navigation
- layers
- target overlays
- measurement interaction
- spatial performance
- lifecycle stability

### C. Treatment Planning — 20%
- tooth identity
- landmarks/local axes
- target setup
- staging
- movement controls
- arch intelligence
- occlusion
- IPR
- attachments
- plan versions
- live revalidation

### D. Validation / Data Integrity — 15%
- collision/contact/proximity correctness
- stage consistency
- provenance
- data completeness
- fail-closed behavior
- export/re-import integrity

### E. Production / Manufacturing — 15%
- appliance stage generation
- trimline/cutline
- shell preparation
- manufacturing QA
- printable outputs
- reports
- production handoff

### F. Performance / Reliability — 10%
- representative real-case runtime
- large mesh interaction
- memory/lifecycle
- restart/recovery
- browser reliability
- repeatability

## Rating interpretation

| Score | Meaning |
|---|---|
| 0–59 | Prototype / incomplete |
| 60–69 | Functional product |
| 70–79 | Professional foundation |
| 80–87 | Strong professional product |
| 88–92 | World-class capability range |
| 93–96 | Highly mature specialist platform |
| 97–100 | Exceptional / benchmark-level maturity |

A score is only awarded from demonstrated evidence, not roadmap promises.

## Expected target after P8

If P1–P8 are implemented to the acceptance standard in this plan, a reasonable **target range** is:

- UI/UX: **88–94**
- 3D CAD interaction: **86–93**
- Treatment planning: **84–92**
- Validation/data integrity: **88–95**
- Production/manufacturing: **80–90**
- Performance/reliability: **85–94**
- Overall: **approximately 86–93**

This is a target, not a guaranteed score.

The upper end requires real-case evidence, mature occlusion/landmark workflows, strong manufacturing preparation, excellent interaction polish, and repeated clean-machine acceptance.

The score should be reassessed after P8 using the actual product, not screenshots.


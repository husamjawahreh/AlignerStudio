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

> **Professional quality + saves implementation time + acceptable/high performance = use it.**

Licensing is NOT a technical selection gate for Aligner Studio when evaluating whether a technology is the right solution for the product. The priority is professional quality, implementation leverage, and acceptable-to-high performance.

Do not reject a library merely because it is external.
Do not reject a technology solely because of licensing during technical selection.
Do not add a library merely because it is popular.

We will still document the source, version, purpose, integration boundary, and provenance of every external technology, and isolate major dependencies behind adapters/interfaces where practical so they remain replaceable.

Do not add a library merely because it is popular.

Every dependency must pass this gate:

```text
Does it solve a real problem?
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
- integration/provenance review

### REFERENCE
Study architecture/algorithms, do not import code.

### REJECT
Do not use because:
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

**Status: IMPLEMENTED (engineering evidence; not clinical/production acceptance)**

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

## 14.1 Selection rule

The default technical rule for Aligner Studio is:

> **Professional quality + saves implementation time + acceptable/high performance = use it.**

When a technology is clearly better for the product on those dimensions, we should prefer using it rather than rebuilding the capability ourselves.

We will actively look for:
- mature open-source libraries
- proven geometry engines
- high-quality 3D interaction libraries
- dental/orthodontic research implementations
- segmentation and landmark models
- manufacturing/CAD algorithms
- performance acceleration technologies
- reliable desktop application frameworks

## 14.2 What Cursor/engineering should do

For every significant external technology:
1. Identify the real product problem it solves.
2. Benchmark or verify it against representative Aligner Studio workloads when practical.
3. Prefer the option that gives professional output with less implementation effort.
4. Prefer acceptable-to-high runtime performance.
5. Integrate it behind a clean boundary when practical.
6. Document source, version, purpose, and integration point.
7. Keep a replacement path for major dependencies where practical.

Licensing is not a technical rejection gate for this project. Any legal/commercial clearance required for actual distribution remains a separate release/legal responsibility, not a reason to unnecessarily reinvent a technically superior component.

## 14.3 Do not reinvent proven infrastructure

We should NOT spend major implementation time rebuilding a mature capability when an external technology can provide a materially more professional result with acceptable performance.

Examples include:
- BVH/spatial acceleration
- robust mesh booleans
- desktop packaging
- GPU/WASM acceleration
- 3D viewport interaction
- mesh processing
- proven segmentation/model inference infrastructure

## 14.4 Do not blindly integrate

A technology should still be rejected or replaced when it causes:
- poor technical fit
- unacceptable performance
- opaque or incorrect clinical behavior
- incompatible data models
- inability to test/reproduce results
- obsolete or unstable runtime dependencies
- severe architecture coupling

**Default decision: use the strongest proven technology when the evidence shows it is more professional, saves meaningful implementation time, and performs at an acceptable-to-high level. Reinvent only where doing so is materially better for Aligner Studio.**

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

---

# 18 — FIRST VERSION
# CROSS-PLATFORM DELIVERABLE

**Status: FINAL DELIVERY PHASE — AFTER P8**

The first deliverable is no longer called a "Demo".

It is officially called:

> **ALIGNER STUDIO — FIRST VERSION**

The purpose of the First Version is to deliver the implemented Aligner Studio product as a usable desktop application that can be installed and tested by the doctor/partner.

The First Version is the first real software release candidate for external testing. It must not be treated as a presentation-only prototype.

## 18.1 Target platforms

The First Version must target:

- **Windows**
- **macOS**
- **Linux**

The exact packaging technology should be selected during implementation based on the strongest combination of:
- professional desktop UX
- maximum reuse of the existing frontend/backend
- installation simplicity
- reliable local processing
- GPU/CPU compatibility
- performance
- crash/recovery behavior
- maintainability
- cross-platform consistency

Do not prematurely lock the packaging framework. Evaluate the best practical option when P7/P8 architecture is mature.

## 18.2 First Version product requirements

The First Version must provide:

### Application
- installable desktop application
- professional application identity/name
- application icon/assets
- version number
- startup/shutdown behavior
- local application data directory
- configuration handling
- clean first launch
- no dependency on Cursor/VS Code
- no developer terminal required for normal doctor use

### Core workflow

```text
LAUNCH
 ↓
CASE INTAKE
 ↓
ANALYSIS
 ↓
SEGMENTATION
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
 ↓
EXPORT
```

The complete workflow must operate from the packaged application using the same production architecture validated through P0–P8.

### Real-case testing

The First Version must include a controlled test package/process for the doctor to load representative cases.

It must support:
- real upper/lower scans
- real segmentation
- case persistence
- target setup
- staging
- doctor refinement
- validation
- production/export
- reopening and verification

No fake clinical data may be used to make the First Version appear complete.

## 18.3 Distribution packages

The release process must produce appropriate packages/installers for:

### Windows
- production installer/package
- clean installation test
- clean launch test
- uninstall/reinstall test
- packaged backend/local services where required

### macOS
- production application/package
- clean installation test
- clean launch test
- application permissions/path validation
- packaged backend/local services where required

### Linux
- production package suitable for the supported distribution target
- clean installation test
- clean launch test
- packaged backend/local services where required

The exact package formats are implementation decisions and must be selected after evaluating the actual application architecture.

## 18.4 Local backend and processing

If the application requires backend processing, the First Version must make this transparent to the doctor.

The doctor must not need to:
- manually run `uvicorn`
- activate Python environments
- set environment variables
- start workers
- manage ports
- configure development paths
- run shell commands

The application must own or reliably launch the required local services/processes.

## 18.5 Offline/local-first expectation

The First Version should be capable of running the core workflow locally where technically possible.

External network access must not be required for ordinary local case processing unless a specific model/service genuinely requires it.

If an external dependency is required:
- show a truthful application state
- handle connection failure
- never silently substitute fake output

## 18.6 GPU / CPU / model packaging

The First Version must define a supported hardware matrix.

At minimum document:
- CPU requirements
- RAM requirements
- GPU requirements if required
- supported GPU backends
- disk requirements
- supported OS versions
- expected processing time ranges
- model/checkpoint requirements
- fallback behavior when hardware is insufficient

Do not promise GPU support that has not been tested.

Do not package research checkpoints blindly.

Model packaging/distribution must be decided per model based on:
- runtime compatibility
- performance
- reproducibility
- storage size
- platform support
- deployment complexity

## 18.7 Doctor-facing installation and onboarding

The First Version must provide:

1. Installer/application package.
2. Version identifier.
3. Short installation instructions.
4. First-launch instructions.
5. Supported hardware/OS requirements.
6. Test-case import instructions.
7. Basic workflow guide.
8. Known limitations.
9. How to report a problem.
10. Safe recovery/restart instructions.

The doctor should be able to start testing without access to the source repository.

## 18.8 First Version acceptance gate

The First Version cannot be released merely because the application builds.

It must pass:

### Build
- Windows build
- macOS build
- Linux build

### Installation
- clean-machine installation
- first launch
- application update/version check where implemented
- uninstall/reinstall

### Workflow
- Case Intake
- Analysis
- Segmentation
- Treatment Setup
- Staging
- Refinement
- Validation
- Production
- Export

### Reliability
- application restart
- backend/process restart where applicable
- browser/app refresh equivalent where applicable
- interrupted processing
- failed processing recovery
- repeated case loading
- repeated export

### Data integrity
- case identity
- semantic tooth identity
- stage integrity
- doctor edits
- validation state
- provenance
- export/re-import

### Real-case acceptance
- multiple real cases
- upper + lower
- different orientations
- representative mesh densities
- missing/ambiguous data
- real segmentation
- real validation
- real export

### Performance
- startup time
- segmentation runtime
- planning runtime
- 3D interaction performance
- memory usage
- export runtime

Every measured performance claim must be backed by actual benchmark evidence.

## 18.9 First Version must NOT expose engineering internals

Doctor-facing application must not expose:

- Fixture
- ToothInstanceNet
- adapter
- backend
- worker
- deterministic planner
- experimental
- engineering
- debug-only terminology
- internal model names
- development paths
- localhost URLs
- terminal commands

Technical diagnostics may exist in a separate controlled diagnostic/reporting mechanism.

## 18.10 First Version documentation

The release package should contain:

```text
FIRST_VERSION/
├── Installer / Application Package
├── README
├── INSTALLATION GUIDE
├── QUICK START
├── SUPPORTED SYSTEMS
├── TEST CASE GUIDE
├── KNOWN LIMITATIONS
├── RELEASE NOTES
└── SUPPORT / ISSUE REPORTING GUIDE
```

## 18.11 What Cursor can and cannot do

### Cursor CAN do

Cursor can implement and prepare most of the engineering required for the First Version, including:

- desktop application integration
- packaging configuration
- Windows/macOS/Linux build configuration
- local backend lifecycle management
- process management
- application startup/shutdown
- installers/package scripts
- icons/assets integration
- configuration management
- model/runtime integration
- application logging
- crash/error handling
- automated tests
- E2E tests
- performance benchmarks
- release scripts
- documentation
- clean-build automation
- CI/release automation where infrastructure is available

### Cursor CANNOT fully replace real-world acceptance

Human/environment-dependent work is still required for:

- physically testing the final installer on each supported OS
- verifying GPU drivers/hardware combinations
- macOS signing/notarization/account setup if distribution requires it
- Windows signing/security reputation workflows if required
- testing Linux packages across the supported distributions
- validating installation permissions and OS-specific behavior on clean machines
- doctor usability testing
- real clinical workflow feedback
- deciding whether the product is acceptable for the doctor's actual workflow
- any regulatory/legal/commercial release decisions

Cursor must therefore prepare the release technically, but the final First Version acceptance requires real clean-machine testing and doctor/partner testing.

## 18.12 First Version release process

```text
P0
 ↓
P1
 ↓
P2
 ↓
P3
 ↓
P4
 ↓
P5
 ↓
P6
 ↓
P7
 ↓
P8
 ↓
FIRST VERSION BUILD
 ↓
WINDOWS PACKAGE
MACOS PACKAGE
LINUX PACKAGE
 ↓
CLEAN-MACHINE INSTALLATION
 ↓
REAL-CASE ACCEPTANCE
 ↓
CROSS-PLATFORM QA
 ↓
DOCTOR TEST PACKAGE
 ↓
FIRST VERSION RELEASE
```

## 18.13 First Version release principle

The First Version is not:

- a screenshot
- a browser-only demo
- a development build
- a mockup
- a deterministic visual simulation
- a fake clinical workflow

It is:

> **The first installable, testable, cross-platform Aligner Studio product delivered for real doctor/partner testing.**

The product may still have explicitly documented limitations, but every implemented capability must be truthful, reproducible, testable, and clearly separated from unsupported clinical claims.

---

# 19 — NEW CHAT HANDOFF / AUTHORITATIVE PROJECT CONTEXT

This section exists so a future project chat can resume without losing the decisions made in this session.

## 19.1 Project

**Project:** Aligner Studio

**Purpose:** Professional 3D clear-aligner / orthodontic planning software.

**Project path:**

`/home/hjawahreh/Desktop/Projects/AlignerStudio`

**Backend:** `http://localhost:8000`

**Frontend:** `http://localhost:5173`

**Real artifact:**

`./official_real_case_stage2_verified_v1.zip`

**Artifact SHA:**

`b0f57d45e19ec1c981964dcad1309570fdc96ec21052ada62050fa3ccb8621b2`

**Current segmentation backend:**

`toothinstancenet_fixture`

**Real artifact evidence:**
- 14 upper tooth instances
- 14 lower tooth instances
- total 28 tooth instances
- real segmentation correspondence has been proven
- FDI must not be invented when unavailable
- semantic-only identity remains valid until genuine clinical identity is supported

## 19.2 Architecture

```text
REAL STL
→ Existing Backend
→ Existing ToothInstanceNet Adapter
→ Orientation + Landmarks
→ Dental Scene Graph
→ TARGET SETUP ENGINE
→ Biomechanical Constraints
→ Macro + Micro Staging
→ Doctor 6-DOF Editor
→ Collision / Contact / IPR / Attachments
→ Validation
→ Export
```

UI workflow:

```text
CASE INTAKE
→ ANALYSIS
→ TREATMENT SETUP
→ STAGING
→ REFINEMENT
→ VALIDATION
→ PRODUCTION
```

Main UI structure:

```text
TOP WORKFLOW HEADER
LEFT CONTEXT / TOOLS / LAYERS
CENTER LARGE 3D CANVAS
RIGHT CONTEXT-SENSITIVE INSPECTOR
BOTTOM STAGE TIMELINE WHEN APPLICABLE
```

No giant one-page dashboard and no page-level scrolling.

## 19.3 Product principles

The product should feel like professional dental CAD software.

Priorities:
- professional 3D presentation
- precise interaction
- truthful processing
- real geometry
- real validation
- editable treatment setup
- dynamic staging
- doctor control
- auditable changes
- reproducible export
- manufacturing-aware architecture
- model-assisted planning only when measurable and explainable

No clinical claims.
No invented FDI.
No fake validation.
No fake geometry.
No engineering terminology exposed to doctors.

## 19.4 Open-source rule — UPDATED

The user's explicit technical rule is:

> **Professional quality + saves implementation time + acceptable/high performance = use it.**

Do not unnecessarily reinvent proven infrastructure.

Open-source/external technologies should be actively considered when they materially improve:
- professional quality
- implementation speed
- performance

Examples already identified:
- Dental-CAD-Designer — reference/selective patterns
- OpenSourceOrtho — architecture reference
- three-mesh-bvh — strong production candidate
- Manifold3D — evaluate/adopt for robust geometry when required
- ToothInstanceNet — current segmentation adapter
- 3DTeethSAM — benchmark candidate
- STTAlign — research adapter/benchmark
- TADPM — research adapter/benchmark
- Slicer Automated Dental Tools / ALI-IOS — orientation/landmark/registration reference
- React Three Fiber / Drei — possible future 3D UX technology only if it materially improves the product and is justified
- other strong technologies may be added when evidence supports them

Every major dependency should still be documented and isolated where practical.

## 19.5 Current phase

**P0 — Production Acceptance Closure**

**Next:** P1 — Production Visual Foundation

P1 must NOT begin until P0 closes.

## 19.6 P0 active blockers

### P0.1 — Two-Arch Correctness
Need to verify:
- upper arch
- lower arch
- transforms
- visibility
- scene composition
- camera/framing
- segmentation layers

Do not assume the lower arch is missing; diagnose the actual root cause.

### P0.2 — Validation Reconciliation
Need to reconcile browser vs benchmark results for:
- collisions
- contacts
- proximity
- stage selection
- mesh states
- semantic identity
- thresholds

Known discrepancy:
- browser acceptance showed 13 collisions / 13 proximity / 13 contacts
- N4.7 real-case benchmark showed collisions 0 for the real raw fixture
- this must be investigated and reconciled, not suppressed.

### P0.3 — Export Integrity
Current known failure involved semantic-only `tooth_number=None` during source/stage and target/final comparison.

Must fix comparison/integrity without inventing FDI.

### P0.4 — Clean Browser Acceptance
After P0.1–P0.3:
- real case end-to-end
- both arches
- validation reconciled
- export succeeds
- exported data auditable

## 19.7 Previous engineering history

The old N-phase roadmap is historical only.

Completed engineering history included:
- persistence
- processing architecture
- truthful progress
- executor recovery
- fixture reconstruction optimization
- geometric validation optimization
- live elapsed time
- structured timing
- real-case benchmark work

Important real-case performance evidence:
- fixture reconstruction improved from roughly 82–84s to roughly 1.5–1.9s per arch
- adjacent-pair geometric validation improved from >300s to roughly 2.45s for the optimized pair operation
- real full pipeline benchmark reached roughly 103.60s
- moved tooth interpolation was exact linear interpolation
- unmoved drift was at floating-point noise level
- fast suite had 144 passed, 1 deselected at that point

Do not reopen completed engineering history unless a current P-phase requirement proves it necessary.

## 19.8 Browser acceptance evidence from previous work

A clean real-case browser run successfully reached:
- Processing 10%
- 82% collision/proximity
- Treatment Setup/Plan area
- Staging
- Refinement/Tooth Editor area
- Validation
- Production/Export area

However, P0 remains open because:
- two-arch presentation still required clean verification
- browser validation counts conflicted with benchmark evidence
- export validation failed for semantic-only identity comparison

Do not declare P0 complete until these are resolved with evidence.

## 19.9 Doctor-facing terminology

Use:

- Case Intake
- Analysis
- Treatment Setup
- Staging
- Refinement
- Validation
- Production
- Tooth Controls
- Review Findings
- Production / Export Package
- Computed
- Verified
- Requires Review
- Not Available

Avoid exposing:
- Fixture
- Experimental
- Engineering
- Backend
- Worker
- Adapter
- deterministic planner
- internal model name
- development terminology

## 19.10 Gingiva rule

If real gingiva exists:
- use real gingiva.

If it does not:
- synthetic gingival envelope may be created in P1.

Synthetic gingiva is presentation-only and must NEVER affect:
- treatment calculations
- measurements
- contacts
- collisions
- proximity
- staging
- clinical validation
- clinical approval

## 19.11 Important safety/architecture rules

Never:
- invent FDI
- replace ToothInstanceNet without measured evidence
- add fake clinical claims
- weaken collision/proximity validation
- use synthetic geometry as anatomical evidence
- use engineering fallback for real cases
- silently substitute fake output
- rewrite treatment mathematics without necessity
- start P1 while P0 is unresolved
- close a phase based only on screenshots or claims

## 19.12 Cursor working protocol

Cursor commands should be:
- one phase/subphase at a time
- explicit about scope
- explicit about forbidden changes
- evidence-driven
- followed by a structured report

After each Cursor report:
1. Review it against this Master Plan.
2. Verify tests/evidence.
3. Only then issue the next command.

Do not give Cursor multiple unrelated implementation commands at once.

## 19.13 First Version final objective

After P8:

**Build and deliver Aligner Studio First Version as an installable application for Windows, macOS, and Linux.**

It must be:
- independent of Cursor/IDE
- installable
- testable
- cross-platform
- real-case capable
- production-architecture based
- documented
- benchmarked
- clean-machine tested

Cursor can implement most of the technical release work, but real OS/hardware installation testing, doctor usability testing, and final external acceptance require real environments/human testers.

## 19.14 Session decision summary

This session established the following final decisions:

1. The authoritative roadmap is **AlignerStudio_PRODUCTION_MASTER_PLAN.md v2.0+**.
2. The active roadmap is **P0–P8**, not the old N-phase roadmap.
3. Current phase is **P0 — Production Acceptance Closure**.
4. Next phase is **P1 — Production Visual Foundation**.
5. Open-source selection rule is:
   **Professional quality + saves implementation time + acceptable/high performance = use it.**
6. The product's first external deliverable is called **First Version**, not Demo.
7. First Version targets **Windows + macOS + Linux**.
8. First Version comes **after P8**.
9. First Version is an actual installable/testable application, not a browser demo.
10. P0 must be fully closed before P1.
11. P0.1/P0.2/P0.3 remain the immediate technical blockers.
12. No invented FDI or unsupported clinical claims.
13. External technologies should be used when they materially improve professional quality, implementation speed, or performance.
14. Major external technologies should remain documented and replaceable where practical.
15. Cursor can prepare most implementation/release engineering, but real cross-platform clean-machine testing and doctor acceptance remain human/environment-dependent.


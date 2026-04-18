# Shadow-mode Autoware ADAS Project Roadmap (3 months)

## 0. Project summary

### Goal
Build a **shadow-mode autonomous driving evaluation platform** that:
- does **not** take over vehicle control,
- estimates virtual steering / acceleration / braking commands,
- compares them against the driver's actual operations,
- visualizes and logs the differences,
- can be demonstrated as a portfolio project for ADAS / autonomous driving / AMR job applications.

### Core concept
This project is **not** a self-driving car implementation for public-road control.
It is a **development and evaluation platform** that generates virtual control outputs and compares them with human driving behavior.

### Constraints
- No actuator takeover
- Low budget
- Prefer laptop / existing hardware / minimal sensors
- Complete a demonstrable version in 3 months

### Positioning for portfolio
This project should be described as:
- an **evaluation platform**,
- a **shadow-mode ADAS prototype**,
- a **planning / control comparison system**,
- a **ROS 2 / Autoware-integrated autonomous driving experiment platform**.

---

## 1. Final deliverable definition

At the end of 3 months, the project should support the following:

### Mandatory deliverables
1. **Sensor input pipeline**
   - Forward camera
   - Vehicle speed / GPS / IMU if available
   - Recorded bag/video replay support

2. **Perception / state estimation (minimal viable)**
   - Lane estimate or lane-center approximation
   - Ego state estimate (speed, yaw, lane offset if possible)
   - Optional lead vehicle detection

3. **Virtual control generation**
   - Virtual steering command
   - Virtual target speed / acceleration / braking demand

4. **Driver vs virtual-control comparison**
   - Steering difference
   - Speed / acceleration difference
   - Predicted path difference
   - Basic safety metrics

5. **Visualization**
   - Overlay or dashboard showing:
     - lane / path
     - virtual command
     - driver command
     - deviation and warning score

6. **Logging / replay / evaluation**
   - rosbag or equivalent replay
   - CSV / JSON metric output
   - reproducible test scenarios

7. **Portfolio materials**
   - GitHub repo
   - architecture diagram
   - short demo video
   - technical write-up

### Nice-to-have deliverables
- Simple lead vehicle following logic
- TTC-like metric
- Danger / intervention suggestion score
- Small HMI with warning indicator
- Autoware module integration for path/control evaluation

---

## 2. Recommended scope

To finish in 3 months, **do not** try to build a full autonomous driving stack.

### Recommended scope to keep
- Shadow mode only
- Camera-first implementation
- Replay-first evaluation
- One road scenario class at first:
  - straight urban roads,
  - low-speed roads,
  - or a fixed repeated route
- Autoware use limited to:
  - planning / path handling / control references,
  - ROS 2 integration,
  - map / trajectory / visualization concepts

### Scope to avoid in the 3-month version
- End-to-end full real-time autonomy on public roads
- Full HD map production
- Sensor fusion with many sensors from day 1
- Heavy object detection optimization
- Perfect localization
- Full legal-compliance feature set

Reason:
The portfolio value comes more from **system design, evaluation methodology, and reproducible improvement** than from trying to copy a production autonomous vehicle stack.

---

## 3. System architecture (recommended)

## 3.1 Inputs
- Forward camera video
- GPS (optional)
- IMU (optional)
- vehicle speed from OBD/CAN read-only if available
- manual driver input proxy if available:
  - steering angle,
  - throttle/brake estimate,
  - or derived motion signal from ego behavior

## 3.2 Processing blocks
1. **Data ingestion node**
2. **Lane / road geometry estimation node**
3. **Ego state estimation node**
4. **Virtual planner / controller node**
5. **Comparison and metrics node**
6. **Visualization / dashboard node**
7. **Logger / replay node**

## 3.3 Outputs
- virtual steering angle command
- virtual speed / deceleration request
- lateral error
- heading error
- driver-vs-virtual command delta
- warning / intervention score
- synchronized logs and demo video

---

## 4. 3-month roadmap

## Month 1: Make the platform observable and replayable

### Objective
Create a data pipeline and a minimal end-to-end shadow-mode skeleton.

### Week 1: Project bootstrap
#### Tasks
- Decide the exact demo story
- Freeze system scope
- Set up repository structure
- Set up ROS 2 workspace
- Decide message formats and logging strategy
- Prepare task board / issue tracker

#### Deliverables
- `README.md` draft
- project architecture diagram
- component list
- milestone tracker

#### Acceptance criteria
- Repository structure is created
- ROS 2 workspace builds
- clear project statement exists

#### Suggested repo structure
```text
project-root/
  docs/
  bags/
  configs/
  scripts/
  src/
    data_ingest/
    lane_estimation/
    ego_state/
    virtual_control/
    metrics/
    dashboard/
  results/
```

---

### Week 2: Data acquisition and replay pipeline
#### Tasks
- Record forward camera data
- Record GPS / IMU / speed if available
- Build timestamp synchronization strategy
- Convert recordings into rosbag or unified replay format
- Verify replay pipeline works

#### Deliverables
- at least 2 recorded scenarios
- replay script
- data format documentation

#### Acceptance criteria
- One recorded drive can be replayed offline end-to-end
- timestamps are stable enough for analysis

#### Notes
If live vehicle data is difficult, start with:
- camera video,
- GPS from smartphone,
- derived speed from video timestamps,
- optional manual annotations.

---

### Week 3: Minimal lane / ego-state estimation
#### Tasks
- Implement lane estimate or lane-center approximation
- Estimate ego heading relative to lane
- Estimate lateral offset proxy
- Create debug visualization

#### Deliverables
- lane overlay video
- ego-state output topic

#### Acceptance criteria
- For selected recordings, the lane estimate is visually stable enough to support a virtual steering proposal

#### Scope advice
A simple classical or lightweight approach is fine.
Do not chase SOTA perception here.

---

### Week 4: Minimal virtual steering generation
#### Tasks
- Implement virtual path from lane centerline
- Implement simple steering controller:
  - Pure Pursuit,
  - Stanley,
  - or a simple geometric controller
- Compare virtual steering output with actual vehicle trajectory / driver behavior
- Build first metric plots

#### Deliverables
- virtual steering output
- steering delta plot
- first demo video

#### Acceptance criteria
- The system can generate virtual steering for replayed data
- steering command and actual motion can be plotted on a shared timeline

---

## Month 2: Make it meaningful as an ADAS evaluation platform

### Objective
Turn the skeleton into an evaluation system with metrics and visual explanations.

### Week 5: Add longitudinal shadow logic
#### Tasks
- Add virtual target speed logic
- Add simple deceleration / braking demand logic
- If lead vehicle detection is not ready, start with rule-based curvature / lane confidence / manual event zones

#### Deliverables
- virtual speed command
- acceleration / brake suggestion output

#### Acceptance criteria
- The system produces both lateral and longitudinal virtual guidance signals

---

### Week 6: Metrics design
#### Tasks
- Define metrics formally
- Implement metric computation
- Add scenario labeling

#### Minimum metrics
- steering delta
- speed delta
- lateral deviation proxy
- heading error
- path disagreement score
- warning score

#### Optional metrics
- TTC-like estimate
- minimum headway estimate
- comfort proxy (jerk / aggressiveness)
- lane departure risk score

#### Deliverables
- metric spec document
- CSV metric outputs
- per-run summary report

#### Acceptance criteria
- A single replay generates a reproducible metric summary

---

### Week 7: Visualization and HMI
#### Tasks
- Build a dashboard or overlay UI showing:
  - camera feed / replay frame
  - lane estimate
  - virtual path
  - driver-vs-virtual steering/speed
  - risk score
- Add event markers for disagreement spikes

#### Deliverables
- dashboard screenshot set
- 1 polished demo clip

#### Acceptance criteria
- A third party can watch the demo and understand what the system is doing without verbal explanation

---

### Week 8: Failure analysis and first improvement loop
#### Tasks
- Select 3 to 5 representative failure cases
- Investigate why disagreement is large
- Improve one subsystem only
  - lane estimate smoothing,
  - controller gain tuning,
  - filtering,
  - event threshold tuning
- Compare before/after

#### Deliverables
- failure case notes
- before/after metrics
- comparison plots

#### Acceptance criteria
- At least one measurable improvement is demonstrated

---

## Month 3: Turn it into a portfolio-grade project

### Objective
Stabilize the system, integrate Autoware-related value, and package the results.

### Week 9: Add Autoware integration where it helps most
#### Tasks
Choose one realistic integration point:
- trajectory / path representation
- control logic comparison
- map / route handling concepts
- ROS 2 interoperability and visualization

#### Recommendation
If resources are limited, do **not** force full-stack Autoware execution.
Instead:
- reuse concepts,
- integrate selected nodes or message flows,
- compare your shadow controller with an Autoware-style path/control pipeline.

#### Deliverables
- documented Autoware integration scope
- architecture update
- one working integration demo

#### Acceptance criteria
- You can clearly explain what part is Autoware-based, what part is custom, and why

---

### Week 10: Safety framing and scenario validation
#### Tasks
- Formalize project limitations
- Document safe test policy
- Create scenario categories:
  - straight road,
  - gentle curve,
  - lane merge-like situation,
  - low-speed stop/go
- Run repeated evaluations

#### Deliverables
- test protocol
- scenario matrix
- safety disclaimer and usage constraints

#### Acceptance criteria
- The project can be presented responsibly as a non-control evaluation platform

---

### Week 11: Portfolio packaging
#### Tasks
- Clean repository
- Improve README
- Add diagrams
- Prepare technical article draft
- Record final demo video
- Export representative plots/images

#### Deliverables
- polished GitHub repo
- 3–5 minute demo video
- architecture diagram
- technical summary article

#### Acceptance criteria
- A recruiter or engineer can understand the project from the repo landing page

---

### Week 12: Interview story and final polish
#### Tasks
- Prepare STAR-style explanations
- Prepare “why shadow mode” explanation
- Prepare “constraints and trade-offs” explanation
- Prepare “next step if given more budget” explanation
- Fix rough edges

#### Deliverables
- interview talking points
- final release tag
- final screenshots and metric tables

#### Acceptance criteria
- You can explain:
  - goal,
  - architecture,
  - trade-offs,
  - failures,
  - improvements,
  - next steps
  in a coherent 5–10 minute walkthrough

---

## 5. Weekly operating rhythm

Use this weekly cycle every week:
1. Define one narrow target
2. Implement the minimum version
3. Run replay on the same 2–3 scenarios
4. Save metrics and screenshots
5. Write a short engineering note
6. Decide whether to improve or freeze

Reason:
Without a fixed evaluation loop, side projects drift into endless tinkering.

---

## 6. Minimal technical stack recommendation

### Hardware
- Existing laptop as primary compute
- Forward camera or dashcam-like camera
- Smartphone GPS/IMU if dedicated sensors are unavailable
- Optional read-only OBD/CAN adapter

### Software
- Ubuntu
- ROS 2
- Python + C++ as needed
- OpenCV
- RViz
- rosbag
- simple plotting tools (Python/matplotlib)
- optional limited Autoware components

### Why this stack
It balances:
- low cost,
- reproducibility,
- ROS 2 relevance,
- demonstrable system integration value.

---

## 7. Metrics definition template

Document these clearly in `docs/metrics.md`.

### Lateral metrics
- lane center offset
- heading error
- virtual steering vs actual steering delta
- path tracking disagreement

### Longitudinal metrics
- target speed vs actual speed delta
- acceleration disagreement
- braking demand disagreement

### Safety-oriented metrics
- warning score
- lane departure risk proxy
- TTC-like estimate if possible
- minimum stopping margin estimate if possible

### Comfort-oriented metrics
- steering smoothness proxy
- jerk proxy
- oscillation / instability count

### Portfolio rule
Every metric should answer one of these:
- Is the system behaving reasonably?
- When does it disagree with the driver?
- Is the disagreement safety-relevant?
- Did an improvement reduce the problem?

---

## 8. GitHub portfolio checklist

Your repo should include:

### Top-level README
- project summary
- motivation
- system diagram
- hardware list
- software stack
- quickstart
- demo GIF/video link
- results summary
- limitations

### Docs folder
- architecture
- data collection method
- safety policy
- metrics definition
- scenario description
- future work

### Evidence assets
- screenshots
- plots
- bag replay examples
- before/after comparison

### Strong recruiter-facing points
- low-cost engineering under constraints
- ROS 2 integration
- evaluation-driven development
- autonomous driving concepts without unsafe control takeover
- measurable improvement cycle

---

## 9. What to say in interviews

### One-sentence summary
“I built a shadow-mode ADAS/autonomous-driving evaluation platform that generated virtual steering and speed commands, compared them with human driving, and quantified disagreement and safety-relevant events using replayable ROS 2 pipelines.”

### Key engineering points
- I deliberately avoided actuator takeover for safety and scope control.
- I focused on evaluation, observability, and reproducibility.
- I used replay and metrics rather than subjective demo-only claims.
- I integrated autonomous-driving concepts under tight hardware constraints.
- I improved the system through failure analysis and before/after comparisons.

### Strong discussion topics
- Why shadow mode is valuable
- Trade-offs under low compute budget
- How metrics were chosen
- What failed first
- What would be upgraded with more hardware

---

## 10. Stretch goals after 3 months

Only attempt these after the MVP works:
- better lead vehicle detection
- map-based route context
- stronger controller (e.g. MPC-like comparison)
- limited real-time optimization
- AMR variant using the same shadow-evaluation architecture
- simulator integration for closed-loop comparison

---

## 11. Risks and mitigations

### Risk 1: perception consumes all available time
**Mitigation:**
Use a simple lane estimate and invest effort in evaluation/metrics instead.

### Risk 2: hardware is too weak for real-time
**Mitigation:**
Use replay-first architecture and make offline evaluation the primary success path.

### Risk 3: no actual steering angle data
**Mitigation:**
Compare virtual control against trajectory-derived motion or heading behavior instead.

### Risk 4: project looks like a toy demo
**Mitigation:**
Emphasize architecture, metrics, failure analysis, and before/after improvement.

### Risk 5: Autoware integration becomes too heavy
**Mitigation:**
Integrate selected concepts/modules only, and document the boundaries clearly.

---

## 12. Concrete 3-month success criteria

This project is successful if, by the end of 3 months, you can show:

1. A replayable ROS 2 pipeline
2. Virtual steering and longitudinal suggestions
3. Driver-vs-system difference visualization
4. At least 5 defined metrics
5. At least 3 scenario categories
6. At least 1 before/after improvement result
7. A clean GitHub repo with diagrams and demo video
8. A clear explanation of design trade-offs and next steps

If all 8 are achieved, this is already a strong portfolio project.

---

## 13. Recommended next files to create

Create these files next:

```text
docs/architecture.md
docs/metrics.md
docs/safety_policy.md
docs/scenarios.md
docs/interview_notes.md
README.md
```

### Suggested order
1. `README.md`
2. `docs/architecture.md`
3. `docs/metrics.md`
4. `docs/scenarios.md`
5. `docs/safety_policy.md`

---

## 14. Suggested implementation order (very important)

Do things in this order:

1. Replay pipeline
2. Lane/state estimation
3. Virtual steering
4. Dashboard
5. Longitudinal logic
6. Metrics
7. Improvement cycle
8. Autoware integration
9. Portfolio cleanup

Do **not** start with full Autoware integration.
Do **not** start with fancy perception.
Do **not** delay visualization and logging.

---

## 15. Final recommendation

The best framing for this project is:

> **Shadow-mode autonomous driving evaluation platform using ROS 2 and selected Autoware concepts/components**

That framing is strong because it shows:
- autonomous driving knowledge,
- realistic scope control,
- safety awareness,
- measurable engineering practice,
- and clear extensibility toward AMR or ADAS products.


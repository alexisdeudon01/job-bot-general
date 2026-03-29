# Dashboard inspection report

## Files reviewed
- `dashboard/app.py`
- `dashboard/Dockerfile`
- `dashboard/requirements.txt`
- `docker-compose.yml`
- `analyzer/main.py`
- `generator/main.py`
- `README.md`

## Dashboard diagnosis

### `dashboard/app.py`
Current dashboard is only a minimal Streamlit UI:
- title
- job URL input
- CV uploader
- two buttons showing informational messages only

It does not launch the batch containers, does not read shared result files, and does not persist the uploaded CV.

### Relation with analyzer/generator
The current architecture is file-based through shared mounted volumes:
- analyzer produces a JSON analysis artifact in the shared output volume
- generator consumes the analysis artifact and the CV from the shared data/output volumes
- dashboard mounts the same shared directories but currently does not consume them

So the dashboard is not coupled to existing batch outputs today.

## Container lifecycle diagnosis

### analyzer
`analyzer/main.py` behaves like a one-shot batch job:
- without `JOB_URL`, it exits cleanly with code 0
- with `JOB_URL`, it runs once, writes its result, then exits

### generator
`generator/main.py` also behaves like a one-shot batch job:
- it expects analyzer output and the CV input
- it runs once, writes its result, then exits

### Consequence
If only `dashboard` remains visible in `docker ps`, that is consistent with analyzer/generator being short-lived jobs rather than persistent services.

To distinguish normal completion from failure, check:
- `docker compose ps -a`
- `docker compose logs analyzer`
- `docker compose logs generator`

If exit code is 0, the behavior is expected.

## Compose structure diagnosis
`docker-compose.yml` currently presents all three entries as standard services, but they have different lifecycles:
- `dashboard`: long-running server
- `analyzer`: batch job
- `generator`: batch job

That mismatch is likely the source of confusion.

## Concrete recommendations

### 1. Clarify expected behavior
At minimum, document that analyzer and generator are one-shot jobs and are expected to stop after completion.

### 2. Use Compose profiles
Recommended parent change:
- put `analyzer` and `generator` in a `batch` profile
- keep `dashboard` as the main UI service

That makes the lifecycle explicit and avoids interpreting completed jobs as broken containers.

### 3. Decouple dashboard startup from batch jobs
Current `dashboard` depends on `generator`, and `generator` depends on `analyzer`.
This is misleading if dashboard is only a UI/viewer.

Recommended parent change:
- remove `depends_on` from `dashboard`
- let dashboard start independently
- have the UI show that no analysis/generation is available yet when outputs are absent

### 4. Improve dashboard later if desired
If stronger integration is wanted, `dashboard/app.py` could later be extended to:
- save the uploaded CV into the shared data volume
- detect whether analyzer output exists
- detect whether generator output exists
- display friendly statuses and next steps

## Final conclusion
- Dashboard is not the reason analyzer/generator stop.
- Dashboard does not currently require batch outputs to exist.
- Analyzer and generator appear intentionally designed as one-shot containers.
- The main problem is likely Compose UX/structure, not a dashboard bug.
- Best recommendation: separate long-running UI from batch jobs using Compose profiles and clearer docs.
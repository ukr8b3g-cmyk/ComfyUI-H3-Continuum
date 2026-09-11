# Issue #20: workflow persistence test branch

**Candidate only:** `test/issue-20-workflow-persistence`.
The maintainer cannot reproduce the complete Model/VAE/LoRA reset on the maintainer's system. Passing the automated tests below does not establish that the reporter's problem is fixed. Do not promote this branch to main until browser testing and the required completion review have finished.

## Scope

Only `web/project_id.js` changes runtime behavior. Serialization no longer temporarily removes/reinserts live widgets; unchanged widget order is not rewritten; obsolete deferred setup is ignored; First Image geometry is read from the owning graph rather than another active tab. Existing widget names/order, public node schemas, Sampling, Audio, Review Queue and Run Storage are unchanged. The branch does not edit other loaders' selections, force global workflow persistence settings, disable canvas repaint, or delete saved Takes. Tests/support code, this document, status notes and touched manifest hashes accompany that runtime change.

This is not a fix for old corrupted workflow files, unrelated memory errors, Spectrum incompatibility or Reference Audio/Second Pass issues.

## Existing Git installation

Save/export a separate copy of your workflow, then stop ComfyUI. Open a terminal **inside the Continuum custom-node folder**, not the main ComfyUI repository. Run the following checks:

```text
git rev-parse --show-toplevel
git remote -v
git status --short
git branch --show-current
git rev-parse --short HEAD
```

The root must be the Continuum folder and `origin` must point to `ukr8b3g-cmyk/ComfyUI-H3-Continuum`. Record the current branch and commit for rollback. If there are local changes, stop and preserve them before switching. Do not force checkout/reset or discard them. Stop if any command below fails.

For the **first** test-branch checkout:

```text
git fetch origin test/issue-20-workflow-persistence
git switch -c test/issue-20-workflow-persistence FETCH_HEAD
git branch --show-current
git rev-parse --short HEAD
```

The explicit fetch also works for installations originally cloned with a single-branch refspec. This creates a local test branch without changing main. A plain `git pull` on main does not select the candidate.

When the local test branch already exists, switch to it and update it explicitly instead:

```text
git switch test/issue-20-workflow-persistence
git pull --ff-only origin test/issue-20-workflow-persistence
```

Restart ComfyUI and hard-refresh its page (Ctrl+F5 on Windows). Keep the ComfyUI/frontend versions and other extensions unchanged during this comparison.

## ZIP/Manager installation without its own Git repository

Stop ComfyUI. Move the existing Continuum folder to a backup location **outside every ComfyUI `custom_nodes` directory**. Do not merely rename it within `custom_nodes`; that can load duplicate node definitions. Keep the backup and do not delete workflows, models, outputs or saved Takes.

From the `custom_nodes` parent directory, with the destination folder absent:

```text
git clone --branch test/issue-20-workflow-persistence --single-branch https://github.com/ukr8b3g-cmyk/ComfyUI-H3-Continuum.git ComfyUI-H3-Continuum
cd ComfyUI-H3-Continuum
git branch --show-current
git rev-parse --short HEAD
```

Restart ComfyUI and hard-refresh the page. Only one active Continuum installation should be present.

## Browser test (no generation required)

1. Open a separate copy of the workflow that reproduced the reset. Change Model, Video VAE, Audio VAE and LoRA selections, plus a few sampler settings. Keep prompts/media otherwise unchanged.
2. Save it and export `before-switch.json`.
3. Switch to another **workflow tab inside ComfyUI**, then return. Repeat several times, including a quick tab round-trip.
4. Check the actual selected values, not only the unsaved `*` indicator. Export `after-switch.json` before manually correcting any reset.
5. Reload the page and reopen the saved workflow. Check the values again.

Please report the test-branch commit, ComfyUI version, **frontend version**, browser/version and whether values stay stable. If it still fails, share both exported JSON files and any browser-console errors. Inspect/redact private prompts, media names, paths or credentials before posting publicly. Note whether values revert to old valid selections or appear in the wrong fields (such as Render History text in Height). These may be different failure paths.

## Rollback

Stop ComfyUI first. For an existing Git checkout, check `git status --short`, preserve any new local changes, and switch back to the branch recorded earlier (usually `main`):

```text
git switch main
```

Use the recorded branch rather than `main` if different. For the fresh-clone method, move the test installation outside `custom_nodes` and restore the backed-up original folder. Restart ComfyUI and hard-refresh again. Neither rollback requires deleting saved Takes.

## Automated validation and limits

```text
node tests/frontend_review_queue.cjs
node tests/frontend_issue20_persistence.cjs
python -m pytest -q -p no:cacheprovider
```

The existing fixture retains 46 cases. The new fixture adds nine modeled scenarios covering read-only serialization, indexed/compact save formats, exception cleanup, idempotent ordering, detached deferred callbacks, owner-graph resolution, active setup and sibling-loader preservation. Against the original runtime, seven of those nine fail; against the candidate, all nine pass. This is evidence for these individual code paths, not reproduction of the reporter's whole UI problem.

Full CPU baseline/candidate comparisons retain the same 20 existing failures for missing workflow assets; the candidate adds one passing pytest gate. Those distribution failures are not repaired in this narrowly scoped branch. Exact results and snapshots are in the isolated Issue20 validation run; status is also recorded in PROJECT_STATE.md and WORKLOG.md. No real ComfyUI browser or GPU run was performed by this automation. Required H3情報チェック cross-task review remains pending because that destination was unavailable in this session.

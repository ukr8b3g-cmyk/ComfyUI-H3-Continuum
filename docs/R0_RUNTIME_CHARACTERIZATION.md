# Runtime Redesign R0 Characterization

Date: 2026-09-14 (Asia/Tokyo)  
Phase: R0 only  
Architecture changes: none

## 1. Historical baseline

この文書は2026-09-14時点のR0 CPU characterizationです。現行3.9.1の受入結果ではありません。当時の実装・Workflow・既存変更を保持した状態で調査し、アーキテクチャ変更やGPU生成は行っていません。

## 2. Baseline validation

R0変更前:

```text
full CPU pytest: 1187 passed, 1 skipped, 1 warning, 62.18 s
frontend_review_queue.cjs: 46 passed
tools/verify_runtime.py: PASS
registered public nodes: 7
```

実ComfyUI Queue、GPU、VAE DecodeはR0の対象外であり未実行。

## 3. Continuation source baseline

### 3.1 Storage OFF

| Inputs | Accepted prefix | Effective generation start | Continuation state | Current result |
|---|---:|---:|---|---|
| none | 0 | Chunk 1 | none | fresh Full Run |
| compatible explicit Session with 1 accepted chunk | 1 | Chunk 2 | last accepted Session entry | prefix reuse |
| Session + `Regenerate From = 2` | 1 | Chunk 2 | Session Chunk 1 | Chunk 2以降を再生成 |
| incompatible explicit Session | 0 | Chunk 1 | none | Sessionをadvisory rejectしてfresh run |
| initial State only | 0 | logical Chunk 1 | supplied State | generated plan is continuation and increments State `clip_index` |
| compatible Session + valid State | Session prefix | prefix後 | Session last entry | StateはSession検証前に抑止 |
| invalid Session + valid State | 0 | Chunk 1 | none | Stateへfallbackせずfresh run |
| initial State + invalid `Regenerate From > 1` | n/a | n/a | n/a | `SequenceRuntimeError` |

重要なV9との差分: 現在の`_preserved_prefix()`はSession validation、resolution、duration、identity不一致を例外として外へ出さず、noteを付けて空prefixを返す。このため、V9の「invalid/incompatible Sessionなら既存Sessionエラー」は現行実装の事実ではない。

実際の現行結果は次である。

```text
Session present + initial State present
→ initial State = None
→ Sessionを検証
→ Session invalid/incompatibleならSession prefixを0件へ落とす
→ initial Stateには戻らない
→ fresh Chunk 1を生成
→ reportへ "saved session was ignored; generated a fresh run (...)"
```

したがってR1以降で維持すべきbaselineは、ユーザーが別途変更を承認しない限り「no State fallback + advisory fresh run」である。

Storage OFF characterizationでは、Run Storage Review policy invocationは0、Run Storage filesystem I/Oは0だった。

### 3.2 Run Storage ON

| Inputs / saved state | Current result |
|---|---|
| explicit Session present | `RunStorageError: Run Storage cannot be combined with an explicit Session`。storage書込前に停止 |
| validated saved prefix + initial State | saved prefixが優先。Stateはcontinuation sourceにならない |
| no saved prefix + initial State | initial Stateを使用 |
| Review Continue | review decisionを作成後、prefix実読込後にreconcileして再度decisionを作成 |

現在のReview Continue decision-producing pathを隔離すると、pure policy callは2回だった。

```text
_resolve_review_contract()
→ resolve_review_execution()       # first decision
→ prefix selection/load
→ _reconcile_review_execution_with_reused_prefix()
→ resolve_review_execution()       # second decision
```

`_validated_review_head()`も同じpure functionをmetadata validationに使用するが、その戻り値はQueue decisionではない。R2の「Decision 1回」は上記decision-producing 2経路を1経路にする課題であり、R0では変更していない。

## 4. ContinuationSourceFacts mapping baseline

この型とprojection関数はR0時点のsource treeには存在しない。R3/R4で新しい意味を作らないため、現行runtime値からのmappingを次で固定する。

| selected kind | `accepted_chunks` | `reroll_from_chunk` | `physical_group_boundaries` |
|---|---:|---|---|
| `run_storage` | 実際にraw検証とloadを通過した`best_entries`数 | final branch contractの有効boundary。通常continueは0 | accepted prefix内で完全に成立した現行physical groups |
| `explicit_session` | `_preserved_prefix()`が受理したentries数 | explicit Session経路の実効`reroll_from_chunk` | terminal atomicity適用後、accepted prefix内で完全に成立したgroups |
| `initial_state` | 0 | 0または現行で許可される1 | empty tuple |
| `none` | 0 | 0（plain Full Run baseline） | empty tuple |

`initial_state`はaccepted raw prefixではない。logical Chunk 1のSamplingにcontinuation stateを供給するだけである。

## 5. Current validated-prefix representation

R0 source treeには`ValidatedPrefix`、`EmptyValidatedPrefix`、`PrefixFacts`、`ContinuationSourceFacts`、`to_planning_facts()`はまだ存在しない。現在は次のmutable valuesへ分散している。

- `review_head`: `revision_id`, `status`, `validated_prefix_count`, `review_unit`, `branch_regenerate_from`, `effective_reroll_nonce`, `updated_utc`, `manifest`
- `best_entries`: raw existence、SHA-256、entry contractを通過して実際にloadされたentries
- `best_records`: accepted entriesに対応するmanifest records
- `RunStorageController.reused_count`: `len(best_entries)`
- `RunStorageController.review_execution`: prefix load前decisionを、load後reconcileで置換した値

よってV9の`ValidatedPrefix.to_planning_facts() -> PrefixFacts`は「現行契約」ではなく、R2で導入する将来契約である。R0でその型を追加するとR1/R2実装へ先行するため、追加していない。R2で導入する場合も戻り型を`ContinuationSourceFacts`へ流用しない。

## 6. ReviewUnit inventory

Productionの`ReviewUnit`定義は1種類だけである。

```text
v3/review_control.py
  class ReviewUnit(start, end, physical_group)
```

Production usage:

- `v3/review_control.py`: unit作成、normalization、pause metadata、Review/Take policy
- `run_storage.py`: import、review group marker、pause metadata validation、finalize validation
- `v3/nodes.py`: `review_execution`からprojection rangeを読む。別`ReviewUnit`型は定義しない

R0検索では別の`class ReviewUnit`は存在しなかった。

## 7. Required behavior coverage map

新しいR0 testは`tests/test_runtime_redesign_r0_characterization.py`に隔離した。既存fixtureと合わせた代表coverageは次の通り。

| Contract | Characterization coverage |
|---|---|
| Review Q1 → next → complete | `test_limit_one_returns_one_new_chunk_and_prefix_assembly`, `test_prefix_five_generates_only_chunk_six_and_completes`, L0/L1 storage tests |
| Regenerate Current | N0-N5 and terminal regenerate tests in `test_v38_review_run_storage.py` |
| Finish Remaining | `test_n5_finish_remaining_keeps_current_branch_nonce`, `test_finish_remaining_complete_records_the_final_generated_group` |
| Use This Take / Continue From Here | N2B take-selection, canonical, and continue tests |
| Back to Settings compatible extension | `test_i2va_two_to_three_reuses_both_canonical_prefix_chunks` |
| terminal physical group | terminal atomic tests in execution-cap and Run Storage suites |
| Session/State precedence | new R0 characterization tests |
| Balanced 22 / Strong 39 | new parametrized R0 characterization test |
| Reference Image / Audio and Refine Context | `test_audit_boundary_repairs.py`, `test_v35_context_sampler.py` |
| Video Reference | `test_p46a_reference_video_memory.py` and sequence contract tests |
| Timeline Video | `test_timeline_video.py` |
| Driving Audio | `test_v34_driving_audio.py` |
| Second Pass | `test_v35_second_pass_contract.py`, `test_v35_second_pass_sampling.py`, selective node tests |
| external wrappers | graph-contract Turbo/Sage tests and `test_model_patch.py` |

## 8. Hardening signature baseline

`hardening.run_sequence_with_hardening()` calls `inspect.signature(base).bind_partial(...)`. The current keyword-only `run_sequence` signature contains 41 parameters, in this order:

```text
model
clip
video_vae
audio_vae
sampler
sigmas
first_frame
last_frame
prompt_plan
width
height
continuity
base_seed
audio_continuity
exact_total_duration
diagnostics_mode
reroll_from_chunk
reroll_nonce
strict_compatibility
debug
seam_correction
enable_preview
session
initial_state
latent_only
reference_assets
reference_audio_source
reference_audio_vae
driving_audio_source
driving_audio_vae
reference_video_source
timeline_video_source
guide_source
capture_refine_context
memory_attribution
prompt_conditioning_cache
reference_encode_cache
continuation_transport
max_new_physical_groups
_memory_attribution_collector
_diagnostic_continuation_policy
```

R4 thin adapterはこの名前・keyword-only形・defaultsを維持する必要がある。

## 9. R1 concrete plan (not implemented)

R1はProjectionだけに限定する。

1. 現在`v3/nodes.py`にある`_review_decode_chunk_range()`の判断を、torch/ComfyUI非依存のpure `ProjectionDecision`へ写す。
2. `full_accepted_prefix`と`current_review_unit(start,end)`だけを表現する。
3. 現在の`_apply_review_decode_scope()`のTensor/Assembly再構築をOutput Projectorの単一ownerへ移す。
4. Session、full Refine Context、Run Storage recordsは切り詰めず、表示用Video/Audio latentとAssemblyだけを同じrangeで投影する。
5. terminal merged unitは既存physical group境界に従い分割しない。
6. Full Run、Finish Remaining、complete、Use This Takeは現行どおりfull projectionを維持する。
7. focused parity、full CPU、frontend、manifest、workflow SHA/ZIP parity、public schemaをGateにする。

R1ではReview policy、prefix探索、Session/State priority、Sampling、commit/finalizeを変更しない。R1実装は明示承認までHOLD。

## 10. R0 disposition

R0 Characterizationの実装対象はtest/documentationだけで、Production runtimeは変更していない。

R1へ進む前の要確認事項:

1. V9の「invalid/incompatible Sessionは既存エラー」を、実コードの「advisory reject + fresh run」へ訂正するか。
2. `ValidatedPrefix.to_planning_facts()`を現行契約ではなくR2導入契約として扱うか。

この2点を未訂正のままR2/R4へ進むと、現行挙動維持とV9本文を同時に満たせない。


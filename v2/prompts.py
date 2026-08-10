"""Prompt planning for the integrated H3 Continuum sampler.

The parser is intentionally deterministic and side-effect free so saved workflows
can be reproduced without depending on UI state.
"""
from __future__ import annotations
import hashlib, json, re
from typing import Any
from ..constants import (
    PROMPT_FORMAT_AUTO,PROMPT_FORMAT_FIXED,PROMPT_FORMAT_LIST,PROMPT_FORMAT_TIMELINE,
    PROMPT_MODE_FIXED,PROMPT_MODE_LIST,PROMPT_MODE_TIMELINE,PROMPT_PLAN_MAGIC,
)
from ..version import PROMPT_PLAN_SCHEMA_VERSION
_TIMELINE_HEADER=re.compile(r"^\s*\[\s*(?P<start>\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*[-–—]\s*(?P<end>\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*\]\s*$",re.IGNORECASE)
_CHUNK_HEADER=re.compile(r"^\s*\[\s*(?:chunk|clip)\s*(?P<index>\d+)\s*\]\s*$",re.IGNORECASE)
_LIST_SEPARATOR=re.compile(r"^\s*---+\s*$",re.MULTILINE)
class PromptPlanError(ValueError): pass
def prompt_hash(prompt:str)->str: return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
def _normalize_prompt(value:str,*,label:str)->str:
    text=str(value).strip()
    if not text: raise PromptPlanError(f"{label} is empty")
    return text
def _parse_json_list(script:str):
    stripped=script.lstrip()
    if not stripped.startswith("["): return None
    try: value=json.loads(script)
    except json.JSONDecodeError: return None
    if not isinstance(value,list) or not all(isinstance(item,str) for item in value): raise PromptPlanError("JSON prompt list must be an array of strings")
    return [_normalize_prompt(item,label=f"prompt {index+1}") for index,item in enumerate(value)]
def _parse_list(script,chunks):
    values=_parse_json_list(script)
    if values is None: values=[_normalize_prompt(part,label=f"prompt {index+1}") for index,part in enumerate(_LIST_SEPARATOR.split(script)) if part.strip()]
    if not values: raise PromptPlanError("prompt list contains no prompts")
    notes=[]
    if len(values)<chunks: notes.append(f"repeated the last prompt for {chunks-len(values)} chunk(s)"); values.extend([values[-1]]*(chunks-len(values)))
    elif len(values)>chunks: notes.append(f"ignored {len(values)-chunks} extra prompt(s)"); values=values[:chunks]
    return values,notes
def _parse_timeline_sections(script):
    sections=[]; current=None; body=[]
    def finish():
        nonlocal current,body
        if current is None:
            if any(line.strip() for line in body): raise PromptPlanError("timeline text before the first [0-5s] or [Chunk 1] header is not allowed")
            body=[]; return
        current["prompt"]=_normalize_prompt("\n".join(body),label="timeline section"); sections.append(current); current=None; body=[]
    for line in str(script).splitlines():
        time_match=_TIMELINE_HEADER.match(line); chunk_match=_CHUNK_HEADER.match(line)
        if time_match or chunk_match:
            finish()
            if time_match:
                start=float(time_match.group("start")); end=float(time_match.group("end"))
                if not end>start: raise PromptPlanError(f"timeline range must increase: {line.strip()}")
                current={"kind":"time","start":start,"end":end}
            else:
                index=int(chunk_match.group("index"))
                if index<1: raise PromptPlanError("chunk numbers are one-based")
                current={"kind":"chunk","index":index}
            continue
        body.append(line)
    finish()
    if not sections: raise PromptPlanError("timeline contains no sections")
    return sections
def _parse_timeline(script,chunks,chunk_seconds):
    sections=_parse_timeline_sections(script); prompts=[]; notes=[]
    for chunk_index in range(1,chunks+1):
        chunk_sections=[item for item in sections if item["kind"]=="chunk" and item["index"]==chunk_index]
        if len(chunk_sections)>1: raise PromptPlanError(f"timeline defines Chunk {chunk_index} more than once")
        if chunk_sections: prompts.append(chunk_sections[0]["prompt"]); continue
        start=(chunk_index-1)*chunk_seconds; end=chunk_index*chunk_seconds; scored=[]
        for order,item in enumerate(sections):
            if item["kind"]!="time": continue
            overlap=max(0.0,min(end,item["end"])-max(start,item["start"]))
            if overlap>0: scored.append((overlap,-order,item))
        if not scored: raise PromptPlanError(f"timeline does not cover chunk {chunk_index} ({start:.3f}-{end:.3f}s)")
        scored.sort(reverse=True,key=lambda row:(row[0],row[1])); prompts.append(scored[0][2]["prompt"])
        if len(scored)>1 and abs(scored[0][0]-scored[1][0])<1e-9: notes.append(f"chunk {chunk_index} had an equal-overlap timeline tie; used the earlier section")
    return prompts,notes
def detect_prompt_mode(script):
    text=str(script)
    for line in text.splitlines():
        if _TIMELINE_HEADER.match(line) or _CHUNK_HEADER.match(line): return PROMPT_MODE_TIMELINE
    if _parse_json_list(text) is not None or _LIST_SEPARATOR.search(text): return PROMPT_MODE_LIST
    return PROMPT_MODE_FIXED
def resolve_prompt_mode(mode,script):
    explicit={PROMPT_FORMAT_FIXED:PROMPT_MODE_FIXED,PROMPT_FORMAT_LIST:PROMPT_MODE_LIST,PROMPT_FORMAT_TIMELINE:PROMPT_MODE_TIMELINE}
    if mode==PROMPT_FORMAT_AUTO: return detect_prompt_mode(script)
    if mode in explicit: return explicit[mode]
    if mode in (PROMPT_MODE_FIXED,PROMPT_MODE_LIST,PROMPT_MODE_TIMELINE): return mode
    raise PromptPlanError(f"unknown prompt format: {mode!r}")
def make_prompt_plan(*,mode,script,chunks,chunk_seconds):
    chunks=int(chunks); chunk_seconds=float(chunk_seconds)
    if not 1<=chunks<=16: raise PromptPlanError("chunks must be between 1 and 16")
    if not 4.0<=chunk_seconds<=15.0: raise PromptPlanError("chunk_seconds must be between 4.0 and 15.0 for native H3")
    resolved_mode=resolve_prompt_mode(mode,script); notes=[]
    if mode==PROMPT_FORMAT_AUTO:
        detected={PROMPT_MODE_FIXED:PROMPT_FORMAT_FIXED,PROMPT_MODE_LIST:PROMPT_FORMAT_LIST,PROMPT_MODE_TIMELINE:PROMPT_FORMAT_TIMELINE}[resolved_mode]; notes.append(f"Auto detected {detected}")
    if resolved_mode==PROMPT_MODE_FIXED: prompt=_normalize_prompt(script,label="fixed prompt"); prompts=[prompt]*chunks
    elif resolved_mode==PROMPT_MODE_LIST: prompts,parse_notes=_parse_list(script,chunks); notes.extend(parse_notes)
    elif resolved_mode==PROMPT_MODE_TIMELINE: prompts,parse_notes=_parse_timeline(script,chunks,chunk_seconds); notes.extend(parse_notes)
    else: raise PromptPlanError(f"unknown prompt mode: {resolved_mode!r}")
    return {"magic":PROMPT_PLAN_MAGIC,"schema_version":PROMPT_PLAN_SCHEMA_VERSION,"mode":resolved_mode,"chunks":chunks,"chunk_seconds":chunk_seconds,"prompts":prompts,"hashes":[prompt_hash(p) for p in prompts],"notes":notes}
def validate_prompt_plan(plan):
    if not isinstance(plan,dict) or plan.get("magic")!=PROMPT_PLAN_MAGIC: raise PromptPlanError("invalid H3 Continuum prompt plan")
    if int(plan.get("schema_version",-1))!=PROMPT_PLAN_SCHEMA_VERSION: raise PromptPlanError(f"unsupported prompt-plan schema {plan.get('schema_version')}; expected {PROMPT_PLAN_SCHEMA_VERSION}")
    chunks=int(plan.get("chunks",0)); prompts=plan.get("prompts"); hashes=plan.get("hashes")
    if not 1<=chunks<=16: raise PromptPlanError("prompt-plan chunks are invalid")
    if not isinstance(prompts,list) or len(prompts)!=chunks: raise PromptPlanError("prompt-plan prompt count does not match chunks")
    if not isinstance(hashes,list) or len(hashes)!=chunks: raise PromptPlanError("prompt-plan hash count does not match chunks")
    for index,prompt in enumerate(prompts):
        _normalize_prompt(prompt,label=f"prompt {index+1}")
        if hashes[index]!=prompt_hash(prompt): raise PromptPlanError(f"prompt-plan hash mismatch at chunk {index+1}")
    return plan
def build_sampler_prompt_plan(*,prompt_mode,prompt_script,sequence_prompt,prompt_plan,chunks,chunk_seconds):
    chunks=int(chunks); chunk_seconds=float(chunk_seconds)
    if sequence_prompt is not None: return make_prompt_plan(mode=prompt_mode,script=sequence_prompt,chunks=chunks,chunk_seconds=chunk_seconds)
    if prompt_plan is not None:
        plan=validate_prompt_plan(prompt_plan)
        if int(plan["chunks"])!=chunks: raise PromptPlanError("connected prompt_plan chunks do not match the Sampler chunks widget")
        if abs(float(plan["chunk_seconds"])-chunk_seconds)>1e-6: raise PromptPlanError("connected prompt_plan chunk_seconds do not match the Sampler widget")
        return plan
    return make_prompt_plan(mode=prompt_mode,script=prompt_script,chunks=chunks,chunk_seconds=chunk_seconds)
def apply_prompt_overrides(plan,overrides):
    plan=validate_prompt_plan(plan); prompts=list(plan["prompts"]); replaced=[]
    for index,value in enumerate(overrides[:int(plan["chunks"])]):
        if value is None: continue
        prompts[index]=_normalize_prompt(value,label=f"Clip {index+1} Prompt"); replaced.append(index+1)
    if not replaced: return plan
    result=dict(plan); result["mode"]=PROMPT_MODE_LIST; result["prompts"]=prompts; result["hashes"]=[prompt_hash(p) for p in prompts]; result["notes"]=list(plan.get("notes") or [])+["external Clip Prompt input(s): "+", ".join(map(str,replaced))]
    return validate_prompt_plan(result)
def prompt_plan_report(plan):
    plan=validate_prompt_plan(plan); unique=len(set(plan["hashes"])); note="; ".join(plan.get("notes") or [])
    result=f"Prompt plan: {plan['mode']}; {plan['chunks']} chunks; {unique} unique prompt(s); {plan['chunk_seconds']:.3f}s per chunk."
    return result+(" "+note+"." if note else "")

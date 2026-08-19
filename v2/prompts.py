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
_TIMELINE_LIKE_HEADER=re.compile(r"^\s*\[\s*(?:(?:chunk|clip)\b|\d+(?:\.\d+)?[^\]]*(?:[-–—]|\bto\b))",re.IGNORECASE)
_LIST_SEPARATOR=re.compile(r"^\s*---+\s*$",re.MULTILINE)
class PromptPlanError(ValueError): pass
def _prompt_error(code,reason,*,line_number=None,source=None,suggested_fix):
    location=f" line {line_number}" if line_number is not None else ""
    lines=[f"{code}{location}: {reason}"]
    if source is not None: lines.append(f"Source: {source}")
    if suggested_fix: lines.append(f"Suggested fix: {suggested_fix}")
    raise PromptPlanError("\n".join(lines))
def prompt_hash(prompt:str)->str: return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
def _normalize_prompt(value:str,*,label:str)->str:
    return "" if value is None else str(value)
def _parse_json_list(script:str):
    stripped=script.lstrip()
    if not stripped.startswith("["): return None
    try: value=json.loads(script)
    except json.JSONDecodeError: return None
    if not isinstance(value,list) or not all(isinstance(item,str) for item in value): return None
    return [_normalize_prompt(item,label=f"prompt {index+1}") for index,item in enumerate(value)]
def _parse_list(script,chunks):
    values=_parse_json_list(script)
    if values is None: values=[_normalize_prompt(part,label=f"prompt {index+1}") for index,part in enumerate(_LIST_SEPARATOR.split(script)) if part.strip()]
    if not values: values=[str(script)]
    notes=[]
    if len(values)<chunks: notes.append(f"repeated the last prompt for {chunks-len(values)} chunk(s)"); values.extend([values[-1]]*(chunks-len(values)))
    elif len(values)>chunks: notes.append(f"ignored {len(values)-chunks} extra prompt(s)"); values=values[:chunks]
    return values,notes
def _timeline_preamble(script):
    body=[]
    for line in str(script).splitlines():
        if _TIMELINE_HEADER.match(line) or _CHUNK_HEADER.match(line): break
        body.append(line)
    return "\n".join(body).strip()
def _parse_timeline_sections(script,*,allow_preamble=True):
    preamble=_timeline_preamble(script)
    sections=[]; current=None; body=[]
    def finish():
        nonlocal current,body
        if current is None:
            if any(line.strip() for line in body) and not allow_preamble: raise PromptPlanError("timeline text before the first [0-5s] or [Chunk 1] header is not allowed")
            body=[]; return
        if not any(line.strip() for line in body):
            _prompt_error("H3C-P005","timeline section body is empty",line_number=current["line_number"],source=current["source"],suggested_fix="add prompt text below this header")
        prompt=_normalize_prompt("\n".join(body),label="timeline section")
        current["prompt"]=f"{preamble}\n\n{prompt}" if preamble else prompt
        sections.append(current); current=None; body=[]
    for line_number,line in enumerate(str(script).splitlines(),start=1):
        time_match=_TIMELINE_HEADER.match(line); chunk_match=_CHUNK_HEADER.match(line)
        if time_match or chunk_match:
            finish()
            if time_match:
                start=float(time_match.group("start")); end=float(time_match.group("end"))
                if not end>start: _prompt_error("H3C-P002","timeline end must be greater than its start",line_number=line_number,source=line.strip(),suggested_fix="use an increasing range such as [0-5s]")
                current={"kind":"time","start":start,"end":end,"line_number":line_number,"source":line.strip()}
            else:
                index=int(chunk_match.group("index"))
                if index<1: _prompt_error("H3C-P004","chunk numbers are one-based",line_number=line_number,source=line.strip(),suggested_fix="use [Chunk 1] or a larger one-based chunk number")
                current={"kind":"chunk","index":index,"line_number":line_number,"source":line.strip()}
            continue
        if _TIMELINE_LIKE_HEADER.match(line):
            _prompt_error("H3C-P001","invalid timeline header",line_number=line_number,source=line.strip(),suggested_fix="use [0-5s] or [Chunk 1]")
        body.append(line)
    finish()
    if not sections: raise PromptPlanError("timeline contains no sections")
    return sections
def parse_sparse_prompt_overrides(script):
    sections=_parse_timeline_sections(script,allow_preamble=False); overrides={}
    for item in sections:
        if item["kind"]!="chunk": raise PromptPlanError("Sparse Clip Overrides only accepts [Clip N] or [Chunk N] sections")
        index=int(item["index"])
        if index in overrides: raise PromptPlanError(f"Sparse Clip Overrides defines Clip {index} more than once")
        overrides[index]=item["prompt"]
    return overrides
def validate_sparse_prompt_overrides(overrides,*,chunks):
    chunks=int(chunks)
    if not isinstance(overrides,dict): raise PromptPlanError("Sparse Clip Overrides must be a dictionary")
    validated={}
    for index,prompt in overrides.items():
        if type(index) is not int: raise PromptPlanError("Sparse Clip Override numbers must be integers")
        if not 1<=index<=chunks: raise PromptPlanError(f"Sparse Clip Override {index} is outside the configured 1-{chunks} chunks")
        validated[index]=_normalize_prompt(prompt,label=f"Clip {index} Override")
    if not validated: raise PromptPlanError("Sparse Clip Overrides contains no overrides")
    return validated
def _parse_timeline(script,chunks,chunk_seconds):
    sections=_parse_timeline_sections(script); prompts=[]; notes=[]; diagnostics=[]
    if _timeline_preamble(script): notes.append("applied timeline preamble to all chunks")
    seen_chunks={}; total_end=chunks*chunk_seconds; usable=[]
    for item in sections:
        if item["kind"]=="chunk":
            index=int(item["index"])
            if index in seen_chunks:
                _prompt_error("H3C-P003",f"timeline defines Chunk {index} more than once",line_number=item["line_number"],source=item["source"],suggested_fix=f"keep only one [Chunk {index}] section")
            seen_chunks[index]=item
            if index<=chunks: usable.append(item)
            else: diagnostics.append({"level":"warning","code":"H3C-P104","message":f"ignored {item['source']} because the configured sequence has only {chunks} chunk(s)"})
        elif min(total_end,item["end"])-max(0.0,item["start"])>0:
            usable.append(item)
        else:
            diagnostics.append({"level":"warning","code":"H3C-P104","message":f"ignored {item['source']} because it is outside 0-{total_end:.3f}s"})
    if not usable:
        _prompt_error("H3C-P005","timeline contains no usable prompt section for the configured sequence",suggested_fix="add a section such as [0-5s] with non-empty prompt text")
    previous_prompt=None; previous_source=None
    for chunk_index in range(1,chunks+1):
        chunk_sections=[item for item in sections if item["kind"]=="chunk" and item["index"]==chunk_index]
        if chunk_sections:
            selected=chunk_sections[0]; prompts.append(selected["prompt"]); previous_prompt=selected["prompt"]; previous_source=f"{selected['source']} at line {selected['line_number']}"
            diagnostics.append({"level":"info","code":"H3C-P000","message":f"Chunk {chunk_index} source: {previous_source}"}); continue
        start=(chunk_index-1)*chunk_seconds; end=chunk_index*chunk_seconds; scored=[]
        for order,item in enumerate(sections):
            if item["kind"]!="time": continue
            overlap=max(0.0,min(end,item["end"])-max(start,item["start"]))
            if overlap>0: scored.append((overlap,-order,item))
        if not scored:
            if previous_prompt is None:
                selected=usable[0]; fallback_reason=f"used earliest valid prompt from {selected['source']}"
            else:
                selected=None; fallback_reason=f"reused previous prompt from {previous_source}"
            prompt=selected["prompt"] if selected is not None else previous_prompt
            source=f"{selected['source']} at line {selected['line_number']}" if selected is not None else previous_source
            prompts.append(prompt); previous_prompt=prompt; previous_source=source
            diagnostics.append({"level":"warning","code":"H3C-P101","message":f"Timeline does not cover Chunk {chunk_index} ({start:.3f}-{end:.3f}s); {fallback_reason}."})
            diagnostics.append({"level":"info","code":"H3C-P000","message":f"Chunk {chunk_index} source: fallback to {source}"}); continue
        scored.sort(reverse=True,key=lambda row:(row[0],row[1])); selected=scored[0][2]; prompts.append(selected["prompt"]); previous_prompt=selected["prompt"]; previous_source=f"{selected['source']} at line {selected['line_number']}"
        diagnostics.append({"level":"info","code":"H3C-P000","message":f"Chunk {chunk_index} source: {previous_source}"})
        if len(scored)>1 and abs(scored[0][0]-scored[1][0])<1e-9: notes.append(f"chunk {chunk_index} had an equal-overlap timeline tie; used the earlier section")
    return prompts,notes,diagnostics
def detect_prompt_mode(script):
    text=str(script)
    for line in text.splitlines():
        if _TIMELINE_HEADER.match(line) or _CHUNK_HEADER.match(line): return PROMPT_MODE_TIMELINE
        if _TIMELINE_LIKE_HEADER.match(line): return PROMPT_MODE_FIXED
    if _parse_json_list(text) is not None or _LIST_SEPARATOR.search(text): return PROMPT_MODE_LIST
    return PROMPT_MODE_FIXED
def resolve_prompt_mode(mode,script):
    explicit={PROMPT_FORMAT_FIXED:PROMPT_MODE_FIXED,PROMPT_FORMAT_LIST:PROMPT_MODE_LIST,PROMPT_FORMAT_TIMELINE:PROMPT_MODE_TIMELINE}
    if mode==PROMPT_FORMAT_AUTO: return detect_prompt_mode(script)
    if mode in explicit: return explicit[mode]
    if mode in (PROMPT_MODE_FIXED,PROMPT_MODE_LIST,PROMPT_MODE_TIMELINE): return mode
    return PROMPT_MODE_FIXED
def make_prompt_plan(*,mode,script,chunks,chunk_seconds):
    chunks=int(chunks); chunk_seconds=float(chunk_seconds)
    if not 1<=chunks<=16: raise PromptPlanError("chunks must be between 1 and 16")
    if not 4.0<=chunk_seconds<=15.0: raise PromptPlanError("chunk_seconds must be between 4.0 and 15.0 for native H3")
    notes=[]; diagnostics=[]
    try:
        resolved_mode=resolve_prompt_mode(mode,script)
        if mode==PROMPT_FORMAT_AUTO:
            detected={PROMPT_MODE_FIXED:PROMPT_FORMAT_FIXED,PROMPT_MODE_LIST:PROMPT_FORMAT_LIST,PROMPT_MODE_TIMELINE:PROMPT_FORMAT_TIMELINE}[resolved_mode]; notes.append(f"Auto detected {detected}")
        if resolved_mode==PROMPT_MODE_FIXED: prompt=_normalize_prompt(script,label="fixed prompt"); prompts=[prompt]*chunks
        elif resolved_mode==PROMPT_MODE_LIST: prompts,parse_notes=_parse_list(script,chunks); notes.extend(parse_notes)
        elif resolved_mode==PROMPT_MODE_TIMELINE: prompts,parse_notes,diagnostics=_parse_timeline(script,chunks,chunk_seconds); notes.extend(parse_notes)
        else: raise PromptPlanError(f"unknown prompt mode: {resolved_mode!r}")
    except (PromptPlanError,TypeError,ValueError) as exc:
        resolved_mode=PROMPT_MODE_FIXED; prompts=[_normalize_prompt(script,label="fixed prompt")]*chunks
        notes.append("Prompt syntax was not recognized; used Fixed prompt fallback")
        diagnostics=[{"level":"warning","code":"H3C-P100","message":str(exc)}]
    result={"magic":PROMPT_PLAN_MAGIC,"schema_version":PROMPT_PLAN_SCHEMA_VERSION,"mode":resolved_mode,"chunks":chunks,"chunk_seconds":chunk_seconds,"prompts":prompts,"hashes":[prompt_hash(p) for p in prompts],"notes":notes}
    if diagnostics: result["diagnostics"]=diagnostics
    return result
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
    diagnostics=plan.get("diagnostics")
    if diagnostics is not None and (not isinstance(diagnostics,list) or not all(isinstance(item,dict) for item in diagnostics)): raise PromptPlanError("prompt-plan diagnostics are invalid")
    return plan
def build_sampler_prompt_plan(*,prompt_mode,prompt_script,sequence_prompt,prompt_plan,chunks,chunk_seconds):
    chunks=int(chunks); chunk_seconds=float(chunk_seconds)
    if sequence_prompt is not None: return make_prompt_plan(mode=prompt_mode,script=sequence_prompt,chunks=chunks,chunk_seconds=chunk_seconds)
    if prompt_plan is not None:
        plan=validate_prompt_plan(prompt_plan)
        prompts=list(plan["prompts"])
        if len(prompts)<chunks: prompts.extend([prompts[-1] if prompts else ""]*(chunks-len(prompts)))
        elif len(prompts)>chunks: prompts=prompts[:chunks]
        result=dict(plan); result["chunks"]=chunks; result["chunk_seconds"]=chunk_seconds; result["prompts"]=prompts; result["hashes"]=[prompt_hash(p) for p in prompts]
        if int(plan["chunks"])!=chunks or abs(float(plan["chunk_seconds"])-chunk_seconds)>1e-6: result["notes"]=list(plan.get("notes") or [])+["adapted connected prompt plan to Sampler chunk settings"]
        return validate_prompt_plan(result)
    return make_prompt_plan(mode=prompt_mode,script=prompt_script,chunks=chunks,chunk_seconds=chunk_seconds)
def apply_prompt_overrides(plan,overrides):
    plan=validate_prompt_plan(plan); prompts=list(plan["prompts"]); replaced=[]
    for index,value in enumerate(overrides[:int(plan["chunks"])]):
        if value is None: continue
        prompts[index]=_normalize_prompt(value,label=f"Clip {index+1} Prompt"); replaced.append(index+1)
    if not replaced: return plan
    result=dict(plan); result["mode"]=PROMPT_MODE_LIST; result["prompts"]=prompts; result["hashes"]=[prompt_hash(p) for p in prompts]; result["notes"]=list(plan.get("notes") or [])+["external Clip Prompt input(s): "+", ".join(map(str,replaced))]; result.pop("diagnostics",None)
    return validate_prompt_plan(result)
def prompt_plan_report(plan):
    plan=validate_prompt_plan(plan); unique=len(set(plan["hashes"])); note="; ".join(plan.get("notes") or [])
    result=f"Prompt plan: {plan['mode']}; {plan['chunks']} chunks; {unique} unique prompt(s); {plan['chunk_seconds']:.3f}s per chunk."
    if note: result+=" "+note+"."
    diagnostics=list(plan.get("diagnostics") or [])
    if not diagnostics: return result+"\nPrompt Preflight: OK."
    lines=[result,"Prompt Preflight:"]
    for item in diagnostics:
        level=str(item.get("level","info")).upper(); code=str(item.get("code","H3C-P000")); message=str(item.get("message",""))
        lines.append(f"- {level} {code}: {message}")
    return "\n".join(lines)

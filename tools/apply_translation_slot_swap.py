#!/usr/bin/env python3
"""Assign translated strings to differently sized slots inside each MWo3 overlay."""

from __future__ import annotations

import argparse, csv, json, re, struct
from collections import defaultdict
from pathlib import Path

from dte_codec import encode_whole_page, load_pairs
from translation_cache import load_best_by_source

JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
UNSAFE = re.compile(r"[^\x20-\x7e\n\r\t「」]")
CONTROL = re.compile(r"\$[A-Za-z]")


def starts(data: bytes) -> list[int]:
    out=[]; pos=0
    while (pos := data.find(b"MWo3", pos)) >= 0: out.append(pos); pos += 4
    return out


def valid(source: str, text: str) -> bool:
    return bool(text) and not JAPANESE.search(text) and not UNSAFE.search(text) \
        and CONTROL.findall(source) == CONTROL.findall(text) \
        and [c for c in source if c in "「」"] == [c for c in text if c in "「」"] \
        and ("「" not in source or (len(text.splitlines()) <= 3 and all(
            len(line.replace("「", "").replace("」", "")) <= 44 for line in text.splitlines())))


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("stage",type=Path); ap.add_argument("occurrences",type=Path)
    ap.add_argument("output",type=Path); ap.add_argument("--cache",type=Path,action="append",required=True)
    ap.add_argument("--dte",type=Path,required=True); ap.add_argument("--report",type=Path,required=True); a=ap.parse_args()
    stage=bytearray(a.stage.read_bytes()); pairs=load_pairs(a.dte); translations=load_best_by_source(a.cache)
    with a.occurrences.open(encoding="utf8",newline="") as f: rows=list(csv.DictReader(f,dialect="excel-tab"))
    boundaries=starts(stage); by_member=defaultdict(list)
    for row in rows: by_member[row["member"]].append(row)
    report=[]
    for i,begin in enumerate(boundaries):
        end=boundaries[i+1] if i+1<len(boundaries) else len(stage); member=stage[begin:end]
        name=member[0x20:0x40].split(b"\0",1)[0].decode("ascii","replace"); load=struct.unpack_from("<I",member,8)[0]
        references=defaultdict(list)
        for p in range(0,len(member)-3,4):
            references[struct.unpack_from("<I",member,p)[0]].append(p)
        slots=[]
        for row in by_member.get(name,[]):
            absolute=int(row["absolute_offset"],0); relative=absolute-begin; address=load+relative
            refs=references.get(address,[])
            original=row["source"].encode("cp932"); text=str(translations.get(row["source"],{}).get("translation",""))
            translated=False; raw=original
            if valid(row["source"],text):
                try: raw,_=encode_whole_page(text,pairs); translated=True
                except (ValueError,UnicodeEncodeError): pass
            slots.append({"row":row,"relative":relative,"capacity":int(row["max_encoded_bytes"]),"refs":refs,
                          "original":original,"raw":raw,"translated":translated,"text":text})
        movable=[x for x in slots if x["refs"]]; fixed=[x for x in slots if not x["refs"]]
        # Fall back the most space-hungry translations until a complete sorted
        # size/capacity matching exists. Original strings always fit own slots.
        while True:
            tasks=sorted(movable,key=lambda x:len(x["raw"])); destinations=sorted(movable,key=lambda x:x["capacity"])
            failures=[n for n,(task,dest) in enumerate(zip(tasks,destinations)) if len(task["raw"])>dest["capacity"]]
            if not failures: break
            choices=[x for x in movable if x["translated"]]
            if not choices: raise SystemExit(f"{name}: original strings do not fit their slots")
            victim=max(choices,key=lambda x:len(x["raw"])-len(x["original"])); victim["raw"]=victim["original"]; victim["translated"]=False
        for task,dest in zip(tasks,destinations):
            start=begin+dest["relative"]; cap=dest["capacity"]
            stage[start:start+cap+1]=task["raw"]+b"\0"*(cap+1-len(task["raw"]))
            for ref in task["refs"]: struct.pack_into("<I",stage,begin+ref,load+dest["relative"])
            report.append({"id":task["row"]["id"],"member":name,"source":task["row"]["source"],
                           "status":"applied-swapped" if task["translated"] else "japanese-fallback",
                           "encoded_bytes":len(task["raw"]),"destination":hex(begin+dest["relative"]),"allocation":cap})
        for task in fixed:
            if task["translated"] and len(task["raw"])<=task["capacity"]:
                start=begin+task["relative"];cap=task["capacity"]
                stage[start:start+cap+1]=task["raw"]+b"\0"*(cap+1-len(task["raw"])); status="applied-fixed"
            else: status="japanese-no-pointer"
            report.append({"id":task["row"]["id"],"member":name,"source":task["row"]["source"],"status":status,
                           "encoded_bytes":len(task["raw"]),"destination":hex(begin+task["relative"]),"allocation":task["capacity"]})
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(stage)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(report[0]),dialect="excel-tab");w.writeheader();w.writerows(report)
    counts=defaultdict(int)
    for row in report:counts[row["status"]]+=1
    print(json.dumps(counts,sort_keys=True))

if __name__=="__main__": main()

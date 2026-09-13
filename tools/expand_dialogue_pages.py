#!/usr/bin/env python3
"""Safely clone verified MWo3 dialogue records for English pages 2 and 3."""

from __future__ import annotations

import argparse, csv, struct
from collections import defaultdict
from pathlib import Path

from dte_codec import encode_whole_page, load_pairs


def align(n: int, a: int = 0x80) -> int:
    return (n + a - 1) & -a


def starts(data: bytes) -> list[int]:
    out=[]; p=0
    while (p := data.find(b"MWo3", p)) >= 0:
        out.append(p); p += 4
    return out


def member_name(data: bytes) -> str:
    return data[0x20:0x40].split(b"\0", 1)[0].decode("ascii")


def locate(clean: bytes, load: int, target: int):
    found=[]
    for ref in range(0, len(clean)-3, 4):
        if struct.unpack_from("<I", clean, ref)[0] != load + target or ref < 8:
            continue
        record=ref-8
        if struct.unpack_from("<I", clean, record)[0] != 1:
            continue
        first=record
        while first >= 24 and struct.unpack_from("<I", clean, first-24)[0] == 1:
            first -= 24
        block=first-8
        if block < 0 or struct.unpack_from("<I", clean, block)[0] != 1:
            continue
        end=first
        while end+24 <= len(clean) and struct.unpack_from("<I", clean, end)[0] == 1:
            end += 24
        # Preserve the complete 0x28-byte script-block tail. The words after
        # 0x7e are part of the sequencer boundary even though they are zero;
        # truncating them leaves a portrait onscreen with no dialogue box.
        if end+0x28 > len(clean) or any(clean[end:end+8]) or struct.unpack_from("<I", clean, end+16)[0] != 0x7e:
            continue
        parents=[p for p in range(0,len(clean)-3,4) if struct.unpack_from("<I",clean,p)[0] == load+block]
        if len(parents) == 1:
            found.append((block,end+0x28,parents[0],record))
    unique=list(dict.fromkeys(found))
    return unique[0] if len(unique)==1 else None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("clean_stage",type=Path); ap.add_argument("patched_stage",type=Path)
    ap.add_argument("occurrences",type=Path); ap.add_argument("table",type=Path)
    ap.add_argument("dte",type=Path); ap.add_argument("output",type=Path)
    args=ap.parse_args()
    with args.table.open(encoding="utf-8-sig",newline="") as f:
        table=list(csv.DictReader(f,dialect="excel-tab"))
    pages={r["Original Japanese"]:[(r.get("English Page 2") or "").strip(),(r.get("English Page 3") or "").strip()]
           for r in table if (r.get("English Page 2") or "").strip() or (r.get("English Page 3") or "").strip()}
    if not pages:
        args.output.write_bytes(args.patched_stage.read_bytes()); print("no inserted dialogue pages requested"); return
    with args.occurrences.open(encoding="utf-8",newline="") as f:
        occ=list(csv.DictReader(f,dialect="excel-tab"))
    wanted=defaultdict(list); matched_sources=set()
    for r in occ:
        if r["source"] in pages: wanted[r["member"]].append(r); matched_sources.add(r["source"])
    absent=set(pages)-matched_sources
    if absent:
        raise SystemExit(f"extra pages are dialogue-only; {len(absent)} requested source(s) are not dialogue")
    clean_all=args.clean_stage.read_bytes(); patched_all=args.patched_stage.read_bytes()
    cs=starts(clean_all); ps=starts(patched_all)
    clean_members={member_name(clean_all[s:(cs[i+1] if i+1<len(cs) else len(clean_all))]):clean_all[s:(cs[i+1] if i+1<len(cs) else len(clean_all))] for i,s in enumerate(cs)}
    pairs=load_pairs(args.dte); rebuilt=[]; expanded=0; affected=set()
    for i,s in enumerate(ps):
        end=ps[i+1] if i+1<len(ps) else len(patched_all); member=bytearray(patched_all[s:end]); name=member_name(member)
        clean=clean_members[name]; load=struct.unpack_from("<I",clean,8)[0]
        blocks=defaultdict(dict)
        for row in wanted.get(name,[]):
            hit=locate(clean,load,int(row["member_offset"],0))
            if hit: blocks[hit[:3]][hit[3]]=pages[row["source"]]
        if wanted.get(name) and not blocks:
            raise SystemExit(f"{name}: requested extra pages, but no safe dialogue record was found")
        string_pool={}
        for (bs,be,parent), records in sorted(blocks.items()):
            first=bs+8; cursor=first; new_records=bytearray()
            while cursor < be-0x28:
                rec=bytes(member[cursor:cursor+24]); new_records.extend(rec)
                for page in records.get(cursor,[]):
                    if not page: continue
                    raw,_=encode_whole_page(page,pairs)
                    if raw not in string_pool:
                        pos=align(len(member),8); member.extend(b"\0"*(pos-len(member))); member.extend(raw+b"\0"); string_pool[raw]=pos
                    clone=bytearray(rec); struct.pack_into("<I",clone,8,load+string_pool[raw]); new_records.extend(clone); expanded+=1
                cursor+=24
            new_block=align(len(member)); member.extend(b"\0"*(new_block-len(member)))
            member.extend(member[bs:bs+8]+new_records+member[be-0x28:be])
            if struct.unpack_from("<I",member,parent)[0] != load+bs:
                raise SystemExit(f"{name}: parent pointer changed before page expansion")
            struct.pack_into("<I",member,parent,load+new_block); affected.add(name)
        if blocks:
            size=align(len(member)); member.extend(b"\0"*(size-len(member)))
            growth=size-(end-s); struct.pack_into("<I",member,0x10,struct.unpack_from("<I",member,0x10)[0]+growth)
            struct.pack_into("<I",member,0x18,load+size); struct.pack_into("<I",member,0x1c,load+size)
        rebuilt.append(bytes(member))
    missing=set(wanted)-affected
    if missing: raise SystemExit("no safe page blocks in: "+", ".join(sorted(missing)))
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_bytes(b"".join(rebuilt))
    print(f"inserted {expanded} dialogue page records in {len(affected)} overlays; STAGE.BIN {len(patched_all)} -> {args.output.stat().st_size}")

if __name__ == "__main__": main()

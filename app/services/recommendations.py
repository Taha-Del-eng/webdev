def recommend(products, current=None, limit=4):
    if not products: return []
    if not current: return products[:limit]
    cat = (current.get("category") or "").lower()
    raw_tags=current.get("tags") or []
    if isinstance(raw_tags,str):
        raw_tags=raw_tags.split(",")
    tags={str(t).strip().lower() for t in raw_tags if str(t).strip()}
    scored=[]
    for p in products:
        if p.get("id")==current.get("id"): continue
        score=0
        if p.get("category","").lower()==cat: score += 3
        raw_ptags=p.get("tags") or []
        if isinstance(raw_ptags,str):
            raw_ptags=raw_ptags.split(",")
        ptags={str(t).strip().lower() for t in raw_ptags if str(t).strip()}
        score += len(tags & ptags) * 2
        if abs(float(p.get("price",0))-float(current.get("price",0))) < max(float(current.get("price",1))*0.5,1500): score += 1
        scored.append((score,p))
    scored.sort(key=lambda x:(-x[0],-float(x[1].get("rating") or 0)))
    return [p for _,p in scored[:limit]]

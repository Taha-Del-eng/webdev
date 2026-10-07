def recommend(products, current=None, limit=4):
    if not products: return []
    if not current: return products[:limit]
    cat = (current.get("category") or "").lower()
    tags = set((current.get("tags") or "").lower().split(","))
    scored=[]
    for p in products:
        if p.get("id")==current.get("id"): continue
        score=0
        if p.get("category","").lower()==cat: score += 3
        ptags=set((p.get("tags") or "").lower().split(","))
        score += len(tags & ptags) * 2
        if abs(float(p.get("price",0))-float(current.get("price",0))) < max(float(current.get("price",1))*0.5,1500): score += 1
        scored.append((score,p))
    scored.sort(key=lambda x:(-x[0],-float(x[1].get("rating") or 0)))
    return [p for _,p in scored[:limit]]
